TIERS = {
    "informational": {"page": False, "channel": "slack"},
    "warning": {"page": "business_hours_only", "channel": "slack+ticket"},
    "critical": {"page": "always", "channel": "pagerduty"},
}

ESCALATION_MATRIX = {
    # (confidence_band, blast_radius_tier): (escalation_tier, fix_action)
    ("high",   "low"):      ("informational", "auto_fix_pr"),
    ("high",   "medium"):   ("informational", "auto_fix_pr"),
    ("high",   "high"):     ("warning",       "fix_pr_expedited_review"),
    ("high",   "critical"): ("critical",      "fix_pr_expedited_review"),
    ("medium", "low"):      ("informational", "auto_fix_pr"),
    ("medium", "medium"):   ("warning",       "fix_pr_standard_review"),
    ("medium", "high"):     ("warning",       "fix_pr_expedited_review"),
    ("medium", "critical"): ("critical",      "investigation_only"),
    ("low",    "low"):      ("warning",       "investigation_only"),
    ("low",    "medium"):   ("warning",       "investigation_only"),
    ("low",    "high"):     ("critical",      "investigation_only"),
    ("low",    "critical"): ("critical",      "investigation_only"),
}

def confidence_band(confidence: int) -> str:
    if confidence >= 85:
        return "high"
    if confidence >= 60:
        return "medium"
    return "low"

def route_escalation(confidence: int, blast_radius_tier: str, service_owner: str) -> dict:
    band = confidence_band(confidence)
    tier, fix_action = ESCALATION_MATRIX[(band, blast_radius_tier)]
    recipient = service_owner if tier != "critical" else get_current_oncall(service_owner)
    return {
        "tier": tier,
        "fix_action": fix_action,
        "recipient": recipient,
        "page": TIERS[tier]["page"],
        "channel": TIERS[tier]["channel"]
    }
