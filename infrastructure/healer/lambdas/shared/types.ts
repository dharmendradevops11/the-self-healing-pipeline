export type HealerSource = "sentry" | "bedrock-digest" | "manual";
export type HealerSeverity = "critical" | "high" | "medium";
export type HealerIssueType = "crash" | "performance" | "integration" | "infra";
export type FixType = "code-fix" | "investigation-only";

import type { BlastRadius, EscalationDecision } from "./decision";

/** Routing outcome from the Chapter 9 decision model. */
export interface PipelineDecision extends EscalationDecision {
  compositeConfidence: number;
  blastRadius: BlastRadius;
  /** Registry owner of the affected service, if known. */
  owner: string;
}

export interface HealerEvent {
  source: HealerSource;
  severity: HealerSeverity;
  type: HealerIssueType;
  title: string;
  stackTrace?: string;
  affectedService: string;
  affectedEndpoint?: string;
  cloudwatchLogGroup: string;
  sentryIssueUrl?: string;
  triggeredAt: string;
}

export interface CloudWatchLogEntry {
  timestamp: number;
  message: string;
}

export interface EnrichedHealerEvent extends HealerEvent {
  cloudwatchLogs: CloudWatchLogEntry[];
  sentryEventCount?: number;
  lastDeployAt?: string;
}

export interface InvestigationReport {
  rootCauseHypothesis: string;
  /**
   * Composite confidence, 0-100 (Chapter 9). Blends signal strength, the model's own
   * certainty and historical success rate. Every confidence number downstream uses this.
   */
  confidenceScore: number;
  /** The model's own stated confidence, 0-100, before blending. */
  modelConfidenceScore?: number;
  signalStrength?: number;
  /** Rolling accuracy for this failure category, or null if history is sparse. */
  historicalSuccessRate?: number | null;
  /** Failure category used for the trust ledger, for example "crash:TypeError". */
  category?: string;
  affectedFiles: string[];
  fixStrategy: string;
  rawBedrockResponse: string;
}

export interface FixResult {
  type: FixType;
  diff: string;
  affectedFiles: string[];
  /** 0-100. 90+ = single clear cause. 60-89 = likely cause. <60 = hypothesis/low-confidence. */
  confidenceScore: number;
  explanation: string;
}

export interface TestCheckResult {
  passed: boolean;
  output: string;
}

export interface TestResults {
  typeCheck: TestCheckResult;
  unitTests: TestCheckResult;
  lint: TestCheckResult;
  overallPassed: boolean;
}

export interface PipelineState {
  executionId: string;
  event: HealerEvent;
  enriched?: EnrichedHealerEvent;
  investigation?: InvestigationReport;
  fix?: FixResult;
  testResults?: TestResults;
  decision?: PipelineDecision;
  prUrl?: string;
  prNumber?: number;
  stageError?: string;
  failedStage?: string;
  branchName?: string;
}

export interface SentryWebhookPayload {
  action: string;
  data: {
    issue: {
      id: string;
      title: string;
      culprit: string;
      permalink: string;
      level: string;
      metadata?: { value?: string; filename?: string };
      project: { slug: string };
    };
  };
}
