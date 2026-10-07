def detect_memory_anomaly(service_name, lookback_hours=24):
    """Scan CloudWatch for abnormal memory patterns."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=lookback_hours)

    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/ECS', MetricName='MemoryUtilization',
        Dimensions=[{'Name': 'ServiceName', 'Value': service_name}],
        StartTime=start_time, EndTime=end_time,
        Period=300, Statistics=['Average', 'Maximum']
    )
    datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])

    # Rate of change over 2-hour (24-datapoint) windows
    growth_rates = []
    for i in range(len(datapoints) - 24):
        start_mem, end_mem = datapoints[i]['Average'], datapoints[i + 24]['Average']
        growth_rates.append({
            'timestamp': datapoints[i + 24]['Timestamp'],
            'growth_rate': (end_mem - start_mem) / start_mem,
            'absolute_memory': end_mem
        })

    current_memory = datapoints[-1]['Average']
    suspicious_growth = [g for g in growth_rates if g['growth_rate'] > 0.3]

    return {
        'is_anomalous': len(suspicious_growth) > 0 and current_memory > 70,
        'current_memory_pct': current_memory,
        'growth_periods': suspicious_growth
    }
