import { SNSClient, PublishCommand } from "@aws-sdk/client-sns";
import { readPipelineState } from "../shared/s3-client";
import { PipelineState } from "../shared/types";

const snsClient = new SNSClient({ region: process.env.AWS_REGION ?? "us-east-2" });

const severityIcon = (s: string) => (s === "critical" ? "🔴" : s === "high" ? "🟠" : "🟡");

export const handler = async (input: { executionId: string }): Promise<void> => {
  const topicArn = process.env.HEALER_NOTIFICATION_TOPIC_ARN;

  const state = await readPipelineState<PipelineState>(input.executionId);
  const { event, investigation, fix, prUrl, stageError } = state;

  if (!topicArn) {
    console.warn("[NOTIFY] HEALER_NOTIFICATION_TOPIC_ARN not set — skipping notification");
    return;
  }

  const confidence = investigation?.confidenceScore ?? 0;
  const isFixed = fix?.type === "code-fix";

  const message = [
    `${severityIcon(event.severity)} *Self-Healer — ${isFixed ? "Fix Ready ✅" : "Investigation Report 🔍"}*`,
    `*Service:* ${event.affectedService} | *Severity:* ${event.severity}`,
    `*Issue:* ${event.title}`,
    investigation ? `*Root cause:* ${investigation.rootCauseHypothesis.slice(0, 300)}` : "",
    `*Confidence:* ${confidence}/100`,
    prUrl ? `*PR created:* ${prUrl}` : "*PR creation failed*",
    stageError ? `⚠️ Pipeline error: ${String(stageError).slice(0, 100)}` : "",
  ]
    .filter(Boolean)
    .join("\n");

  const subject = `[Healer] ${event.affectedService} — ${isFixed ? "Fix Ready" : "Investigation"} (${confidence}/100)`;

  // Amazon Q / AWS Chatbot requires MessageStructure:"json" with the
  // {"version":"1.0","source":"custom","content":{"description":"..."}} format
  // on the https protocol key to render as a rich card in Slack.
  const chatbotPayload = JSON.stringify({
    version: "1.0",
    source: "custom",
    content: { description: message },
  });

  try {
    await snsClient.send(new PublishCommand({
      TopicArn: topicArn,
      Subject: subject,
      MessageStructure: "json",
      Message: JSON.stringify({
        default: message,
        email: message,
        https: chatbotPayload,
        http: chatbotPayload,
      }),
    }));
    console.log(`[NOTIFY] Published to SNS (Chatbot format) — execution ${input.executionId}`);
  } catch (err: any) {
    console.error(`[NOTIFY] SNS publish failed: ${err?.message ?? String(err)}`);
  }
};
