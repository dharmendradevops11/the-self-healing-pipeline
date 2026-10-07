def build_decision_trail(self, incident_data: Dict) -> Dict:
    """Build an auditable record of what the system considered and why."""
    decision_trail = {
        "timestamp": datetime.utcnow().isoformat(),
        "incident_id": incident_data["id"],
        "evidence_considered": [],
        "alternatives_evaluated": [],
        "decision_factors": {},
        "regulatory_metadata": {}
    }

    # Log each piece of evidence examined. Everything that lands in the trail
    # goes through the scrubber first — see Chapter 11. Raw log lines can carry
    # credentials, customer records, or an injected payload, and an audit store
    # is the last place you want any of those sitting in plaintext.
    for log_entry in incident_data["logs"]:
        evidence = self.analyze_log(log_entry)
        decision_trail["evidence_considered"].append({
            "source": "application_logs",
            "content": scrub_sensitive_data(log_entry),
            "relevance_score": evidence["relevance"],
            "reasoning": evidence["why_relevant"]
        })

    # Generate multiple fix options
    fix_options = self.generate_alternatives(incident_data)
    for option in fix_options:
        decision_trail["alternatives_evaluated"].append({
            "approach": option["description"],
            "estimated_risk": option["risk_score"],
            "estimated_effectiveness": option["effectiveness"],
            "rejected_because": option.get("rejection_reason")
        })

    # Document why we chose this specific fix
    chosen_fix = self.select_best_option(fix_options)
    decision_trail["decision_factors"] = {
        "primary_reason": chosen_fix["selection_rationale"],
        "confidence_score": chosen_fix["confidence"],
        "similar_past_incidents": self.find_precedents(incident_data),
        "blast_radius": chosen_fix["estimated_blast_radius"]
    }

    return decision_trail
