import { S3Client, PutObjectCommand, GetObjectCommand } from "@aws-sdk/client-s3";
import { logReasoningStep } from "../../lambdas/shared/audit";

const client = new S3Client({ region: process.env.AWS_REGION ?? "us-east-2" });
const BUCKET = process.env.HEALER_AUDIT_BUCKET ?? "healer-audit";

export const storeAuditLog = async (
  executionId: string,
  stage: string,
  payload: { prompt?: string; response?: string; metadata?: object; confidence?: number },
): Promise<void> => {
  await logReasoningStep(executionId, {
    stepType: stage,
    input: payload.prompt,
    output: payload.response,
    toolCalls: payload.metadata ? [payload.metadata] : [],
    confidence: payload.confidence,
  });
};

export const writePipelineState = async (state: object): Promise<void> => {
  const s = state as { executionId: string };
  const key = `pipeline-state/${s.executionId}/state.json`;
  await client.send(
    new PutObjectCommand({
      Bucket: BUCKET,
      Key: key,
      Body: JSON.stringify(state),
      ContentType: "application/json",
    }),
  );
};

export const readPipelineState = async <T>(executionId: string): Promise<T> => {
  const key = `pipeline-state/${executionId}/state.json`;
  const response = await client.send(new GetObjectCommand({ Bucket: BUCKET, Key: key }));
  const body = await response.Body!.transformToString();
  return JSON.parse(body) as T;
};
