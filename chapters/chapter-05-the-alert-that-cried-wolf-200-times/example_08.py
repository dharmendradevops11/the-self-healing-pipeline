import boto3
from datetime import datetime, timedelta

devops_guru = boto3.client('devopsguru')

def fetch_and_filter_insights():
    """Get recent insights and filter out known noise patterns."""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)

    response = devops_guru.list_insights(
        StatusFilter={
            'Ongoing': {'Type': 'REACTIVE'},
            'Closed': {'Type': 'REACTIVE'}
        },
        MaxResults=100
    )

    actionable_insights = []
    for insight in response['ReactiveInsights']:
        severity = insight.get('Severity', 'LOW')
        resource_collection = insight.get('ResourceCollection', {})

        # Ignore LOW severity unless it touches a resource we've tagged critical
        if severity == 'LOW' and not is_critical_resource(resource_collection):
            continue
        actionable_insights.append(insight)

    return actionable_insights
