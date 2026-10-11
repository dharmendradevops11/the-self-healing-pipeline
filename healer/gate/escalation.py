"""The escalation matrix: confidence band x blast radius -> authority (Chapter 9)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

TIERS: dict[str, dict[str, Any]] = {
    "informational": {"page": False, "channel": "slack"},
    "warning": {"page": "business_hours_only", "channel": "slack+ticket"},
    "critical": {"page": "always", "channel": "pagerduty"},
}

ESCALATION_MATRIX: dict[tuple[str, str], tuple[str, str]] = {
    # (confidence_band, blast_radius_tier): (escalation_tier, fix_action)
    ("high", "low"): ("informational", "auto_fix_pr"),
    ("high", "medium"): ("informational", "auto_fix_pr"),
    ("high", "high"): ("warning", "fix_pr_expedited_review"),
    ("high", "critical"): ("critical", "fix_pr_expedited_review"),
    ("medium", "low"): ("informational", "auto_fix_pr"),
    ("medium", "medium"): ("warning", "fix_pr_standard_review"),
    ("medium", "high"): ("warning", "fix_pr_expedited_review"),
    ("medium", "critical"): ("critical", "investigation_only"),
    ("low", "low"): ("warning", "investigation_only"),
    ("low", "medium"): ("warning", "investigation_only"),
    ("low", "high"): ("critical", "investigation_only"),
    ("low", "critical"): ("critical", "investigation_only"),
}

FIX_ACTIONS = (
    "auto_fix_pr",
    "fix_pr_standard_review",
    "fix_pr_expedited_review",
    "investigation_only",
)


DEFAULT_FIX_THRESHOLD = 60  # Chapter 2 and 18: a deliberate policy choice, a deployment parameter


def confidence_band(confidence: int, fix_threshold: int = DEFAULT_FIX_THRESHOLD) -> str:
    if confidence >= 85:
        return "high"
    if confidence >= fix_threshold:
        return "medium"
    return "low"


def route_escalation(
    confidence: int,
    blast_radius_tier: str,
    service_owner: str,
    get_current_oncall: Callable[[str], str] = lambda owner: owner,
    fix_threshold: int = DEFAULT_FIX_THRESHOLD,
) -> dict[str, Any]:
    """Decide how urgent the notification is and what the pipeline may do without a human.

    The book calls an undefined get_current_oncall(); here it is a parameter. Wire in your
    paging system, or leave the default, which pages the service owner.
    """
    band = confidence_band(confidence, fix_threshold)
    tier, fix_action = ESCALATION_MATRIX[(band, blast_radius_tier)]
    recipient = service_owner if tier != "critical" else get_current_oncall(service_owner)
    return {
        "band": band,
        "tier": tier,
        "fix_action": fix_action,
        "recipient": recipient,
        "page": TIERS[tier]["page"],
        "channel": TIERS[tier]["channel"],
    }
