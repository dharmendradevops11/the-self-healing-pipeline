import axios from "axios";
import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";

const SENTRY_API = "https://sentry.io/api/0";
const smClient = new SecretsManagerClient({ region: process.env.AWS_REGION ?? "us-east-2" });

let cachedSentryToken: string | null = null;

const getSentryToken = async (): Promise<string> => {
  if (cachedSentryToken !== null) return cachedSentryToken;
  const arn = process.env.SENTRY_AUTH_TOKEN_SECRET_ARN;
  if (arn) {
    const { SecretString } = await smClient.send(new GetSecretValueCommand({ SecretId: arn }));
    cachedSentryToken = SecretString ?? "";
  } else {
    cachedSentryToken = "";
  }
  return cachedSentryToken;
};

export interface SentryEvent {
  id: string;
  message: string;
  dateCreated: string;
}

export const getSentryIssueCount = async (issueUrl: string): Promise<number> => {
  const token = await getSentryToken();
  if (!issueUrl || !token) return 0;
  try {
    const issueId = issueUrl.split("/issues/")[1]?.replace("/", "");
    if (!issueId) return 0;
    const response = await axios.get<SentryEvent[]>(
      `${SENTRY_API}/issues/${issueId}/events/?limit=100`,
      {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 10_000,
      },
    );
    return response.data.length;
  } catch {
    return 0;
  }
};
