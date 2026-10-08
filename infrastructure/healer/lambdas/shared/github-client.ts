import { Octokit } from "@octokit/rest";
import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";
import { PipelineState, TestResults } from "./types";
import { buildReviewerPacket } from "./reviewer-packet";
import { recordOutcome } from "./ledger-client";
import { logReasoningStep } from "./audit";

const smClient = new SecretsManagerClient({ region: process.env.AWS_REGION ?? "us-east-2" });

// Fetch token at invocation time — never store in plaintext env var (P0 security fix).
// GITHUB_TOKEN_SECRET_ARN env var is the Secrets Manager ARN; falls back to GITHUB_TOKEN
// for local/test use only.
const getGithubToken = async (): Promise<string> => {
  const arn = process.env.GITHUB_TOKEN_SECRET_ARN;
  if (arn) {
    const { SecretString } = await smClient.send(new GetSecretValueCommand({ SecretId: arn }));
    return SecretString ?? "";
  }
  return process.env.GITHUB_TOKEN ?? "";
};

const getOctokit = async () => new Octokit({ auth: await getGithubToken() });

const buildTestSummary = (testResults?: TestResults): string => {
  if (!testResults) return "_Tests did not run._";
  const ok = (p: boolean) => (p ? "PASS" : "FAIL");
  return [
    `Type check: ${ok(testResults.typeCheck.passed)}`,
    `Unit tests: ${ok(testResults.unitTests.passed)}`,
    `Lint: ${ok(testResults.lint.passed)}`,
    testResults.overallPassed ? "All checks passed." : "Some checks failed — review carefully.",
  ].join("\n");
};

const buildPRBody = (state: PipelineState): string => {
  const { event, investigation, fix, testResults } = state;
  const isFixPR = fix?.type === "code-fix";
  const confidence = investigation?.confidenceScore ?? 0;

  return `## Self-Healing Pipeline — ${isFixPR ? "Fix" : "Investigation Report"}

**Issue:** ${event.title}
**Source:** ${event.source} | **Severity:** ${event.severity} | **Service:** ${event.affectedService}
${event.sentryIssueUrl ? `**Sentry:** ${event.sentryIssueUrl}` : ""}

---

### Routing decision

${state.decision ? `**Composite confidence:** ${state.decision.compositeConfidence}/100 (${state.decision.band}) | **Blast radius:** ${state.decision.blastRadius.tier} | **Action:** \`${state.decision.fixAction}\`
**Escalation:** ${state.decision.tier} → ${state.decision.recipient} (${state.decision.channel})` : "_No routing decision recorded._"}

---

### Root Cause Analysis

${investigation?.rootCauseHypothesis ?? "_Investigation did not complete._"}

**Confidence:** ${confidence}/100${investigation?.modelConfidenceScore !== undefined ? ` (model said ${investigation.modelConfidenceScore}, signal ${Math.round((investigation.signalStrength ?? 0) * 100)}%, history ${investigation.historicalSuccessRate == null ? "n/a" : Math.round(investigation.historicalSuccessRate * 100) + "%"})` : ""}
**Fix strategy:** ${investigation?.fixStrategy ?? "N/A"}
**Files analysed:** ${(investigation?.affectedFiles ?? []).map((f) => `\`${f}\``).join(", ") || "None"}

---

### ${isFixPR ? "Fix Applied" : "Investigation Notes (No Code Change)"}

${fix?.explanation ?? "_No fix was generated._"}

---

### Test Results

