"""Blast radius: the cost of the agent being wrong (Chapter 9)."""

from __future__ import annotations

from typing import Any

Registry = dict[str, dict[str, Any]]

TIERS = ("low", "medium", "high", "critical")


def estimate_blast_radius(service_name: str, registry: Registry) -> dict[str, Any]:
    """Walk the dependency tree and tier the damage if a fix to this service is wrong.

    registry maps service_name -> {
        "dependents": [list of service names],
        "estimated_users": int,
        "handles_pii_or_payment": bool,
        "pci_scoped": bool   # optional: never fix automatically (Chapter 11, PCI DSS)
    }
    Returns calculated blast radius metrics and tier.
    """
    visited: set[str] = set()
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
        # The book prints len(visited) - 1, which is -1 for an unknown service. Clamped here.
        "affected_services": max(len(visited) - 1, 0),
        "estimated_users": total_users,
        "sensitive_data_at_risk": touches_sensitive_data,
        "tier": tier,
    }


def blast_radius_or_default(
    service_name: str, registry: Registry, unknown_service_tier: str = "medium"
) -> dict[str, Any]:
    """Like estimate_blast_radius, but an unregistered service is not treated as zero-risk.

    The book assumes the service is in the registry. Silently scoring an unknown service as
    "low" would hand it the most authority, so it gets a configurable default tier instead.
    """
    if service_name in registry:
        return estimate_blast_radius(service_name, registry)
    return {
        "affected_services": 0,
        "estimated_users": 0,
        "sensitive_data_at_risk": False,
        "tier": unknown_service_tier,
    }
