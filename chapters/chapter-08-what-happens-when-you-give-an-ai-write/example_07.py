def investigate_failure(failure_event):
    # Cheap, fast signal first
    stack_trace = extract_stack_trace(failure_event['log_stream'])
    affected_files = parse_file_paths_from_trace(stack_trace)

    # Targeted read of just the implicated files
    source_context = {}
    for file_path in affected_files[:5]:
        content = s3.get_object(
            Bucket=config['repo_bucket'],
            Key=f"repos/{failure_event['repo']}/{file_path}"
        )['Body'].read().decode('utf-8')
        source_context[file_path] = content

    recent_changes = get_git_history(
        repo=failure_event['repo'], file_paths=affected_files,
        since=failure_event['timestamp'] - timedelta(days=7)
    )

    # Only pay for metrics if the source hints at a resource issue
    metrics_context = None
    if contains_resource_keywords(source_context):
        metrics_context = get_cloudwatch_metrics(
            namespace='AWS/ECS', metrics=['CPUUtilization', 'MemoryUtilization'],
            start=failure_event['timestamp'] - timedelta(hours=2),
            end=failure_event['timestamp']
        )

    return call_llm_with_context(
        stack_trace, source_context, recent_changes, metrics_context
    )
