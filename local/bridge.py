"""Local stand-in for two pieces of AWS that have no emulator here.

1. Bootstrap: creates the S3 bucket and the DynamoDB table (idempotent). On AWS
   the SAM template creates them.
2. Event source mapping: long-polls SQS and invokes the analyzer Lambda container
   through the Runtime Interface Emulator with the same event shape AWS sends,
   then deletes only the messages the function did not report as failed. Failed
   messages reappear after the visibility timeout; after maxReceiveCount the
   queue moves them to the dead-letter queue, as on AWS.
"""
import json
import logging
import os
import time
import urllib.request

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

logging.basicConfig(level=logging.INFO, format="%(asctime)s bridge %(message)s")
log = logging.getLogger()

QUEUE_URL = os.environ["HAKEM_QUEUE_URL"]
BUCKET = os.environ["HAKEM_BUCKET"]
TABLE = os.environ["HAKEM_JOBS_TABLE"]
LAMBDA_URL = os.environ["LAMBDA_URL"]
BATCH = int(os.environ.get("BATCH_SIZE", "5"))

s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"],
                  config=Config(s3={"addressing_style": "path"}))
ddb = boto3.client("dynamodb", endpoint_url=os.environ["DYNAMODB_ENDPOINT"])
sqs = boto3.client("sqs", endpoint_url=os.environ["SQS_ENDPOINT"])


def retry(fn, what):
    for attempt in range(30):
        try:
            return fn()
        except (EndpointConnectionError, ConnectionError) as exc:
            log.info("waiting for %s (%s)", what, exc.__class__.__name__)
            time.sleep(2)
    raise RuntimeError(f"{what} never became reachable")


def bootstrap():
    def bucket():
        try:
            s3.create_bucket(Bucket=BUCKET)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise

    def table():
        try:
            ddb.create_table(TableName=TABLE,
                             KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                             AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                             BillingMode="PAY_PER_REQUEST")
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceInUseException":
                raise

    retry(bucket, "S3")
    retry(table, "DynamoDB")
    retry(lambda: sqs.get_queue_attributes(QueueUrl=QUEUE_URL), "SQS")
    log.info("bucket %s, table %s and queue ready", BUCKET, TABLE)


def invoke(records):
    event = {"Records": [{
        "messageId": m["MessageId"],
        "receiptHandle": m["ReceiptHandle"],
        "body": m["Body"],
        "attributes": m.get("Attributes", {}),
        "eventSource": "aws:sqs",
    } for m in records]}
    req = urllib.request.Request(LAMBDA_URL, data=json.dumps(event).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.loads(resp.read() or b"{}")


def poll_forever():
    while True:
        resp = sqs.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=BATCH,
                                   WaitTimeSeconds=10, AttributeNames=["ApproximateReceiveCount"])
        msgs = resp.get("Messages", [])
        if not msgs:
            continue
        try:
            result = invoke(msgs)
        except Exception as exc:  # function crashed or timed out: the whole batch is retried
            log.error("invocation failed, %d message(s) will be retried: %s", len(msgs), exc)
            continue
        if result.get("errorMessage"):
            log.error("function error, batch will be retried: %s", result["errorMessage"])
            continue
        failed = {f["itemIdentifier"] for f in result.get("batchItemFailures", [])}
        for m in msgs:
            if m["MessageId"] not in failed:
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=m["ReceiptHandle"])
        log.info("batch of %d: %d done, %d to retry", len(msgs), len(msgs) - len(failed), len(failed))


if __name__ == "__main__":
    bootstrap()
    poll_forever()
