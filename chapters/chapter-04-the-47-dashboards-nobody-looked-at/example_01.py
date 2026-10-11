def fetch_relevant_logs(log_group: str, task_arn: str, failure_time: int) -> str:
    """Fetch the minimal log context needed for diagnosis."""
    cloudwatch = boto3.client('logs')

    # Get logs from 2 minutes before failure to failure time
    start_time = (failure_time - 120) * 1000
    end_time = failure_time * 1000

    response = cloudwatch.filter_log_events(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        limit=100  # Bounded — we don't need the entire history
    )

    return "\n".join(
        f"[{e['timestamp']}] {e['message']}" for e in response['events']
    )
