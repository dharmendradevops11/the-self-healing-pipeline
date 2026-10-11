# Simplified agent loop from the INVESTIGATE stage
def investigate_failure(event):
    stack_trace = event['stackTrace']
    file_paths = extract_files_from_trace(stack_trace)

    source_code = {p: read_file_from_repo(p) for p in file_paths}
    recent_commits = get_commits_for_files(file_paths, days=7)

    context = {
        'error': event['errorMessage'], 'trace': stack_trace,
        'code': source_code, 'changes': recent_commits
    }

    prompt = build_diagnostic_prompt(context)
    response = bedrock.invoke_claude(prompt)
    diagnosis = parse_json_response(response)
    # Returns: rootCauseHypothesis, confidenceScore, affectedFiles, fixStrategy

    write_to_s3(diagnosis)  # State bus for next stage
    return diagnosis
