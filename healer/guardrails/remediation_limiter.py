"""The remediation rate limit (Chapter 7, "Guardrails, Dry-Runs, and Testing Your Automation").

At most `limit` automated remediations per service per hour. Fails closed: if DynamoDB
errors, the answer is "no", never "go ahead".
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = "remediation_rate_limits"

# Real service names contain hyphens, underscores and dots (checkout-api, payment_service,
# cart.v2), so a plain isalnum() check would reject almost every service you actually run.
# Better still: validate against your service registry, which is the authority on what exists.
SERVICE_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")


def check_rate_limit(
    dynamodb: Any, service_name: str, limit: int = 3, now: float | None = None
) -> bool:
    """Check and increment the remediation rate limit atomically. `dynamodb` is a boto3 client."""
    if not isinstance(service_name, str) or not SERVICE_NAME_PATTERN.fullmatch(service_name):
        return False
    try:
        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key={
                "service": {"S": service_name},
                "window": {"S": time.strftime("%Y-%m-%d-%H", time.gmtime(now))},
            },
            UpdateExpression="ADD attempt_count :incr",
            ConditionExpression="attempt_count < :limit OR attribute_not_exists(attempt_count)",
            ExpressionAttributeValues={":incr": {"N": "1"}, ":limit": {"N": str(limit)}},
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        logger.exception("DynamoDB call failed during rate limit check")
        return False  # fail closed


def create_table(dynamodb: Any, table_name: str = TABLE_NAME) -> Any:
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "service", "AttributeType": "S"},
            {"AttributeName": "window", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "service", "KeyType": "HASH"},
            {"AttributeName": "window", "KeyType": "RANGE"},
        ],
    )
