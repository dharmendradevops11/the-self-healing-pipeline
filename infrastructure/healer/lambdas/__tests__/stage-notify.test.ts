import { handler } from "../stage-notify/index";
import * as s3Client from "../shared/s3-client";
import { PipelineState } from "../shared/types";

jest.mock("@aws-sdk/client-sns", () => {
  const send = jest.fn().mockResolvedValue({});
  return {
    SNSClient: jest.fn(() => ({ send })),
    PublishCommand: jest.fn((input) => ({ input })),
    __send: send,
  };
});
jest.mock("../shared/s3-client");

// eslint-disable-next-line @typescript-eslint/no-var-requires
const mockSend: jest.Mock = require("@aws-sdk/client-sns").__send;

const state: PipelineState = {
  executionId: "exec-003",
  prUrl: "https://github.com/YOUR-GITHUB-ORG/your-repo/pull/99",
  prNumber: 99,
  event: {
    source: "sentry",
    severity: "critical",
    type: "crash",
    title: "Fatal: unhandled rejection",
    affectedService: "your-api",
    cloudwatchLogGroup: "/ecs/dev-your-api",
    triggeredAt: "2026-05-18T04:00:00Z",
  },
  investigation: {
    rootCauseHypothesis: "Missing null check",
    confidenceScore: 90,
    affectedFiles: ["src/auth/index.ts"],
    fixStrategy: "Add null guard",
    rawBedrockResponse: "",
  },
};

const mockReadState = jest.spyOn(s3Client, "readPipelineState").mockResolvedValue(state);

describe("Stage 6 NOTIFY", () => {
  beforeEach(() => {
    process.env.HEALER_NOTIFICATION_TOPIC_ARN = "arn:aws:sns:us-east-1:111122223333:healer-notifications";
    jest.clearAllMocks();
    mockReadState.mockResolvedValue(state);
  });

  it("publishes a notification containing the PR link", async () => {
    await handler({ executionId: "exec-003" });
    expect(mockSend).toHaveBeenCalledTimes(1);
    const { input } = mockSend.mock.calls[0][0];
    expect(input.TopicArn).toContain("healer-notifications");
    expect(input.Message).toContain("pull/99");
  });

  it("does not throw if SNS publish fails", async () => {
    mockSend.mockRejectedValueOnce(new Error("SNS down"));
    await expect(handler({ executionId: "exec-003" })).resolves.not.toThrow();
  });
});
