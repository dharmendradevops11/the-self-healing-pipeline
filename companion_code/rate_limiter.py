import os
import re
import time
import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Configure production-ready boto3 client configuration
BOTO3_CONFIG = Config(
    connect_timeout=2,       # 2 seconds connection timeout
    read_timeout=3,          # 3 seconds read timeout
    retries={'max_attempts': 2, 'mode': 'standard'}, # Automatic retry handling
    max_pool_connections=50  # Prevent connection starvation in multi-threaded runtime
)

def get_dynamodb_client():
    """Initialize DynamoDB client with custom production configuration safely."""
    return boto3.client(
        'dynamodb',
        region_name=os.environ.get('AWS_REGION', 'us-east-1'),
        config=BOTO3_CONFIG
    )

def current_hour_window() -> str:
    """Return current UTC hour window partition string (e.g. '2026-08-27-16')."""
    return time.strftime("%Y-%m-%d-%H", time.gmtime())

def check_rate_limit(service_name: str, limit: int = 3) -> bool:
    """Check and increment remediation rate limits atomically in DynamoDB.
    
    Args:
        service_name: Name of the service to throttle (alphanumeric boundary check).
        limit: Limit budget per hour window.
    """
    if not service_name or not isinstance(service_name, str) or not re.match(r'^[a-zA-Z0-9-]+$', service_name):
        logger.error("Invalid service name provided for rate limiter validation.")
        return False

    dynamodb = get_dynamodb_client()
    window = current_hour_window()

    try:
        dynamodb.update_item(
            TableName="remediation_rate_limits",
            Key={
                "service": {"S": service_name},
                "window": {"S": window}
            },
            UpdateExpression="ADD attempt_count :incr",
            ConditionExpression="attempt_count < :limit OR attribute_not_exists(attempt_count)",
            ExpressionAttributeValues={
                ":incr": {"N": "1"},
                ":limit": {"N": str(limit)}
            },
        )
        logger.info(f"Rate limit check passed for service: {service_name} inside window: {window}")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(f"Rate limit exceeded (Max: {limit}) for service: {service_name} inside window: {window}")
            return False
        logger.error(f"DynamoDB call failed during rate limit check: {e}", exc_info=True)
        # Fail safe closed: reject action if DynamoDB throws database exceptions
        return False
