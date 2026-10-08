import {
  computeConfidence,
  computeSignalStrength,
  estimateBlastRadius,
  confidenceBand,
  routeEscalation,
  successRateFromVerdicts,
  ESCALATION_MATRIX,
  ServiceRegistry,
} from "../shared/decision";

describe("computeConfidence (book, Chapter 9)", () => {
  it("blends signal 0.30, model 0.45, history 0.25", () => {
    expect(computeConfidence(1, 1, 1)).toBe(100);
    expect(computeConfidence(0, 0, 0)).toBe(0);
    expect(computeConfidence(0.8, 0.9, 0.7)).toBe(82); // 0.24 + 0.405 + 0.175
  });

  it("shifts half of the history weight to the model when history is sparse", () => {
    // weights become signal 0.30, model 0.575, history 0.125, neutral prior 0.5
    expect(computeConfidence(0.8, 0.9, null)).toBe(82); // 0.24 + 0.5175 + 0.0625
  });

  it("does not let a high model score alone clear the 60 gate", () => {
    // A very confident model with no evidence and a poor track record.
    expect(computeConfidence(0, 0.95, 0.2)).toBeLessThan(60);
  });
});

describe("computeSignalStrength", () => {
  it("is 1.0 with full evidence and 0 with none", () => {
    expect(
      computeSignalStrength({ logLines: 20, hasStackTrace: true, filesImplied: 2, filesRead: 2, hasCommitContext: true }),
    ).toBeCloseTo(1);
    expect(
      computeSignalStrength({ logLines: 0, hasStackTrace: false, filesImplied: 0, filesRead: 0, hasCommitContext: false }),
    ).toBe(0);
  });

  it("caps log credit at 20 lines and file credit at 100%", () => {
    expect(
      computeSignalStrength({ logLines: 500, hasStackTrace: false, filesImplied: 1, filesRead: 5, hasCommitContext: false }),
    ).toBeCloseTo(0.6);
  });
});

describe("estimateBlastRadius (book, Chapter 9)", () => {
  const registry: ServiceRegistry = {
    gateway: { dependents: ["checkout", "reports"], estimated_users: 1000 },
    checkout: { dependents: [], estimated_users: 60_000, handles_pii_or_payment: true },
    reports: { dependents: [], estimated_users: 200 },
    internal: { dependents: [], estimated_users: 100 },
    mid: { dependents: [], estimated_users: 6_000 },
    big: { dependents: [], estimated_users: 60_000 },
    huge: { dependents: [], estimated_users: 600_000 },
  };

  it("walks dependents and flags sensitive data as critical", () => {
    const r = estimateBlastRadius("gateway", registry);
    expect(r.affected_services).toBe(2);
    expect(r.estimated_users).toBe(61_200);
    expect(r.sensitive_data_at_risk).toBe(true);
    expect(r.tier).toBe("critical");
  });

  it("maps user counts to tiers", () => {
    expect(estimateBlastRadius("internal", registry).tier).toBe("low");
    expect(estimateBlastRadius("mid", registry).tier).toBe("medium");
    expect(estimateBlastRadius("big", registry).tier).toBe("high");
    expect(estimateBlastRadius("huge", registry).tier).toBe("critical");
  });

  it("survives dependency cycles and unknown services", () => {
    const cyclic: ServiceRegistry = { a: { dependents: ["b"] }, b: { dependents: ["a"] } };
    expect(estimateBlastRadius("a", cyclic).affected_services).toBe(1);
    expect(estimateBlastRadius("nope", {}).affected_services).toBe(0);
  });
});

describe("confidenceBand", () => {
  it("is low below 60, medium 60-84, high at 85 and above", () => {
    expect(confidenceBand(59)).toBe("low");
    expect(confidenceBand(60)).toBe("medium");
    expect(confidenceBand(84)).toBe("medium");
    expect(confidenceBand(85)).toBe("high");
  });
});

describe("escalation matrix (book, Chapter 9)", () => {
  it("has all 12 cells", () => {
    expect(Object.keys(ESCALATION_MATRIX)).toHaveLength(12);
  });

  const cases: Array<[number, "low" | "medium" | "high" | "critical", string, string]> = [
    [90, "low", "informational", "auto_fix_pr"],
    [90, "medium", "informational", "auto_fix_pr"],
    [90, "high", "warning", "fix_pr_expedited_review"],
    [90, "critical", "critical", "fix_pr_expedited_review"],
    [70, "low", "informational", "auto_fix_pr"],
    [70, "medium", "warning", "fix_pr_standard_review"],
    [70, "high", "warning", "fix_pr_expedited_review"],
    [70, "critical", "critical", "investigation_only"],
    [40, "low", "warning", "investigation_only"],
    [40, "medium", "warning", "investigation_only"],
    [40, "high", "critical", "investigation_only"],
    [40, "critical", "critical", "investigation_only"],
  ];
  it.each(cases)("confidence %i x %s blast radius", (conf, blast, tier, action) => {
    const d = routeEscalation(conf, blast, "owner");
    expect(d.tier).toBe(tier);
    expect(d.fixAction).toBe(action);
  });

  it("pages the on-call only for critical tier", () => {
    const oncall = (o: string) => `oncall-of-${o}`;
    expect(routeEscalation(70, "medium", "team-a", oncall).recipient).toBe("team-a");
    const crit = routeEscalation(40, "critical", "team-a", oncall);
    expect(crit.recipient).toBe("oncall-of-team-a");
    expect(crit.page).toBe("always");
    expect(crit.channel).toBe("pagerduty");
  });

  it("uses business-hours paging and slack+ticket for warnings, and no paging for informational", () => {
    const w = routeEscalation(70, "medium", "o");
    expect([w.page, w.channel]).toEqual(["business_hours_only", "slack+ticket"]);
    const i = routeEscalation(90, "low", "o");
    expect([i.page, i.channel]).toEqual([false, "slack"]);
  });
});

describe("successRateFromVerdicts", () => {
  it("returns null until there are enough resolved outcomes", () => {
    expect(successRateFromVerdicts(["approved", "approved", "pending"])).toBeNull();
  });

  it("scores approved 1, modified 0.5, rejected 0", () => {
    const v = ["approved", "approved", "modified", "rejected", "rejected", "pending"];
    expect(successRateFromVerdicts(v)).toBeCloseTo((1 + 1 + 0.5) / 5);
  });
});
