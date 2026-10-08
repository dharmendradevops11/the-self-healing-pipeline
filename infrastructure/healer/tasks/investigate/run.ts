import * as fs from "fs";
import { cloneRepo, readFileFromRepo, getRecentCommitsForFiles } from "../shared/git-client";
import { invokeClaudeJson } from "../shared/bedrock-client";
import { storeAuditLog, writePipelineState, readPipelineState } from "../shared/s3-client";
import { buildInvestigationPrompt, INVESTIGATION_SYSTEM_PROMPT } from "./prompts";
import { computeConfidence, computeSignalStrength } from "../../lambdas/shared/decision";
import { buildDecision, parseRegistry, parseTier } from "../../lambdas/shared/routing";
import { getHistoricalSuccessRate } from "../../lambdas/shared/ledger-client";
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
  let signalStrength = 0;
  let impliedCount = 0;
  let readCount = 0;
  let hasCommits = false;

  try {
  const impliedFiles = extractFilesFromStackTrace(enriched.stackTrace ?? "");

  const fileContents: Record<string, string> = {};
  for (const f of impliedFiles) {
    const content = readFileFromRepo(repoPath, f);
    if (content) fileContents[f] = content;
  }

  const recentCommits = await getRecentCommitsForFiles(git, impliedFiles, 5);
  impliedCount = impliedFiles.length;
  readCount = Object.keys(fileContents).length;
  hasCommits = recentCommits.trim().length > 0;
  signalStrength = computeSignalStrength({
    logLines: Math.min((enriched.cloudwatchLogs ?? []).length, 20),
    hasStackTrace: Boolean(enriched.stackTrace),
    filesImplied: impliedCount,
    filesRead: readCount,
    hasCommitContext: hasCommits,
  });
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

  } finally {
    fs.rmSync(repoPath, { recursive: true, force: true });
  }

  // Composite confidence (Chapter 9): never trust the model's self-reported certainty alone.
  const modelScore = Math.max(0, Math.min(100, Number(parsed!.confidenceScore) || 0));
  const errorClass = (enriched.title.split(":")[0] ?? "").trim();
  const category = `${enriched.type}:${/^[A-Za-z]+(Error|Exception)$/.test(errorClass) ? errorClass : "unknown"}`;
  const history = await getHistoricalSuccessRate(category);
  const composite = computeConfidence(signalStrength, modelScore / 100, history);

  const registry = parseRegistry(process.env.HEALER_SERVICE_REGISTRY);
  const unknownTier = parseTier(process.env.HEALER_UNKNOWN_SERVICE_TIER, "medium");
  const decision = buildDecision(enriched.affectedService, composite, registry, unknownTier);

  console.log(
    `[INVESTIGATE] model=${modelScore} signal=${signalStrength.toFixed(2)} history=${history ?? "n/a"} ` +
      `-> composite=${composite} (${decision.band}), blast radius=${decision.blastRadius.tier}, action=${decision.fixAction}`,
  );
  await storeAuditLog(executionId, "confidence", {
    prompt: JSON.stringify({ modelScore, signalStrength, history, category }),
    response: JSON.stringify(decision),
    confidence: composite,
  });

  const updated: PipelineState = {
    ...state,
    investigation: {
      ...parsed!,
      confidenceScore: composite,
      modelConfidenceScore: modelScore,
      signalStrength,
      historicalSuccessRate: history,
      category,
      rawBedrockResponse: raw,
    },
    decision,
  };

  // Write updated state to S3 for next stage
  await writePipelineState(updated);
  console.log(`[INVESTIGATE] State written to S3 for execution ${executionId}`);
};

main().catch((err) => {
  console.error("[INVESTIGATE] Fatal:", err);
  process.exit(1);
});
