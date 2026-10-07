import { APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";
import { createHmac, timingSafeEqual } from "crypto";
import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";
import { publishHealerEvent } from "../shared/sns-client";
import { checkAndRecordRateLimit } from "../shared/dynamodb-client";
import {
  HealerEvent,
  HealerSeverity,
  HealerIssueType,
  SentryWebhookPayload,
} from "../shared/types";

const smClient = new SecretsManagerClient({ region: process.env.AWS_REGION ?? "us-east-2" });

// Fetch Sentry webhook HMAC secret at invocation time — never stored plaintext in env.
// SENTRY_WEBHOOK_SECRET_ARN (production): ARN fetched from Secrets Manager at runtime.
// SENTRY_WEBHOOK_SECRET (test/dev only): direct value, never set in production CFN.
// Returns empty string if neither is configured; caller must treat that as "reject".
const getSentryWebhookSecret = async (): Promise<string> => {
  if (process.env.SENTRY_WEBHOOK_SECRET) return process.env.SENTRY_WEBHOOK_SECRET;
  const arn = process.env.SENTRY_WEBHOOK_SECRET_ARN;
  if (!arn) return "";
  const { SecretString } = await smClient.send(new GetSecretValueCommand({ SecretId: arn }));
  return SecretString ?? "";
};

const verifySentrySignature = async (body: string, signature: string | undefined): Promise<boolean> => {
  const secret = await getSentryWebhookSecret();
  if (!secret) {
    // Reject all requests when secret is unconfigured — never silently accept.
    console.error("[HEALER] SENTRY_WEBHOOK_SECRET_ARN not set or empty — rejecting request");
    return false;
  }
  if (!signature) return false;
  const expected = createHmac("sha256", secret).update(body, "utf8").digest("hex");
  try {
    return timingSafeEqual(Buffer.from(signature, "hex"), Buffer.from(expected, "hex"));
  } catch {
    return false;
  }
};

const sentryLevelToSeverity = (level: string): HealerSeverity => {
  if (level === "fatal" || level === "critical") return "critical";
  if (level === "error") return "high";
  return "medium";
};

const detectIssueType = (title: string, culprit: string): HealerIssueType => {
  const text = `${title} ${culprit}`.toLowerCase();
  if (text.includes("timeout") || text.includes("latency") || text.includes("slow"))
    return "performance";
  if (text.includes("error") || text.includes("exception") || text.includes("crash"))
    return "integration";
  return "crash";
};

const extractService = (projectSlug: string, culprit: string): string => {
  // Map your project slug to your service name:
  // if (projectSlug.includes("api")) return "your-api-service";
  // Customize: map culprit strings to your service names
  // e.g.: if (culprit.includes("admin")) return "admin-service";
  return projectSlug;
};

const serviceToLogGroup = (service: string): string => {
  const env = process.env.ENVIRONMENT ?? "dev";
  // TODO: Add your service → CloudWatch log group mappings here.
  // By default returns /ecs/{env}-{service} which works for most ECS setups.
  // Example: const map: Record<string, string> = {
  //   "my-api": `/ecs/${env}-my-api`,
  //   "my-worker": `/aws/lambda/${env}-my-worker`,
  // };
  return `/ecs/${env}-${service}`;
};

export const handler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const rawBody = event.body ?? "";
  const signature =
    event.headers["sentry-hook-signature"] ?? event.headers["Sentry-Hook-Signature"];

  if (!await verifySentrySignature(rawBody, signature)) {
    console.warn("[HEALER] Rejected request with invalid Sentry signature");
    return { statusCode: 401, body: JSON.stringify({ error: "Invalid signature" }) };
  }

  let payload: SentryWebhookPayload;
  try {
    payload = JSON.parse(rawBody || "{}") as SentryWebhookPayload;
    if (!payload?.data?.issue?.title) throw new Error("Missing issue title");
  } catch {
    return { statusCode: 400, body: JSON.stringify({ error: "Invalid Sentry payload" }) };
  }

  const issue = payload.data.issue;
  const service = extractService(issue.project.slug, issue.culprit);

  const rateCheck = await checkAndRecordRateLimit(service);
  if (!rateCheck.allowed) {
    return { statusCode: 429, body: JSON.stringify({ error: "Rate limit exceeded", service }) };
  }

  const healerEvent: HealerEvent = {
    source: "sentry",
    severity: sentryLevelToSeverity(issue.level),
    type: detectIssueType(issue.title, issue.culprit),
    title: issue.title,
    stackTrace: issue.metadata?.value,
    affectedService: service,
    cloudwatchLogGroup: serviceToLogGroup(service),
    sentryIssueUrl: issue.permalink,
    triggeredAt: new Date().toISOString(),
  };

  await publishHealerEvent(healerEvent);

  return {
    statusCode: 200,
    body: JSON.stringify({ ok: true, service, severity: healerEvent.severity }),
  };
};
