def get_relevant_logs(service_name, failure_timestamp):
    log_group = f"/aws/ecs/{service_name}"

    # Start 2 minutes before failure, end 1 minute after
    start_time = failure_timestamp - timedelta(minutes=2)
    end_time = failure_timestamp + timedelta(minutes=1)

    # Fetch only ERROR and FATAL level logs
    filter_pattern = '[level=ERROR || level=FATAL]'

    logs_client = boto3.client('logs')
    response = logs_client.filter_log_events(
        logGroupName=log_group,
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000),
        filterPattern=filter_pattern,
        limit=100  # Cap it — we don't need the entire crash dump
    )

    return [event['message'] for event in response['events']]
