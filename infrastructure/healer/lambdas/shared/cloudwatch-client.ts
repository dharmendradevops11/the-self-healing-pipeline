import { CloudWatchLogsClient, FilterLogEventsCommand } from "@aws-sdk/client-cloudwatch-logs";
import { CloudWatchLogEntry } from "./types";

const client = new CloudWatchLogsClient({ region: process.env.AWS_REGION ?? "us-east-2" });

export const fetchRecentLogs = async (
  logGroupName: string,
  minutesBack = 30,
  maxEvents = 200,
): Promise<CloudWatchLogEntry[]> => {
  const startTime = Date.now() - minutesBack * 60 * 1000;

  const response = await client.send(
    new FilterLogEventsCommand({
      logGroupName,
      startTime,
      limit: maxEvents,
      filterPattern: "?ERROR ?error ?Error ?WARN ?exception ?Exception",
    }),
  );

  return (response.events ?? []).map((e) => ({
    timestamp: e.timestamp ?? 0,
    message: e.message ?? "",
  }));
};