\`\`\`
${buildTestSummary(testResults)}
\`\`\`

---

_Execution ID: \`${state.executionId}\` | Triggered: ${event.triggeredAt}_
${state.stageError ? `\n> Pipeline error in stage \`${state.failedStage}\`: ${state.stageError}` : ""}
`;
};

const ACTION_LABELS: Record<string, string> = {
  auto_fix_pr: "healer: auto-fix-pr",
  fix_pr_standard_review: "healer: standard-review",
  fix_pr_expedited_review: "healer: expedited-review",
  investigation_only: "healer: investigation-only",
};

const buildLabels = (state: PipelineState): string[] => {
  const labels = ["healer"];
  const d = state.decision;
  if (d) {
    labels.push(ACTION_LABELS[d.fixAction], `healer: blast-radius-${d.blastRadius.tier}`);
  }
  if ((state.investigation?.confidenceScore ?? 0) < 60) labels.push("healer: low-confidence");
  if ((state.fix?.diff ?? "").split("\n").length > 400) labels.push("healer: large-diff");
  if ((state.fix?.affectedFiles ?? []).some((f) => f.includes("infrastructure/templates"))) {
    labels.push("healer: infra-change");
  }
  return labels;
};

const slugify = (title: string) =>
  title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .slice(0, 40);

export const createHealerPR = async (
  state: PipelineState,
): Promise<{ prUrl: string; prNumber: number }> => {
  const octokit = await getOctokit();
  const owner = process.env.GITHUB_REPO_OWNER ?? "YOUR-GITHUB-ORG";
  const repo = process.env.GITHUB_REPO_NAME ?? "your-repo";
  const base = process.env.GITHUB_BASE_BRANCH ?? "develop";

  const isFixPR = state.fix?.type === "code-fix";

  let branch: string;

  if (state.branchName) {
    // Branch was already pushed by the Fix Fargate task (code-fix or investigation-only report).
    // Never call createRef when branchName is in state — the ref already exists.
    branch = state.branchName;
  } else {
    // No branch from Fix stage (rare: fix stage itself errored before pushing).
    // Create a lightweight branch from base HEAD so the PR still lands.
    const date = new Date().toISOString().slice(0, 10);
    branch = `healer/${date}-${slugify(state.event.title)}`;
    const { data: baseRef } = await octokit.git.getRef({ owner, repo, ref: `heads/${base}` });
    await octokit.git.createRef({
      owner,
      repo,
      ref: `refs/heads/${branch}`,
      sha: baseRef.object.sha,
    });
  }

  // Reviewer packet (Chapter 9): commit HEALER_REPORT.md to the branch so it travels with the PR.
  const { data: head } = await octokit.repos.getBranch({ owner, repo, branch });
  let existingSha: string | undefined;
  try {
    const { data: existing } = await octokit.repos.getContent({ owner, repo, path: "HEALER_REPORT.md", ref: branch });
    if (!Array.isArray(existing) && "sha" in existing) existingSha = existing.sha;
  } catch {
    existingSha = undefined;
  }
  await octokit.repos.createOrUpdateFileContents({
    owner,
    repo,
    path: "HEALER_REPORT.md",
    branch,
    message: "chore(healer): add reviewer packet",
    content: Buffer.from(buildReviewerPacket(state, head.commit.sha), "utf8").toString("base64"),
    ...(existingSha ? { sha: existingSha } : {}),
  });

  const title = `[HEALER] ${isFixPR ? "fix" : "investigate"}: ${state.event.title.slice(0, 70)}`;

  const { data: pr } = await octokit.pulls.create({
    owner,
    repo,
    title,
    base,
    head: branch,
    body: buildPRBody(state),
    draft: !isFixPR,
  });

  await octokit.issues.addLabels({
    owner,
    repo,
    issue_number: pr.number,
    labels: buildLabels(state),
  });

  // Trust ledger: start tracking this outcome as "pending" until a reviewer decides.
  try {
    await recordOutcome({
      executionId: state.executionId,
      hypothesis: state.investigation?.rootCauseHypothesis ?? "",
      confidence: state.investigation?.confidenceScore ?? 0,
      humanVerdict: "pending",
      fixWorked: null,
      category: state.investigation?.category,
    });
  } catch (err) {
    console.warn(`[PR] Could not record ledger entry: ${String(err)}`);
  }
  try {
    await logReasoningStep(state.executionId, {
      stepType: "pr",
      output: { prUrl: pr.html_url, prNumber: pr.number, labels: buildLabels(state) },
      confidence: state.investigation?.confidenceScore,
    });
  } catch (err) {
    console.warn(`[PR] Could not write audit step: ${String(err)}`);
  }

  return { prUrl: pr.html_url, prNumber: pr.number };
};
