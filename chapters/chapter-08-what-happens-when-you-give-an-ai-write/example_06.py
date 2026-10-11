def correlate_memory_with_activity(service_name, anomaly_data):
    """Find what's happening when memory grows."""
    hypotheses = []
    for period in anomaly_data['growth_periods']:
        window_start = period['timestamp'] - timedelta(minutes=30)
        window_end = period['timestamp'] + timedelta(minutes=30)

        log_query = f"""
        fields @timestamp, @message
        | filter @message like /error/ or @message like /exception/
        | sort @timestamp desc
        | limit 50
        """
        logs = execute_cloudwatch_query(service_name, log_query, window_start, window_end)
        commits = get_recent_commits(service_name, window_start)
        hypotheses.append({
            "timestamp": period['timestamp'],
            "logs": logs,
            "commits": commits
        })
    return hypotheses
