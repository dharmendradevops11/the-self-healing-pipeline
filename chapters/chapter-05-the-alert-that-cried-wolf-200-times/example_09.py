def record_alert_feedback(alert_id: str, service_name: str, error_type: str,
                          was_false_positive: bool, investigated_by: str):
    """Record whether an alert was legitimate or noise."""
    dynamodb.put_item(TableName='alert_feedback', Item={
        'alert_id': {'S': alert_id},
        'service_name': {'S': service_name},
        'error_type': {'S': error_type},
        'false_positive': {'BOOL': was_false_positive},
        'investigated_by': {'S': investigated_by},
        'timestamp': {'N': str(int(datetime.now().timestamp()))}
    })

def get_false_positive_rate(service_name: str, error_type: str, days: int = 7) -> float:
    """Calculate FP rate for a specific alert type over a rolling window."""
    cutoff = int(datetime.now().timestamp() - (days * 86400))
    response = dynamodb.query(
        TableName='alert_feedback', IndexName='service_error_index',
        KeyConditionExpression='service_name = :svc AND error_type = :err',
        FilterExpression='#ts > :cutoff',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ExpressionAttributeValues={':svc': {'S': service_name},
                                   ':err': {'S': error_type},
                                   ':cutoff': {'N': str(cutoff)}}
    )
    items = response.get('Items', [])
    if not items:
        return 0.0
    false_positives = sum(1 for item in items if item['false_positive']['BOOL'])
    return false_positives / len(items)
