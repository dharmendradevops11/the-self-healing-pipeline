"""Chapter 13: the state of autonomous pipelines.

The autonomous-response policy ("every dimension must clear"), the auditable decision trail, and
the accountability map. The printed listings use types and helpers the book does not show
(`Incident`, `parse_memory_gib`, `analyze_log`, `scrub_sensitive_data`); they are defined here.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from healer.guardrails.scrubber import scrub_sensitive_data

_UNITS_GIB = {
    "Ki": 1 / (1024 * 1024),
    "Mi": 1 / 1024,
    "Gi": 1.0,
    "Ti": 1024.0,
    "K": 1000 / 1024**3,
    "M": 1_000_000 / 1024**3,
    "G": 1_000_000_000 / 1024**3,
}


def parse_memory_gib(value: str) -> float:
    """Normalize "512Mi", "2Gi", "2048M" to a float in GiB, so comparisons are numeric."""
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([KMGT]i?)?\s*", value)
    if not match:
        raise ValueError(f"cannot read a memory quantity from {value!r}")
    number, unit = float(match.group(1)), match.group(2)
    if unit is None:
        return number / 1024**3  # a bare number is bytes, as in Kubernetes
    return number * _UNITS_GIB[unit]


@dataclass
class Service:
    criticality_tier: str
    handles_sensitive_data: bool = False
    dependent_services_healthy: bool = True


@dataclass
class Action:
    is_reversible: bool
    blast_radius: str  # single_task | single_instance | service | cluster


@dataclass
class Incident:
    service: Service
    action: Action
    confidence: int  # composite score, 0-100
    during_change_freeze: bool = False
    remediations_last_24h: int = 0
    id: str = "incident"
    logs: list[str] = field(default_factory=list)

    def recent_remediation_count(self, hours: int = 24) -> int:
        return self.remediations_last_24h


class MemoryPressurePolicy:
    """Design the autonomous response policy."""

    # Services whose failure modes we understand well enough to automate.
    AUTOMATABLE_TIERS = {"tier-3", "tier-4"}

    def should_auto_remediate(self, incident: Incident) -> bool:
        """Every dimension must clear. Any single failure escalates to a human."""
        checks = (
            incident.service.criticality_tier in self.AUTOMATABLE_TIERS,
            not incident.service.handles_sensitive_data,
            incident.action.is_reversible,
            incident.action.blast_radius in {"single_instance", "single_task"},
            incident.confidence >= 85,  # composite score, 0-100
            incident.service.dependent_services_healthy,
            not incident.during_change_freeze,
            incident.recent_remediation_count(hours=24) < 3,
        )
        return all(checks)

    def calculate_resource_increase(self, current: str, failure_pattern: str) -> str:
        """Define the remediation strategy. Works in GiB floats, formats on the way out."""
        current_gib = parse_memory_gib(current)
        if "OOMKill" in failure_pattern:
            # Conservative: 50% increase, capped at 4 GiB
            new_gib = min(current_gib * 1.5, 4.0)
            return f"{new_gib:g}Gi"
        return f"{current_gib:g}Gi"

    def verification_criteria(self) -> dict[str, Any]:
        """Define what success looks like."""
        return {
            "pod_restart_count": {"operator": "eq", "value": 0, "duration": "5m"},
            "memory_usage_percent": {"operator": "lt", "value": 80},
            "error_rate": {"operator": "lt", "value": 0.01},
        }


def build_decision_trail(
    incident_data: dict[str, Any],
    *,
    analyze_log: Callable[[str], dict[str, Any]],
    generate_alternatives: Callable[[dict[str, Any]], list[dict[str, Any]]],
    select_best_option: Callable[[list[dict[str, Any]]], dict[str, Any]],
    find_precedents: Callable[[dict[str, Any]], list[Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """An auditable record of what the system considered and why.

    Everything that lands in the trail goes through the scrubber first (Chapter 11): raw log
    lines can carry credentials, customer records, or an injected payload, and an audit store is
    the last place to leave them in plaintext. The four analysis steps are parameters.
    """
    trail: dict[str, Any] = {
        "timestamp": (now or datetime.now(UTC)).isoformat(),
        "incident_id": incident_data["id"],
        "evidence_considered": [],
        "alternatives_evaluated": [],
        "decision_factors": {},
        "regulatory_metadata": {},
    }

    for log_entry in incident_data["logs"]:
        evidence = analyze_log(log_entry)
        trail["evidence_considered"].append(
            {
                "source": "application_logs",
                "content": scrub_sensitive_data(log_entry),
                "relevance_score": evidence["relevance"],
                "reasoning": evidence["why_relevant"],
            }
        )

    options = generate_alternatives(incident_data)
    for option in options:
        trail["alternatives_evaluated"].append(
            {
                "approach": option["description"],
                "estimated_risk": option["risk_score"],
                "estimated_effectiveness": option["effectiveness"],
                "rejected_because": option.get("rejection_reason"),
            }
        )

    chosen = select_best_option(options)
    trail["decision_factors"] = {
        "primary_reason": chosen["selection_rationale"],
        "confidence_score": chosen["confidence"],
        "similar_past_incidents": find_precedents(incident_data),
        "blast_radius": chosen["estimated_blast_radius"],
    }
    return trail


def map_accountability(incident: dict[str, Any]) -> dict[str, Any]:
    """Map an incident to accountable humans, even when AI made the change.

    This isn't about blame. It's about who owns the fix and the follow-up. The printed listing
    is a docstring only. The rule it states is the one enforced here: the agent is never
    accountable, so a record without a human owner is refused rather than filled in.
    """
    owner = incident.get("service_owner")
    reviewer = incident.get("approved_by")
    if not owner:
        raise ValueError("an incident needs a service_owner: someone must own the follow-up")
    if reviewer and str(reviewer).lower().startswith(("agent", "healer", "bot")):
        raise ValueError("the agent cannot approve its own change")
    return {
        "incident_id": incident.get("id"),
        "fix_owner": owner,
        "change_approved_by": reviewer or "pending review",
        "follow_up_owner": incident.get("oncall") or owner,
        "change_authored_by": incident.get("authored_by", "self-healing-pipeline (AI)"),
    }
