import { handler } from "../stage-pr/index";
import * as githubClient from "../shared/github-client";
import * as s3Client from "../shared/s3-client";
import { PipelineState } from "../shared/types";

jest.mock("@octokit/rest", () => ({
  Octokit: jest.fn().mockImplementation(() => ({
    git: { createRef: jest.fn().mockResolvedValue({}) },
    pulls: { create: jest.fn().mockResolvedValue({ data: { number: 1, html_url: "" } }) },
    issues: { addLabels: jest.fn().mockResolvedValue({}) },
  })),
}));
jest.mock("../shared/github-client");
jest.mock("../shared/s3-client");

const mockCreatePR = jest.spyOn(githubClient, "createHealerPR").mockResolvedValue({
  prUrl: "https://github.com/YOUR-GITHUB-ORG/your-repo/pull/99",
  prNumber: 99,
});

const state: PipelineState = {
  executionId: "exec-002",
  event: {
    source: "sentry",
    severity: "high",
    type: "crash",
    title: "RangeError: Maximum call stack",
    affectedService: "your-api",
    cloudwatchLogGroup: "/ecs/dev-your-api",
    triggeredAt: "2026-05-18T04:00:00Z",
  },
};

const mockReadState = jest.spyOn(s3Client, "readPipelineState").mockResolvedValue(state);
const mockWriteState = jest.spyOn(s3Client, "writePipelineState").mockResolvedValue();

describe("Stage 5 PR", () => {
  beforeEach(() => jest.clearAllMocks());

  it("creates a PR and writes updated state to S3, returns executionId", async () => {
    mockReadState.mockResolvedValueOnce(state);
    mockWriteState.mockResolvedValue();
    mockCreatePR.mockResolvedValueOnce({
      prUrl: "https://github.com/YOUR-GITHUB-ORG/your-repo/pull/99",
      prNumber: 99,
    });

    const result = await handler({ executionId: "exec-002" });
    expect(result.executionId).toBe("exec-002");
    expect(mockWriteState).toHaveBeenCalledWith(
      expect.objectContaining({
        prUrl: "https://github.com/YOUR-GITHUB-ORG/your-repo/pull/99",
        prNumber: 99,
      }),
    );
  });

  it("records stageError in S3 if PR creation fails but does not throw", async () => {
    mockReadState.mockResolvedValueOnce(state);
    mockWriteState.mockResolvedValue();
    mockCreatePR.mockRejectedValueOnce(new Error("GitHub rate limit"));

    const result = await handler({ executionId: "exec-002" });
    expect(result.executionId).toBe("exec-002");
    expect(mockWriteState).toHaveBeenCalledWith(
      expect.objectContaining({
        stageError: expect.stringContaining("GitHub rate limit"),
        failedStage: "PR",
      }),
    );
  });
});
