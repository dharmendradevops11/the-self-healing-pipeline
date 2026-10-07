import { SNSClient, PublishCommand } from "@aws-sdk/client-sns";
import { HealerEvent } from "./types";

const client = new SNSClient({ region: process.env.AWS_REGION ?? "us-east-2" });

export const publishHealerEvent = async (event: HealerEvent): Promise<void> => {
  const topicArn = process.env.HEALER_SNS_TOPIC_ARN;
  if (!topicArn) throw new Error("HEALER_SNS_TOPIC_ARN not set");

  await client.send(
    new PublishCommand({
      TopicArn: topicArn,
      Message: JSON.stringify(event),
      Subject: `[HEALER] ${event.severity.toUpperCase()} — ${event.title.slice(0, 100)}`,
      MessageAttributes: {
        severity: { DataType: "String", StringValue: event.severity },
        type: { DataType: "String", StringValue: event.type },
        affectedService: { DataType: "String", StringValue: event.affectedService },
      },
    }),
  );
};
