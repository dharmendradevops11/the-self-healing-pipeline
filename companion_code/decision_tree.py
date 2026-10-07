import logging

logger = logging.getLogger(__name__)

# System-wide remediation actions
VALID_REMEDIATIONS = {
    "rollback_feature_flag", "rollback_git", "retry_with_backoff",
    "restart", "restart_with_heap_dump", "escalate_to_human"
}

def choose_remediation(failure_signature: str, confidence: int, has_flag: bool = False) -> str:
    """Select the appropriate remediation action based on failure signature and confidence.
    
    Args:
        failure_signature: The analyzed failure string token.
        confidence: Evaluated heuristic model confidence (0 - 100).
        has_flag: Indicates if active feature flags gate the code path.
    """
    # Input boundary checks
    if not (0 <= confidence <= 100):
        logger.error(f"Confidence score out of boundary: {confidence}. Escalating.")
        return "escalate_to_human"
        
    if confidence < 40:
        logger.info(f"Confidence below cutoff ({confidence} < 40). Escalating to human oncall.")
        return "escalate_to_human"

    logger.info(f"Selecting remediation for: {failure_signature} with confidence: {confidence}")

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
            logger.warning(f"Unknown failure signature: {failure_signature}. Defaulting to escalation.")
            decision = "escalate_to_human"
            
        assert decision in VALID_REMEDIATIONS
        return decision
    except Exception as e:
        logger.critical(f"Remediation selection crashed: {e}", exc_info=True)
        return "escalate_to_human"
