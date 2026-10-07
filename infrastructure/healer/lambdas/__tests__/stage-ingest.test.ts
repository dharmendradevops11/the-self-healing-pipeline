import { handler } from "../stage-ingest/index";
import * as cwClient from "../shared/cloudwatch-client";
import * as sentryClient from "../shared/sentry-client";
import * as s3Client from "../shared/s3-client";
import { PipelineState } from "../shared/types";

jest.mock("../shared/cloudwatch-client");
jest.mock("../shared/sentry-client");
jest.mock("../shared/s3-client");

const mockFetchLogs = jest
  .spyOn(cwClient, "fetchRecentLogs")
  .mockResolvedValue([{ timestamp: Date.now(), message: "ERROR: something broke" }]);
const mockSentryCount = jest.spyOn(sentryClient, "getSentryIssueCount").mockResolvedValue(47);
const mockWriteState = jest.spyOn(s3Client, "writePipelineState").mockResolvedValue();

const baseState: PipelineState = {
  executionId: "exec-001",
  event: {
    source: "sentry",
    severity: "critical",
    type: "crash",
    title: "TypeError in auth",
    affectedService: "your-api",
    cloudwatchLogGroup: "/ecs/dev-your-api",
    triggeredAt: "2026-05-18T03:00:00Z",
    sentryIssueUrl: "https://sentry.io/issues/123/",
  },
};

describe("Stage 1 INGEST", () => {
  beforeEach(() => jest.clearAllMocks());

  it("enriches the event with CloudWatch logs and Sentry count, writes to S3, returns executionId", async () => {
    const result = await handler(baseState);
    expect(result.executionId).toBe("exec-001");
    expect(mockFetchLogs).toHaveBeenCalledWith("/ecs/dev-your-api", 30, 200);
    expect(mockWriteState).toHaveBeenCalledWith(
      expect.objectContaining({
        executionId: "exec-001",
        enriched: expect.objectContaining({
          cloudwatchLogs: expect.arrayContaining([
            expect.objectContaining({ message: "ERROR: something broke" }),
          ]),
          sentryEventCount: 47,
        }),
      }),
    );
  });

  it("continues even if Sentry fetch fails", async () => {
    mockSentryCount.mockRejectedValueOnce(new Error("Sentry unreachable"));
    const result = await handler(baseState);
    expect(result.executionId).toBe("exec-001");
    // writePipelineState called with sentryEventCount 0
    expect(mockWriteState).toHaveBeenCalledWith(
      expect.objectContaining({
        enriched: expect.objectContaining({ sentryEventCount: 0 }),
      }),
    );
  });
});
