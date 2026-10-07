def correlate_deployment_to_metrics(service_name, deployment_time, cloudwatch):
    baseline_start = deployment_time - timedelta(minutes=30)
    baseline_end = deployment_time - timedelta(minutes=5)
    event_start = deployment_time
    event_end = deployment_time + timedelta(minutes=5)

    baseline_errors = get_metric_average(cloudwatch, service_name, 'ErrorRate',
                                         baseline_start, baseline_end)
    event_errors = get_metric_average(cloudwatch, service_name, 'ErrorRate',
                                      event_start, event_end)
    baseline_latency = get_metric_percentile(cloudwatch, service_name, 'Latency',
                                             95, baseline_start, baseline_end)
    event_latency = get_metric_percentile(cloudwatch, service_name, 'Latency',
                                          95, event_start, event_end)

    error_multiplier = event_errors / max(baseline_errors, 0.01)
    latency_multiplier = event_latency / max(baseline_latency, 1)

    return {
        'correlated': error_multiplier > 2.0 or latency_multiplier > 1.5,
        'error_impact': error_multiplier,
        'latency_impact': latency_multiplier,
    }
