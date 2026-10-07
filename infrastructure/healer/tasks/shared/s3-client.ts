import { S3Client, PutObjectCommand, GetObjectCommand } from "@aws-sdk/client-s3";

const client = new S3Client({ region: process.env.AWS_REGION ?? "us-east-2" });
const BUCKET = process.env.HEALER_AUDIT_BUCKET ?? "healer-audit";

export const storeAuditLog = async (
  executionId: string,
  stage: string,
  payload: { prompt?: string; response?: string; metadata?: object },
): Promise<void> => {
  const date = new Date().toISOString().slice(0, 10);
  const key = `${date}/${executionId}/${stage}.json`;

  await client.send(
    new PutObjectCommand({
      Bucket: BUCKET,
      Key: key,
      Body: JSON.stringify({ ...payload, storedAt: new Date().toISOString() }),
      ContentType: "application/json",
    }),
  );
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
