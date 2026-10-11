# Design the autonomous response policy
class MemoryPressurePolicy:
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
        # parse_memory_gib normalizes "512Mi" / "2Gi" / "2048M" to a float in GiB,
        # so the comparison below is numeric rather than a string/number mix.
        current_gib = parse_memory_gib(current)
        if "OOMKill" in failure_pattern:
            # Conservative: 50% increase, capped at 4 GiB
            new_gib = min(current_gib * 1.5, 4.0)
            return f"{new_gib:g}Gi"
        return f"{current_gib:g}Gi"

    def verification_criteria(self) -> dict:
        """Define what success looks like."""
        return {
            "pod_restart_count": {"operator": "eq", "value": 0, "duration": "5m"},
            "memory_usage_percent": {"operator": "lt", "value": 80},
            "error_rate": {"operator": "lt", "value": 0.01}
        }
