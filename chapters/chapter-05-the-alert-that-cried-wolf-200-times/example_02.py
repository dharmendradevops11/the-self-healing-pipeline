def record_alert(service_name: str, hour_window: str) -> bool:
    """
    Atomically check and increment alert count.
    Returns True if alert is allowed (count < 3), False if rate limited.
    """
    try:
        table.update_item(
            Key={'service': service_name, 'hour': hour_window},
            UpdateExpression='SET alert_count = if_not_exists(alert_count, :zero) + :one',
            ConditionExpression='if_not_exists(alert_count, :zero) + :one <= :limit',
            ExpressionAttributeValues={':zero': 0, ':one': 1, ':limit': 3}
        )
        return True  # Alert allowed
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False  # Rate limited
        raise
