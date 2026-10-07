def calculate_deployment_risk(deployment_metadata):
    """Calculate risk score from 0-100 based on deployment context"""
    risk_score = 0
    deploy_time = deployment_metadata['timestamp']

    # Time-based risk
    if deploy_time.weekday() == 4 and deploy_time.hour >= 15:  # Friday afternoon
        risk_score += 25
    elif deploy_time.weekday() in [5, 6]:                      # Weekend
        risk_score += 35
    elif deploy_time.hour < 6 or deploy_time.hour > 22:        # Off-hours
        risk_score += 15

    # Change size risk
    lines_changed = (deployment_metadata['diff_stats']['additions']
                     + deployment_metadata['diff_stats']['deletions'])
    if lines_changed > 2000:
        risk_score += 20
    elif lines_changed > 500:
        risk_score += 10

    # Files changed risk
    files_changed = len(deployment_metadata['files_modified'])
    if files_changed > 50:
        risk_score += 15
    elif files_changed > 20:
        risk_score += 8

    # Time since last successful deploy
    hours_since_last = (deploy_time -
        deployment_metadata['last_success']).total_seconds() / 3600
    if hours_since_last > 72:
        risk_score += 20
    elif hours_since_last < 2:       # rapid deployments increase risk too
        risk_score += 10

    # Recent deployment density across the cluster
    if deployment_metadata['cluster_deploy_count_24h'] > 10:
        risk_score += 15

    return min(risk_score, 100)
