"""The alert flood limiter (Chapter 5, "The Real Cost: Trust Erosion").

The fix for 200 alerts an hour was not smarter filtering. It was a rate limiter that stopped
floods while the team earned back credibility. The check and the increment are one atomic
DynamoDB operation, so two concurrent alerts cannot both slip under the limit.
"""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

TABLE_NAME = "alert_rate_limits"


def record_alert(table: Any, service_name: str, hour_window: str, limit: int = 3) -> bool:
    """Atomically check and increment the alert count.

    Returns True if the alert is allowed (count < limit), False if rate limited. `table` is a
    boto3 DynamoDB Table resource.

    The book prints ConditionExpression="if_not_exists(alert_count, :zero) + :one <= :limit".
    DynamoDB rejects that: a condition expression cannot do arithmetic or call if_not_exists,
    which only exists in update expressions. The condition below says the same thing in the
    form DynamoDB accepts.
    """
    try:
        table.update_item(
            Key={"service": service_name, "hour": hour_window},
            UpdateExpression="SET alert_count = if_not_exists(alert_count, :zero) + :one",
            ConditionExpression="attribute_not_exists(alert_count) OR alert_count < :limit",
            ExpressionAttributeValues={":zero": 0, ":one": 1, ":limit": limit},
        )
        return True  # Alert allowed
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # Rate limited
        raise


def create_table(dynamodb: Any, table_name: str = TABLE_NAME) -> Any:
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
