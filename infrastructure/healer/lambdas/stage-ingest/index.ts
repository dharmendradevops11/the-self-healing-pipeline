import { fetchRecentLogs } from "../shared/cloudwatch-client";
import { getSentryIssueCount } from "../shared/sentry-client";
import { writePipelineState } from "../shared/s3-client";
import { PipelineState, EnrichedHealerEvent } from "../shared/types";

export const handler = async (state: PipelineState): Promise<{ executionId: string }> => {
  const { event } = state;

  const [cloudwatchLogs, sentryEventCount] = await Promise.allSettled([
    fetchRecentLogs(event.cloudwatchLogGroup, 30, 200),
    event.sentryIssueUrl ? getSentryIssueCount(event.sentryIssueUrl) : Promise.resolve(0),
  ]);

  const enriched: EnrichedHealerEvent = {
    ...event,
    cloudwatchLogs: cloudwatchLogs.status === "fulfilled" ? cloudwatchLogs.value : [],
    sentryEventCount: sentryEventCount.status === "fulfilled" ? sentryEventCount.value : 0,
    lastDeployAt: process.env.LAST_DEPLOY_AT,
  };

  const updated: PipelineState = { ...state, enriched };

  // Write state to S3 so Fargate tasks can read it
  await writePipelineState(updated);

  // Return only executionId — downstream stages read full state from S3
  return { executionId: updated.executionId };
};
