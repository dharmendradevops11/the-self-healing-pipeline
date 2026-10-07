import boto3
from botocore.exceptions import ClientError

table = boto3.resource("dynamodb").Table("investigation_rate_limits")

def try_acquire_investigation_slot(service_name: str, hour_bucket: str, limit: int = 3) -> bool:
    """Atomically check-and-increment a per-service, per-hour counter.
    Returns True if this event is allowed to trigger an investigation."""
    try:
        table.update_item(
            Key={"service": service_name, "hour": hour_bucket},
            UpdateExpression="ADD invocation_count :inc",
            ConditionExpression="attribute_not_exists(invocation_count) OR invocation_count < :limit",
            ExpressionAttributeValues={":inc": 1, ":limit": limit},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # rate limit hit, drop the event
        raise
