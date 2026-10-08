import { PipelineState } from "./types";

const q = (v: string) => JSON.stringify(v); // JSON strings are valid YAML double-quoted scalars
const list = (items: string[]) => `[${items.map(q).join(", ")}]`;

const sentryId = (state: PipelineState): string => {
  const m = /\/issues\/(\d+)/.exec(state.event.sentryIssueUrl ?? "");
  return m ? `SENTRY-${m[1]}` : state.executionId;
};

const testsRun = (state: PipelineState): string[] => {
  const t = state.testResults;
  if (!t) return ["not run"];
  const r = (name: string, c: { passed: boolean; output: string }) =>
    `${name}: ${c.passed ? "pass" : "fail"}${c.output.startsWith("Skipped") ? " (skipped)" : ""}`;
  return [r("type-check", t.typeCheck), r("unit", t.unitTests), r("lint", t.lint)];
};

/**
 * The reviewer packet from Chapter 9: what broke, how sure the system is, and the proposed patch,
 * in a short YAML summary a reviewer can scan in seconds. Written as HEALER_REPORT.md on the branch.
 */
export const buildReviewerPacket = (state: PipelineState, fixCommitSha?: string): string => {
  const { event, investigation, fix, decision, enriched } = state;
  const isFix = fix?.type === "code-fix";
  const files = investigation?.affectedFiles ?? [];
  const logCount = Math.min((enriched?.cloudwatchLogs ?? []).length, 20);
  const br = decision?.blastRadius;

  return [
    "incident:",
    `  sentry_event_id: ${q(sentryId(state))}`,
    `  service: ${q(event.affectedService)}`,
    `  first_seen: ${q(event.triggeredAt)}`,
    `  affected_users_estimate: ${br?.estimated_users ?? 0}`,
    "",
    "diagnosis:",
    `  root_cause: ${q(investigation?.rootCauseHypothesis ?? "Investigation did not complete.")}`,
    `  confidence_score: ${investigation?.confidenceScore ?? 0}`,
    `  evidence: ${q(`${logCount} CloudWatch log lines, stack trace, git blame on ${files.join(", ") || "implicated files"}`)}`,
    "",
    "proposed_fix:",
    `  files_changed: ${list(isFix ? (fix?.affectedFiles ?? []) : [])}`,
    `  diff_summary: ${q(isFix ? (fix?.explanation ?? "").split("\n")[0] : "No code change: investigation only")}`,
    `  tests_run: ${list(testsRun(state))}`,
    "",
    "blast_radius:",
    `  tier: ${q(br?.tier ?? "unknown")}`,
    `  affected_services: ${br?.affected_services ?? 0}`,
    `  sensitive_data_at_risk: ${br?.sensitive_data_at_risk ?? false}`,
    "",
    `rollback_plan: ${q(
      isFix
        ? `git revert ${fixCommitSha ?? "<commit-sha>"}; no schema or state changes involved`
        : "No code change to roll back.",
    )}`,
    "",
  ].join("\n");
};
