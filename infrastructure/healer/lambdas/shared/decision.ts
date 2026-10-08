// Decision model from Chapter 9 of the book: composite confidence, blast radius,
// and the escalation matrix. Pure functions only, so they are easy to test.

export type ConfidenceBand = "high" | "medium" | "low";
export type BlastRadiusTier = "low" | "medium" | "high" | "critical";
export type EscalationTier = "informational" | "warning" | "critical";
export type FixAction =
  | "auto_fix_pr"
  | "fix_pr_standard_review"
  | "fix_pr_expedited_review"
  | "investigation_only";

export interface ServiceRegistryEntry {
  dependents?: string[];
  estimated_users?: number;
  handles_pii_or_payment?: boolean;
  /** Who receives non-critical notifications for this service. */
  owner?: string;
  /** Who is paged for critical-tier escalations. Falls back to owner. */
  oncall?: string;
}
export type ServiceRegistry = Record<string, ServiceRegistryEntry>;

export interface BlastRadius {
  affected_services: number;
  estimated_users: number;
  sensitive_data_at_risk: boolean;
  tier: BlastRadiusTier;
}

export interface EscalationDecision {
  band: ConfidenceBand;
  tier: EscalationTier;
  fixAction: FixAction;
  recipient: string;
  page: false | "business_hours_only" | "always";
  channel: string;
}

// Python's round() rounds halves to even; match it so scores agree with the book.
const roundHalfEven = (n: number): number => {
  const floor = Math.floor(n);
  const diff = n - floor;
  if (Math.abs(diff - 0.5) < 1e-9) return floor % 2 === 0 ? floor : floor + 1;
  return Math.round(n);
};

/**
 * Composite confidence, 0-100. All inputs are 0.0-1.0.
 * signalStrength: completeness/relevance of log and trace context.
 * modelCertainty: the model's own stated confidence in the diagnosis.
 * historicalSuccessRate: rolling accuracy for this failure category, or null if sparse.
 */
export const computeConfidence = (
  signalStrength: number,
  modelCertainty: number,
  historicalSuccessRate: number | null,
): number => {
  const weights = { signal: 0.3, model: 0.45, history: 0.25 };

  // Fall back to a neutral prior if historical data is sparse for a new signature.
  let history = historicalSuccessRate;
  if (history === null || history === undefined) {
    history = 0.5;
    weights.model += weights.history * 0.5;
    weights.history *= 0.5;
  }

  const score =
    signalStrength * weights.signal + modelCertainty * weights.model + history * weights.history;
  return roundHalfEven(score * 100);
};

export interface SignalEvidence {
  /** CloudWatch log lines attached to the event (the book attaches the last 20). */
  logLines: number;
  hasStackTrace: boolean;
  /** Files named by the stack trace. */
  filesImplied: number;
  /** Of those, how many were actually found and read in the repository. */
  filesRead: number;
  hasCommitContext: boolean;
}

/**
 * Signal strength, 0.0-1.0: did we feed the model enough evidence to diagnose?
 * The book defines this as completeness/relevance of log and trace context; this is the
 * repository's concrete weighting of that idea.
 */
export const computeSignalStrength = (e: SignalEvidence): number => {
  const logs = Math.min(e.logLines / 20, 1);
  const trace = e.hasStackTrace ? 1 : 0;
  const files = e.filesImplied > 0 ? Math.min(e.filesRead / e.filesImplied, 1) : 0;
  const commits = e.hasCommitContext ? 1 : 0;
  return logs * 0.3 + trace * 0.3 + files * 0.3 + commits * 0.1;
};

export const estimateBlastRadius = (serviceName: string, registry: ServiceRegistry): BlastRadius => {
  const visited = new Set<string>();
  const frontier: string[] = [serviceName];
  let totalUsers = 0;
  let touchesSensitiveData = false;

  while (frontier.length > 0) {
    const current = frontier.pop()!;
    if (visited.has(current) || !(current in registry)) continue;
    visited.add(current);
    const info = registry[current];
    totalUsers += info.estimated_users ?? 0;
    touchesSensitiveData = touchesSensitiveData || (info.handles_pii_or_payment ?? false);
    frontier.push(...(info.dependents ?? []));
  }

  let tier: BlastRadiusTier;
  if (touchesSensitiveData || totalUsers > 500_000) tier = "critical";
  else if (totalUsers > 50_000) tier = "high";
  else if (totalUsers > 5_000) tier = "medium";
  else tier = "low";

  return {
    affected_services: Math.max(visited.size - 1, 0),
    estimated_users: totalUsers,
    sensitive_data_at_risk: touchesSensitiveData,
    tier,
  };
};

export const TIERS: Record<
  EscalationTier,
  { page: false | "business_hours_only" | "always"; channel: string }
> = {
  informational: { page: false, channel: "slack" },
  warning: { page: "business_hours_only", channel: "slack+ticket" },
  critical: { page: "always", channel: "pagerduty" },
};

// (confidence band, blast radius tier) -> (escalation tier, fix action)
export const ESCALATION_MATRIX: Record<string, [EscalationTier, FixAction]> = {
  "high,low": ["informational", "auto_fix_pr"],
  "high,medium": ["informational", "auto_fix_pr"],
  "high,high": ["warning", "fix_pr_expedited_review"],
  "high,critical": ["critical", "fix_pr_expedited_review"],
  "medium,low": ["informational", "auto_fix_pr"],
  "medium,medium": ["warning", "fix_pr_standard_review"],
  "medium,high": ["warning", "fix_pr_expedited_review"],
  "medium,critical": ["critical", "investigation_only"],
  "low,low": ["warning", "investigation_only"],
  "low,medium": ["warning", "investigation_only"],
  "low,high": ["critical", "investigation_only"],
  "low,critical": ["critical", "investigation_only"],
};

export const confidenceBand = (confidence: number): ConfidenceBand => {
  if (confidence >= 85) return "high";
  if (confidence >= 60) return "medium";
  return "low";
};

export const routeEscalation = (
  confidence: number,
  blastRadiusTier: BlastRadiusTier,
  serviceOwner: string,
  getCurrentOncall: (owner: string) => string = (o) => o,
): EscalationDecision => {
  const band = confidenceBand(confidence);
  const [tier, fixAction] = ESCALATION_MATRIX[`${band},${blastRadiusTier}`];
  const recipient = tier !== "critical" ? serviceOwner : getCurrentOncall(serviceOwner);
  return { band, tier, fixAction, recipient, page: TIERS[tier].page, channel: TIERS[tier].channel };
};

/**
 * Rolling accuracy from human verdicts: approved = 1, modified = 0.5, rejected = 0.
 * Returns null when there are too few resolved outcomes to trust.
 */
export const successRateFromVerdicts = (verdicts: string[], minSamples = 5): number | null => {
  const resolved = verdicts.filter((v) => v === "approved" || v === "modified" || v === "rejected");
  if (resolved.length < minSamples) return null;
  const points = resolved.reduce((sum, v) => sum + (v === "approved" ? 1 : v === "modified" ? 0.5 : 0), 0);
  return points / resolved.length;
};
