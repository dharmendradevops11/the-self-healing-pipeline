def estimate_blast_radius(service_name: str, registry: dict) -> dict:
    """
    registry maps service_name -> {
        "dependents": [list of service names],
        "estimated_users": int,
        "handles_pii_or_payment": bool
    }
    Returns calculated blast radius metrics and tier.
    """
    visited = set()
    frontier = [service_name]
    total_users = 0
    touches_sensitive_data = False

    while frontier:
        current = frontier.pop()
        if current in visited or current not in registry:
            continue
        visited.add(current)
        info = registry[current]
        total_users += info.get("estimated_users", 0)
        touches_sensitive_data |= info.get("handles_pii_or_payment", False)
        frontier.extend(info.get("dependents", []))

    if touches_sensitive_data or total_users > 500_000:
        tier = "critical"
    elif total_users > 50_000:
        tier = "high"
    elif total_users > 5_000:
        tier = "medium"
    else:
        tier = "low"

    return {
        "affected_services": len(visited) - 1,
        "estimated_users": total_users,
        "sensitive_data_at_risk": touches_sensitive_data,
        "tier": tier,
    }
