import os
import re
import time
import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
BOTO3_CONFIG = Config(
    connect_timeout=2,
    read_timeout=3,
    retries={'max_attempts': 2, 'mode': 'standard'},
    max_pool_connections=50
)

SERVICE_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")

def check_rate_limit(service_name: str, limit: int = 3) -> bool:
    """Check and increment the remediation rate limit atomically in DynamoDB."""
    # Real service names contain hyphens, underscores and dots
    # (checkout-api, payment_service, cart.v2), so a plain isalnum()
    # check would reject almost every service you actually run.
    # Better still: validate against your service registry rather than
    # a regex, since the registry is the authority on what exists.
    if not isinstance(service_name, str) or not SERVICE_NAME_PATTERN.fullmatch(service_name):
        return False
    dynamodb = boto3.client('dynamodb', config=BOTO3_CONFIG)
    try:
        dynamodb.update_item(
            TableName="remediation_rate_limits",
            Key={
                "service": {"S": service_name},
                "window": {"S": time.strftime("%Y-%m-%d-%H", time.gmtime())}
            },
            UpdateExpression="ADD attempt_count :incr",
            ConditionExpression="attempt_count < :limit OR attribute_not_exists(attempt_count)",
            ExpressionAttributeValues={":incr": {"N": "1"}, ":limit": {"N": str(limit)}},
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        logger.error(f"DynamoDB call failed during rate limit check: {e}", exc_info=True)
        return False
