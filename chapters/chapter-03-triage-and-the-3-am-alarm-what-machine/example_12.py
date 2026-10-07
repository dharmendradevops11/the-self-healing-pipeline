def analyze_build_failure(log_excerpt, build_context):
    prompt = f"""You are analyzing a CI/CD build failure.

Build context:
- Project: {build_context['project']}
- Branch: {build_context['branch']}
- Last successful build: {build_context['last_success']}

Build log excerpt:
{log_excerpt}

Return a JSON object with:
- rootCauseHypothesis: your best guess at what failed
- confidenceScore: 0-100 integer
- affectedFiles: list of files likely involved
- fixStrategy: concrete next steps

Be specific. Reference actual error messages. If confidence is low, say why."""

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,  # from config; see Chapter 2 on model lifecycle
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0
        })
    )
    result = json.loads(response['body'].read())
    return json.loads(result['content'][0]['text'])
