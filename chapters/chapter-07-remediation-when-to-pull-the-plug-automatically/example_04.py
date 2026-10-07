import logging

logger = logging.getLogger(__name__)

class InvalidRemediationError(Exception):
    """Raised when remediation selection produces an action outside the valid set."""

VALID_REMEDIATIONS = {
    "rollback_feature_flag", "rollback_git", "retry_with_backoff",
    "restart", "restart_with_heap_dump", "escalate_to_human",
}

def choose_remediation(failure_signature: str, confidence: int, has_flag: bool = False) -> str:
    """Select the appropriate remediation action based on failure signature and confidence."""
    if not (0 <= confidence <= 100):
        logger.error(f"Confidence score out of boundary: {confidence}. Escalating.")
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
    except Exception as e:
        logger.critical(f"Remediation selection crashed: {e}", exc_info=True)
        return "escalate_to_human"
