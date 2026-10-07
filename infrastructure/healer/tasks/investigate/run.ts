import * as fs from "fs";
import { cloneRepo, readFileFromRepo, getRecentCommitsForFiles } from "../shared/git-client";
import { invokeClaudeJson } from "../shared/bedrock-client";
import { storeAuditLog, writePipelineState, readPipelineState } from "../shared/s3-client";
import { buildInvestigationPrompt, INVESTIGATION_SYSTEM_PROMPT } from "./prompts";
import {
  PipelineState,
  InvestigationReport,
  EnrichedHealerEvent,
} from "../../lambdas/shared/types";

const extractFilesFromStackTrace = (stackTrace: string): string[] => {
  const pattern =
    /(?:at\s+\S+\s+\()?((?:src|lib|app|packages|server|api)[^\s:)]+\.tsx?)/g;
  const matches = [...stackTrace.matchAll(pattern)].map((m) => m[1]);
  return [...new Set(matches)].slice(0, 8);
};

const main = async () => {
  const executionId = process.env.EXECUTION_ID;
  if (!executionId) throw new Error("EXECUTION_ID env var required");

  const state = await readPipelineState<PipelineState>(executionId);
  const enriched = (state.enriched ?? state.event) as EnrichedHealerEvent;

  const { repoPath, git } = await cloneRepo();
  console.log(`[INVESTIGATE] Cloned repo to ${repoPath}`);

  let raw = "";
  let parsed!: InvestigationReport;

  try {
  const impliedFiles = extractFilesFromStackTrace(enriched.stackTrace ?? "");

  const fileContents: Record<string, string> = {};
  for (const f of impliedFiles) {
    const content = readFileFromRepo(repoPath, f);
    if (content) fileContents[f] = content;
  }

  const recentCommits = await getRecentCommitsForFiles(git, impliedFiles, 5);
  const userPrompt = buildInvestigationPrompt(enriched, fileContents, recentCommits);
  try {
    const result = await invokeClaudeJson<InvestigationReport>(
      INVESTIGATION_SYSTEM_PROMPT,
      userPrompt,
    );
    raw = result.raw;
    parsed = result.parsed;
    await storeAuditLog(executionId, "investigate", {
      prompt: userPrompt,
      response: raw,
      metadata: { tokens: result.tokens, filesRead: Object.keys(fileContents) },
    });
  } catch (err) {
    await storeAuditLog(executionId, "investigate-error", {
      prompt: userPrompt,
      response: raw,
      metadata: { error: String(err) },
    });
    throw err;
  }

  console.log(`[INVESTIGATE] Confidence: ${parsed!.confidenceScore}/100`);
  } finally {
    fs.rmSync(repoPath, { recursive: true, force: true });
  }

  const updated: PipelineState = {
    ...state,
    investigation: { ...parsed!, rawBedrockResponse: raw },
  };

  // Write updated state to S3 for next stage
  await writePipelineState(updated);
  console.log(`[INVESTIGATE] State written to S3 for execution ${executionId}`);
};

main().catch((err) => {
  console.error("[INVESTIGATE] Fatal:", err);
  process.exit(1);
});
