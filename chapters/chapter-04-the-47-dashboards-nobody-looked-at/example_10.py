def calculate_pipeline_health_score(service_name, region='us-east-1'):
    """0-100 score. <70: investigate. <50: roll back."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=5)

    error_rate = get_metric_average(cloudwatch, service_name, 'ErrorRate', start_time, end_time)
    error_score = max(0, 100 - (error_rate * 200))

    p95_latency = get_metric_percentile(cloudwatch, service_name, 'Latency', 95,
                                        start_time, end_time)
    latency_score = max(0, 100 - ((p95_latency - 200) / 10))

    cpu = get_metric_average(cloudwatch, service_name, 'CPUUtilization', start_time, end_time)
    memory = get_metric_average(cloudwatch, service_name, 'MemoryUtilization',
                                start_time, end_time)
    resource_score = 100 - max(cpu, memory)

    return round(error_score * 0.4 + latency_score * 0.3 + resource_score * 0.2, 1)
