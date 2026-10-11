"""Choosing a remediation from a failure signature (Chapter 7, "Safe Remediation Patterns")."""

from __future__ import annotations

import logging

from healer.library.remediation.types import InvalidRemediationError

logger = logging.getLogger(__name__)

VALID_REMEDIATIONS = {
    "rollback_feature_flag",
    "rollback_git",
    "retry_with_backoff",
    "restart",
    "restart_with_heap_dump",
    "escalate_to_human",
}


def choose_remediation(failure_signature: str, confidence: int, has_flag: bool = False) -> str:
    """Select the appropriate remediation action based on failure signature and confidence.

    Anything unknown, low-confidence (< 40) or malformed escalates to a human.
    """
    if not (0 <= confidence <= 100):
        logger.error("Confidence score out of boundary: %s. Escalating.", confidence)
        return "escalate_to_human"
    if confidence < 40:
        return "escalate_to_human"

    try:
        if failure_signature == "5xx_spike_post_deploy":
            decision = "rollback_feature_flag" if has_flag else "rollback_git"
        elif failure_signature == "connection_timeout":
            decision = "retry_with_backoff"
        elif failure_signature == "process_unresponsive":
            decision = "restart"
        elif failure_signature == "oom_killed":
            decision = "restart_with_heap_dump"
        else:
            decision = "escalate_to_human"
        if decision not in VALID_REMEDIATIONS:
            raise InvalidRemediationError(f"Unknown remediation action: {decision}")
        return decision
    except Exception:
        logger.critical("Remediation selection crashed", exc_info=True)
        return "escalate_to_human"
