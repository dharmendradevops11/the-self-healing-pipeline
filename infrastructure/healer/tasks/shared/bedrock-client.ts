import { BedrockRuntimeClient, InvokeModelCommand } from "@aws-sdk/client-bedrock-runtime";

const client = new BedrockRuntimeClient({ region: process.env.BEDROCK_REGION ?? "us-east-2" });
const MODEL_ID = process.env.BEDROCK_MODEL_ID ?? "us.anthropic.claude-3-5-sonnet-20241022-v2:0";

export const invokeClaudeJson = async <T>(
  systemPrompt: string,
  userPrompt: string,
): Promise<{ parsed: T; raw: string; tokens: { input: number; output: number } }> => {
  const body = {
    anthropic_version: "bedrock-2023-05-31",
    max_tokens: 8192,
    system: systemPrompt,
    messages: [{ role: "user", content: userPrompt }],
  };

  const response = await client.send(
    new InvokeModelCommand({
      modelId: MODEL_ID,
      body: JSON.stringify(body),
      contentType: "application/json",
      accept: "application/json",
    }),
  );

  const result = JSON.parse(new TextDecoder().decode(response.body));
  const raw: string = result.content[0].text;

  const jsonMatch = raw.match(/```json\n([\s\S]+?)\n```/) ?? raw.match(/(\{[\s\S]+\})/);
  const jsonStr = jsonMatch ? (jsonMatch[1] ?? jsonMatch[0]) : raw;
  const parsed = JSON.parse(jsonStr) as T;

  return {
    parsed,
    raw,
    tokens: {
      input: result.usage?.input_tokens ?? 0,
      output: result.usage?.output_tokens ?? 0,
    },
  };
};
