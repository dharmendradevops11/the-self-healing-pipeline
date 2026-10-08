import { SNSClient, PublishCommand } from "@aws-sdk/client-sns";
import { readPipelineState } from "../shared/s3-client";
import { PipelineState } from "../shared/types";

const snsClient = new SNSClient({ region: process.env.AWS_REGION ?? "us-east-2" });

const severityIcon = (s: string) => (s === "critical" ? "🔴" : s === "high" ? "🟠" : "🟡");

// Escalation tiers from the Chapter 9 matrix.
const TIER_LABEL: Record<string, string> = { informational: "INFO", warning: "WARNING", critical: "CRITICAL" };
const TIER_ICON: Record<string, string> = { informational: "🟢", warning: "🟠", critical: "🔴" };

export const handler = async (input: { executionId: string }): Promise<void> => {
  const topicArn = process.env.HEALER_NOTIFICATION_TOPIC_ARN;

  const state = await readPipelineState<PipelineState>(input.executionId);
  const { event, investigation, fix, prUrl, stageError, decision } = state;

  if (!topicArn) {
    console.warn("[NOTIFY] HEALER_NOTIFICATION_TOPIC_ARN not set — skipping notification");
    return;
  }

  const confidence = investigation?.confidenceScore ?? 0;
  const isFixed = fix?.type === "code-fix";

  const tier = decision?.tier;
  const message = [
    `${tier ? TIER_ICON[tier] : severityIcon(event.severity)} *Self-Healer — ${isFixed ? "Fix Ready ✅" : "Investigation Report 🔍"}*`,
    decision
      ? `*Escalation:* ${TIER_LABEL[decision.tier]} → ${decision.recipient} via ${decision.channel} (page: ${decision.page === false ? "no" : decision.page})`
      : "",
    decision
      ? `*Routing:* ${decision.band} confidence × ${decision.blastRadius.tier} blast radius → ${decision.fixAction}`
      : "",
    `*Service:* ${event.affectedService} | *Severity:* ${event.severity}`,
    `*Issue:* ${event.title}`,
    investigation ? `*Root cause:* ${investigation.rootCauseHypothesis.slice(0, 300)}` : "",
    `*Confidence:* ${confidence}/100`,
    prUrl ? `*PR created:* ${prUrl}` : "*PR creation failed*",
    stageError ? `⚠️ Pipeline error: ${String(stageError).slice(0, 100)}` : "",
  ]
    .filter(Boolean)
    .join("\n");

  const subject = `${tier ? `[${TIER_LABEL[tier]}] ` : ""}[Healer] ${event.affectedService} — ${isFixed ? "Fix Ready" : "Investigation"} (${confidence}/100)`;

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
      Subject: subject.slice(0, 100),
      MessageStructure: "json",
      // Subscribers filter on these, for example to page only when page = "always".
      MessageAttributes: {
        escalationTier: { DataType: "String", StringValue: tier ?? "unknown" },
        page: { DataType: "String", StringValue: String(decision?.page ?? false) },
        channel: { DataType: "String", StringValue: decision?.channel ?? "slack" },
        fixAction: { DataType: "String", StringValue: decision?.fixAction ?? "unknown" },
      },
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
