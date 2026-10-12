import json
from pathlib import Path

import anthropic
import boto3
import httpx2
import pytest
from moto import mock_aws

from hakem_analyzer import handler

SAMPLE = (Path(__file__).resolve().parents[1] / "samples" / "clean_markdown.md").read_text(encoding="utf-8")
BUCKET, TABLE = "hakem-manuscripts", "hakem-jobs"


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("HAKEM_LLM", "off")
    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-central-1"})
        ddb = boto3.client("dynamodb")
        ddb.create_table(TableName=TABLE, KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                         AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                         BillingMode="PAY_PER_REQUEST")
        handler._s3 = handler._ddb = None
        yield s3, ddb
        handler._s3 = handler._ddb = None


def enqueue(s3, ddb, job_id, text=SAMPLE):
    s3.put_object(Bucket=BUCKET, Key=f"manuscripts/{job_id}.txt", Body=text.encode())
    ddb.put_item(TableName=TABLE, Item={"id": {"S": job_id}, "status": {"S": "QUEUED"}})
    return {"messageId": f"m-{job_id}",
            "body": json.dumps({"id": job_id, "bucket": BUCKET, "key": f"manuscripts/{job_id}.txt"})}


def item(ddb, job_id):
    return ddb.get_item(TableName=TABLE, Key={"id": {"S": job_id}})["Item"]


def test_rule_only_report_is_written(aws):
    s3, ddb = aws
    out = handler.lambda_handler({"Records": [enqueue(s3, ddb, "a1")]}, None)
    assert out == {"batchItemFailures": []}
    it = item(ddb, "a1")
    assert it["status"]["S"] == "DONE"
    report = json.loads(it["report"]["S"])
    assert report["checks"]["issues"] == [] and report["review"] is None


def test_redelivered_message_is_not_reprocessed(aws, monkeypatch):
    s3, ddb = aws
    rec = enqueue(s3, ddb, "a2")
    handler.lambda_handler({"Records": [rec]}, None)
    monkeypatch.setattr(handler, "analyze_text", lambda *a: pytest.fail("reprocessed"))
    assert handler.process_message(json.loads(rec["body"])) == "duplicate"


def test_missing_object_is_retried_alone(aws):
    s3, ddb = aws
    good = enqueue(s3, ddb, "ok")
    bad = {"messageId": "m-bad", "body": json.dumps({"id": "ok2", "bucket": BUCKET, "key": "nope.txt"})}
    ddb.put_item(TableName=TABLE, Item={"id": {"S": "ok2"}, "status": {"S": "QUEUED"}})
    out = handler.lambda_handler({"Records": [good, bad]}, None)
    assert out == {"batchItemFailures": [{"itemIdentifier": "m-bad"}]}
    assert item(ddb, "ok")["status"]["S"] == "DONE"


def test_llm_rate_limit_requeues_and_retries(aws, monkeypatch):
    s3, ddb = aws
    monkeypatch.setenv("HAKEM_LLM", "on")
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def boom(*a, **k):
        raise anthropic.RateLimitError("slow down", response=httpx2.Response(429, request=req), body=None)

    monkeypatch.setattr(handler, "review_manuscript", boom)
    out = handler.lambda_handler({"Records": [enqueue(s3, ddb, "r1")]}, None)
    assert out == {"batchItemFailures": [{"itemIdentifier": "m-r1"}]}
    assert item(ddb, "r1")["status"]["S"] == "QUEUED"


def test_model_refusal_keeps_rule_report(aws, monkeypatch):
    s3, ddb = aws
    monkeypatch.setenv("HAKEM_LLM", "on")

    def refuse(*a, **k):
        raise handler.ReviewError("Model declined to review (category: None).")

    monkeypatch.setattr(handler, "review_manuscript", refuse)
    out = handler.lambda_handler({"Records": [enqueue(s3, ddb, "x1")]}, None)
    assert out == {"batchItemFailures": []}
    report = json.loads(item(ddb, "x1")["report"]["S"])
    assert report["review"] is None and "declined" in report["review_error"]


def test_oversized_upload_fails_cleanly(aws, monkeypatch):
    s3, ddb = aws
    monkeypatch.setattr(handler, "MAX_BYTES", 100)
    handler.lambda_handler({"Records": [enqueue(s3, ddb, "big")]}, None)
    assert item(ddb, "big")["status"]["S"] == "FAILED"


def test_malformed_message_is_dropped_not_retried(aws):
    out = handler.lambda_handler({"Records": [{"messageId": "m-x", "body": "not json"}]}, None)
    assert out == {"batchItemFailures": []}


def test_api_key_is_read_from_secrets_manager(aws, monkeypatch):
    sm = boto3.client("secretsmanager")
    arn = sm.create_secret(Name="hakem/anthropic", SecretString="sk-test-123\n")["ARN"]
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY_SECRET_ARN", arn)
    monkeypatch.setenv("HAKEM_LLM", "auto")
    handler._load_api_key_from_secret()
    assert handler.llm_enabled()
    import os
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test-123"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
