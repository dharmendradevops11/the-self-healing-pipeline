import { parseRegistry, parseTier, buildDecision } from "../shared/routing";
import { buildReviewerPacket } from "../shared/reviewer-packet";
import { PipelineState } from "../shared/types";

const registry = parseRegistry(
  JSON.stringify({
    "checkout-api": { dependents: ["ledger"], estimated_users: 800, owner: "payments-team", oncall: "payments-oncall" },
    ledger: { estimated_users: 100, handles_pii_or_payment: true },
    "internal-tool": { estimated_users: 50, owner: "platform" },
  }),
);

describe("parseRegistry / parseTier", () => {
  it("tolerates empty and invalid JSON", () => {
    expect(parseRegistry(undefined)).toEqual({});
    expect(parseRegistry("not json")).toEqual({});
  });
  it("falls back for invalid tiers", () => {
    expect(parseTier("high", "medium")).toBe("high");
    expect(parseTier("bogus", "medium")).toBe("medium");
  });
});

describe("buildDecision", () => {
  it("routes a payment-adjacent service to critical and pages the on-call", () => {
    const d = buildDecision("checkout-api", 90, registry, "medium");
    expect(d.blastRadius.tier).toBe("critical");
    expect(d.tier).toBe("critical");
    expect(d.fixAction).toBe("fix_pr_expedited_review");
    expect(d.recipient).toBe("payments-oncall");
  });

  it("lets a contained, high-confidence fix open a PR informationally", () => {
    const d = buildDecision("internal-tool", 90, registry, "medium");
    expect(d.fixAction).toBe("auto_fix_pr");
    expect(d.tier).toBe("informational");
    expect(d.recipient).toBe("platform");
  });

  it("uses the unknown-service tier instead of assuming zero risk", () => {
    const d = buildDecision("mystery", 70, registry, "high");
    expect(d.blastRadius.tier).toBe("high");
    expect(d.fixAction).toBe("fix_pr_expedited_review");
    expect(d.recipient).toBe("unassigned");
  });

  it("never authorizes a fix below 60", () => {
    expect(buildDecision("internal-tool", 59, registry, "medium").fixAction).toBe("investigation_only");
  });
});

describe("buildReviewerPacket", () => {
  const state: PipelineState = {
    executionId: "exec-1",
    event: {
      source: "sentry",
      severity: "high",
      type: "crash",
      title: "TypeError: x",
      affectedService: "checkout-api",
      cloudwatchLogGroup: "/ecs/x",
      sentryIssueUrl: "https://sentry.io/organizations/o/issues/88213/",
      triggeredAt: "2026-07-19T02:14:00Z",
    },
    investigation: {
      rootCauseHypothesis: 'Null dereference in "auth.ts"',
      confidenceScore: 87,
      affectedFiles: ["src/auth.ts"],
      fixStrategy: "guard",
      rawBedrockResponse: "",
    },
    fix: { type: "code-fix", diff: "d", affectedFiles: ["src/auth.ts"], confidenceScore: 87, explanation: "Add optional chaining\nmore" },
    testResults: {
      typeCheck: { passed: true, output: "" },
      unitTests: { passed: true, output: "" },
      lint: { passed: false, output: "Skipped" },
      overallPassed: false,
    },
    decision: buildDecision("checkout-api", 87, registry, "medium"),
  };

  it("matches the book's layout and sections", () => {
    const y = buildReviewerPacket(state, "abc1234");
    for (const key of ["incident:", "diagnosis:", "proposed_fix:", "blast_radius:", "rollback_plan:"]) {
      expect(y).toContain(key);
    }
    expect(y).toContain('sentry_event_id: "SENTRY-88213"');
    expect(y).toContain("confidence_score: 87");
    expect(y).toContain('files_changed: ["src/auth.ts"]');
    expect(y).toContain('diff_summary: "Add optional chaining"');
    expect(y).toContain('"type-check: pass"');
    expect(y).toContain('"lint: fail (skipped)"');
    expect(y).toContain('git revert abc1234; no schema or state changes involved');
    expect(y).toContain("sensitive_data_at_risk: true");
  });

  it("escapes quotes in the root cause and states there is nothing to roll back for reports", () => {
    const y = buildReviewerPacket({ ...state, fix: { ...state.fix!, type: "investigation-only" } });
    expect(y).toContain('root_cause: "Null dereference in \\"auth.ts\\""');
    expect(y).toContain("No code change to roll back.");
    expect(y).toContain("files_changed: []");
  });
});
