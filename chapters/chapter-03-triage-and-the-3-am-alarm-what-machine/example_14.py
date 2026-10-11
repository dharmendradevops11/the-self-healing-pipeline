def should_alert(anomaly, context):
    """Suppress alerts during known change windows."""
    if context.deployment_in_progress:
        if anomaly.start_time < context.deployment_time + timedelta(minutes=15):
            return False

    if anomaly.metric in ['request_count', 'active_users']:
        if context.is_business_hours and anomaly.magnitude < 3.0:
            return False

    similar = find_historical_anomalies(
        anomaly.metric,
        anomaly.pattern,
        lookback_days=30
    )
    if len(similar) > 5 and all(not a.caused_incident for a in similar):
        return False

    return True
