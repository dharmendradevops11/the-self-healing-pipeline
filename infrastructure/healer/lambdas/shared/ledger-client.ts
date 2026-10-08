import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, PutCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { successRateFromVerdicts } from "./decision";

const client = DynamoDBDocumentClient.from(
  new DynamoDBClient({ region: process.env.AWS_REGION ?? "us-east-2" }),
  { marshallOptions: { removeUndefinedValues: true } },
);

const TABLE = () => process.env.HEALER_TRUST_LEDGER_TABLE ?? "agent-trust-ledger";
const CATEGORY_INDEX = "category-timestamp-index";
const ROLLING_WINDOW = 50;

export type HumanVerdict = "pending" | "approved" | "rejected" | "modified";

// Trust ledger (Chapter 9): one row per execution, so accuracy can be measured against
// what human reviewers actually decided. human_verdict starts as "pending" and is updated
// when a reviewer approves, rejects or modifies the pull request.
export const recordOutcome = async (o: {
  executionId: string;
  hypothesis: string;
  confidence: number;
  humanVerdict: HumanVerdict;
  fixWorked: boolean | null;
  category?: string;
}): Promise<void> => {
  await client.send(
    new PutCommand({
      TableName: TABLE(),
      Item: {
        execution_id: o.executionId,
        hypothesis: o.hypothesis,
        confidence_score: o.confidence,
        human_verdict: o.humanVerdict,
        fix_worked: o.fixWorked,
        category: o.category ?? "unknown",
        timestamp: new Date().toISOString(),
      },
    }),
  );
};

export const updateVerdict = async (
  executionId: string,
  humanVerdict: HumanVerdict,
  fixWorked?: boolean,
): Promise<void> => {
  await client.send(
    new UpdateCommand({
      TableName: TABLE(),
      Key: { execution_id: executionId },
      UpdateExpression: "SET human_verdict = :v, fix_worked = :w",
      ExpressionAttributeValues: { ":v": humanVerdict, ":w": fixWorked ?? null },
      ConditionExpression: "attribute_exists(execution_id)",
    }),
  );
};

// Rolling accuracy for a failure category, or null when there is too little history.
// Fails soft: a ledger outage must not stop an investigation, it just removes the history input.
export const getHistoricalSuccessRate = async (category: string): Promise<number | null> => {
  try {
    const res = await client.send(
      new QueryCommand({
        TableName: TABLE(),
        IndexName: CATEGORY_INDEX,
        KeyConditionExpression: "category = :c",
        ExpressionAttributeValues: { ":c": category },
        ScanIndexForward: false,
        Limit: ROLLING_WINDOW,
      }),
    );
    return successRateFromVerdicts((res.Items ?? []).map((i) => String(i.human_verdict)));
  } catch (err) {
    console.warn(`[LEDGER] History lookup failed for ${category}: ${String(err)}`);
    return null;
  }
};
