import {
  BlastRadius,
  BlastRadiusTier,
  ServiceRegistry,
  estimateBlastRadius,
  routeEscalation,
} from "./decision";
import { PipelineDecision } from "./types";

export const parseRegistry = (raw: string | undefined): ServiceRegistry => {
  if (!raw || !raw.trim()) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as ServiceRegistry) : {};
  } catch {
    console.warn("[ROUTING] HEALER_SERVICE_REGISTRY is not valid JSON; treating the registry as empty.");
    return {};
  }
};

const VALID_TIERS: BlastRadiusTier[] = ["low", "medium", "high", "critical"];

export const parseTier = (raw: string | undefined, fallback: BlastRadiusTier): BlastRadiusTier =>
  VALID_TIERS.includes(raw as BlastRadiusTier) ? (raw as BlastRadiusTier) : fallback;

// Combines composite confidence and blast radius into the routing decision from the
// Chapter 9 escalation matrix. A service missing from the registry gets the configured
// default tier instead of silently counting as zero-risk.
export const buildDecision = (
  service: string,
  compositeConfidence: number,
  registry: ServiceRegistry,
  unknownServiceTier: BlastRadiusTier,
): PipelineDecision => {
  const known = service in registry;
  const blastRadius: BlastRadius = known
    ? estimateBlastRadius(service, registry)
    : { affected_services: 0, estimated_users: 0, sensitive_data_at_risk: false, tier: unknownServiceTier };

  const owner = registry[service]?.owner ?? "unassigned";
  const oncall = registry[service]?.oncall ?? owner;
  const decision = routeEscalation(compositeConfidence, blastRadius.tier, owner, () => oncall);

  return { ...decision, compositeConfidence, blastRadius, owner };
};
