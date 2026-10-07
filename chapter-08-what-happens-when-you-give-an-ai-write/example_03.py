class AgentExecutor:
    def __init__(self, bedrock_client, s3_client, tool_registry):
        self.bedrock = bedrock_client
        self.s3 = s3_client
        self.tools = tool_registry

    def execute(self, state_key: str) -> dict:
        context = self.s3.get_object(
            Bucket='pipeline-agent-state', Key=f'{state_key}/context.json'
        )
        prompt = self._build_prompt(context, self.tools.describe())

        response = self.bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 4096,
                'messages': [{'role': 'user', 'content': prompt}],
                'tools': self.tools.as_bedrock_schema()
            })
        )

        result = self._execute_tool_calls(response)
        self.s3.put_object(
            Bucket='pipeline-agent-state', Key=f'{state_key}/result.json',
            Body=json.dumps(result)
        )
        return result
