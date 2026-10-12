"""AWS Lambda entry point, triggered by SQS.

Each SQS message names a manuscript already stored in S3 by the API:
    {"id": "...", "bucket": "...", "key": "..."}

The handler runs the rule-based checks, optionally the LLM review, and writes the
report to the DynamoDB job item. It uses partial batch responses: a message whose
processing failed for a transient reason (S3/DynamoDB/LLM rate limit or outage)
is reported back so SQS retries only that one, and after maxReceiveCount it moves
to the dead-letter queue. A manuscript the model declines or cannot review is not
retried: it is stored with the rule-based findings and the reason.

Endpoints come from the standard AWS_ENDPOINT_URL* variables, so the same code
talks to real AWS or to local emulators.
"""
from __future__ import annotations

import json
import logging
import os
import time

import anthropic
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .checks import run_checks
from .review import ReviewError, review_manuscript

log = logging.getLogger()
log.setLevel(logging.INFO)

TABLE = os.environ.get("JOBS_TABLE", "hakem-jobs")
MAX_BYTES = int(os.environ.get("MAX_MANUSCRIPT_BYTES", str(2 * 1024 * 1024)))

_s3 = None
_ddb = None


def _clients():
    global _s3, _ddb
    if _s3 is None:
        # Local S3 emulators need path-style URLs; real S3 works with either.
        style = os.environ.get("HAKEM_S3_ADDRESSING", "auto")
        _s3 = boto3.client("s3", config=Config(s3={"addressing_style": style}))
        _ddb = boto3.client("dynamodb")
    return _s3, _ddb


def _load_api_key_from_secret() -> None:
    """On AWS the key lives in Secrets Manager, not in the function's environment
    configuration; read it once per cold start."""
    arn = os.environ.get("ANTHROPIC_API_KEY_SECRET_ARN")
    if arn and not os.environ.get("ANTHROPIC_API_KEY"):
        secret = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
        os.environ["ANTHROPIC_API_KEY"] = secret.strip()


_load_api_key_from_secret()


def llm_enabled() -> bool:
    mode = os.environ.get("HAKEM_LLM", "auto").lower()
    if mode == "off":
        return False
    if mode == "on":
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


class TransientError(RuntimeError):
    """Worth retrying via SQS redelivery."""


def _set_status(ddb, job_id: str, status: str, **extra: str) -> None:
    names = {"#s": "status", "#u": "updatedAt"}
    values = {":s": {"S": status}, ":u": {"N": str(int(time.time()))}}
    sets = ["#s = :s", "#u = :u"]
    for i, (k, v) in enumerate(extra.items()):
        names[f"#e{i}"] = k
        values[f":e{i}"] = {"S": v}
        sets.append(f"#e{i} = :e{i}")
    ddb.update_item(TableName=TABLE, Key={"id": {"S": job_id}},
                    UpdateExpression="SET " + ", ".join(sets),
                    ExpressionAttributeNames=names, ExpressionAttributeValues=values)


def analyze_text(text: str, use_llm: bool) -> dict:
    checks = run_checks(text)
    report = {"checks": checks.to_dict(), "review": None, "review_error": None}
    if use_llm:
        try:
            report["review"] = review_manuscript(text, report["checks"]["issues"])
        except ReviewError as exc:
            report["review_error"] = str(exc)
    return report


def process_message(body: dict) -> str:
    s3, ddb = _clients()
    job_id, bucket, key = body["id"], body["bucket"], body["key"]

    item = ddb.get_item(TableName=TABLE, Key={"id": {"S": job_id}}).get("Item")
    if item is None:
        log.warning("job %s not found; dropping message", job_id)
        return "missing"
    if item["status"]["S"] == "DONE":
        return "duplicate"  # SQS is at-least-once; a redelivered message must not redo paid work

    _set_status(ddb, job_id, "PROCESSING")
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        _set_status(ddb, job_id, "QUEUED")  # do not leave the job looking "in progress"
        raise TransientError(f"s3 get_object failed: {exc}") from exc
    raw = obj["Body"].read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        _set_status(ddb, job_id, "FAILED", error=f"Manuscript is larger than {MAX_BYTES} bytes.")
        return "too_large"
    text = raw.decode("utf-8", errors="replace")

    started = time.time()
    try:
        report = analyze_text(text, llm_enabled())
    except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
        _set_status(ddb, job_id, "QUEUED")
        raise TransientError(f"LLM temporarily unavailable: {exc}") from exc
    report["elapsed_ms"] = int((time.time() - started) * 1000)
    _set_status(ddb, job_id, "DONE", report=json.dumps(report, ensure_ascii=False))
    log.info("job %s done: %d issues, review=%s", job_id, len(report["checks"]["issues"]),
             report["review"] is not None)
    return "done"


def lambda_handler(event, context):
    failures = []
    for record in event.get("Records", []):
        try:
            process_message(json.loads(record["body"]))
        except (TransientError, ClientError) as exc:
            log.error("retrying message %s: %s", record.get("messageId"), exc)
            failures.append({"itemIdentifier": record["messageId"]})
        except (KeyError, json.JSONDecodeError) as exc:
            log.error("malformed message %s dropped: %s", record.get("messageId"), exc)
    return {"batchItemFailures": failures}
