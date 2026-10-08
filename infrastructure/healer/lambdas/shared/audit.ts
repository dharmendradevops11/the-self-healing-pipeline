import { S3Client, PutObjectCommand, ListObjectsV2Command } from "@aws-sdk/client-s3";

const client = new S3Client({ region: process.env.AWS_REGION ?? "us-east-2" });

export interface AuditStep {
  stepType: string;
  input?: unknown;
  output?: unknown;
  toolCalls?: unknown[];
  confidence?: number | null;
}

// Step-level audit logging (Chapter 9): one JSON object per reasoning step, partitioned by
// execution under audit/{execution_id}/step_NNN_{type}.json. The step number continues
// across stages by counting what the execution has already written.
export const logReasoningStep = async (executionId: string, step: AuditStep): Promise<void> => {
  const bucket = process.env.HEALER_AUDIT_BUCKET ?? "healer-audit";
  const prefix = `audit/${executionId}/`;

  const listed = await client.send(new ListObjectsV2Command({ Bucket: bucket, Prefix: prefix }));
  const stepNumber = (listed.KeyCount ?? 0) + 1;

  const record = {
    execution_id: executionId,
    step_number: stepNumber,
    timestamp: new Date().toISOString(),
    step_type: step.stepType,
    input: step.input ?? null,
    output: step.output ?? null,
    tool_calls: step.toolCalls ?? [],
    confidence_score: step.confidence ?? null,
  };

  await client.send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: `${prefix}step_${String(stepNumber).padStart(3, "0")}_${step.stepType}.json`,
      Body: JSON.stringify(record, null, 2),
      ContentType: "application/json",
    }),
  );
};
