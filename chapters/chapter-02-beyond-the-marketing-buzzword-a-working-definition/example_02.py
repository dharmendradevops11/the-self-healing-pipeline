INVESTIGATION_PROMPT = """You are investigating a production error.

Error: {error_message}
Stack trace: {stack_trace}
Last 20 CloudWatch log lines: {log_context}
Recent deployment: {recent_deployment}
Recent commits touching these files: {commit_context}
Relevant metric history: {metric_context}
Dependency changes since last green build: {dependency_context}
Files read from repository: {file_contents}

Return JSON with exactly these fields:
- rootCauseHypothesis: string, specific to file/line where possible
- confidenceScore: integer 0-100
- evidenceSummary: string, what in the logs/code supports this
- affectedFiles: array of file paths
"""

import os

# Never hardcode this. Bedrock models have published end-of-life dates;
# keep the identifier in configuration so a retirement is a config change.
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-sonnet-4-20250514-v1:0",  # tested against this edition
)

def diagnose(error_event: dict, log_context: str, file_contents: dict,
             enrichment: dict) -> dict:
    """
    enrichment carries the context the INVESTIGATE stage gathered beyond the
    raw error: the deploy that preceded it, commits touching the implicated
    files, recent metric history, and dependency deltas since the last green
    build. Everything reaching the prompt is sanitized first; enrichment is
    assembled from AWS and GitHub APIs rather than from the alert payload,
    but it can still quote text an attacker controls.
    """
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": INVESTIGATION_PROMPT.format(
                    error_message=sanitize_for_prompt(error_event["message"]),
                    stack_trace=sanitize_for_prompt(error_event["stack_trace"]),
                    log_context=sanitize_for_prompt(log_context),
                    recent_deployment=enrichment["recent_deployment"],
                    commit_context=sanitize_for_prompt(enrichment["commits"]),
                    metric_context=enrichment["metrics"],
                    dependency_context=enrichment["dependency_changes"],
                    file_contents=file_contents,
                ),
            }],
        }),
    )
    return json.loads(response["body"].read())["content"][0]["text"]
