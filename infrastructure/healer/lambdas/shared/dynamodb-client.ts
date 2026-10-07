import { DynamoDBClient, ConditionalCheckFailedException } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";

const client = DynamoDBDocumentClient.from(
  new DynamoDBClient({ region: process.env.AWS_REGION ?? "us-east-2" }),
);

const TABLE = process.env.RATE_LIMIT_TABLE ?? "healer-rate-limit";
const MAX_PER_HOUR = 3;

// Atomic increment with conditional expression — prevents TOCTOU race where
// two concurrent executions both read count=0, both pass the check, and both
// write count=1. UpdateCommand with ConditionExpression is a single atomic op.
export const checkAndRecordRateLimit = async (
  affectedService: string,
): Promise<{ allowed: boolean; count: number }> => {
  const windowStart = Math.floor(Date.now() / 3_600_000);
  const pk = `${affectedService}#${windowStart}`;
  const ttl = Math.floor(Date.now() / 1000) + 7200;

  try {
    const result = await client.send(
      new UpdateCommand({
        TableName: TABLE,
        Key: { pk },
        UpdateExpression: "SET #count = if_not_exists(#count, :zero) + :one, #ttl = :ttl",
        ConditionExpression: "attribute_not_exists(#count) OR #count < :max",
        ExpressionAttributeNames: { "#count": "count", "#ttl": "ttl" },
        ExpressionAttributeValues: { ":zero": 0, ":one": 1, ":max": MAX_PER_HOUR, ":ttl": ttl },
        ReturnValues: "ALL_NEW",
      }),
    );
    const count = (result.Attributes?.count ?? 1) as number;
    return { allowed: true, count };
  } catch (err) {
    if (err instanceof ConditionalCheckFailedException) {
      return { allowed: false, count: MAX_PER_HOUR };
    }
    throw err;
  }
};
