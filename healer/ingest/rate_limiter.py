"""Investigation rate limit (Chapter 2, Stage 1: Detect).

Without a limiter, one flapping service floods the pipeline and the humans stop trusting it.
The counter lives in DynamoDB and is incremented atomically, so concurrent events cannot race
past the limit.
"""

from __future__ import annotations

import time
from typing import Any

from botocore.exceptions import ClientError

TABLE_NAME = "investigation_rate_limits"


def hour_bucket(now: float | None = None) -> str:
    """UTC hour window, for example '2026-10-09-14'."""
    return time.strftime("%Y-%m-%d-%H", time.gmtime(now))


def claim_issue(
    table: Any, issue_id: str, ttl_seconds: int = 86400, now: float | None = None
) -> bool:
    """Atomically note that this Sentry issue has been taken. False if it already was.

    Sentry can deliver one error more than once: an alert rule and an integration both firing, a
    retry after a slow response. Without this each delivery would run the whole pipeline and open
    its own pull request. The marker lives in the same table as the limiter and expires after a day.
    """
    stamp = time.time() if now is None else now
    try:
        table.put_item(
            Item={
                "service": f"sentry-issue#{issue_id}",
                "hour": "claimed",
                "claimed_at": int(stamp),
                "expires_at": int(stamp) + ttl_seconds,
            },
            ConditionExpression="attribute_not_exists(service)",
        )
        return True
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def try_acquire_investigation_slot(
    table: Any, service_name: str, hour_bucket: str, limit: int = 3
) -> bool:
    """Atomically check-and-increment a per-service, per-hour counter.

    Returns True if this event is allowed to trigger an investigation. `table` is a boto3
    DynamoDB Table resource.
    """
    try:
        table.update_item(
            Key={"service": service_name, "hour": hour_bucket},
            UpdateExpression="ADD invocation_count :inc",
            ConditionExpression=(
                "attribute_not_exists(invocation_count) OR invocation_count < :limit"
            ),
            ExpressionAttributeValues={":inc": 1, ":limit": limit},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # rate limit hit, drop the event
        raise


def create_table(dynamodb: Any, table_name: str = TABLE_NAME) -> Any:
    """Create the counter table, for LocalStack and the tests."""
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "service", "AttributeType": "S"},
            {"AttributeName": "hour", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "service", "KeyType": "HASH"},
            {"AttributeName": "hour", "KeyType": "RANGE"},
        ],
    )
