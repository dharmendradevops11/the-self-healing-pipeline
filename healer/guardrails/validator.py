"""Check the model's claims against reality (Chapter 3, "When Your AI Starts Lying to You").

Because LLMs lie with confidence. A diagnosis that names a service that does not exist, or
claims more errors than the metrics show, is rejected before anyone acts on it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class IncidentValidator:
    """The clients are injected so the checks run against real systems or against test doubles.

    metrics_client.query(expr, time_range) -> number
    service_registry.exists(name) -> bool
    support_api.get_recent(minutes=30) -> list
    """

    def __init__(self, metrics_client: Any, service_registry: Any, support_api: Any):
        self.metrics_client = metrics_client
        self.service_registry = service_registry
        self.support_api = support_api

    def validate_incident(self, llm_analysis: dict[str, Any]) -> dict[str, Any]:
        claimed_errors = llm_analysis.get("error_count", 0)
        actual_errors = self.metrics_client.query(
            "sum(rate(errors[5m]))", llm_analysis["time_range"]
        )
        if claimed_errors > actual_errors * 2:
            return {"valid": False, "reason": "Claimed error count implausible"}

        for service in llm_analysis.get("affected_services", []):
            if not self.service_registry.exists(service):
                return {"valid": False, "reason": f"Nonexistent service mentioned: {service}"}

        if llm_analysis.get("customer_impact"):
            recent_tickets = self.support_api.get_recent(minutes=30)
            if len(recent_tickets) == 0:
                return {
                    "valid": False,
                    "reason": "Claims customer impact but support queue empty",
                }

        return {"valid": True}


def check_constraints(
    affected_files: list[str], file_exists: Callable[[str], bool], max_files: int = 20
) -> list[str]:
    """The second of Chapter 3's three gates: constraint checking.

    "Do the suggested files exist in the repo?" The model can name a file that does not exist
    as readily as a function that does not exist. Each problem is returned as a sentence; an
    empty list means the claims check out. Structural validation (the JSON parses, the score is
    an integer from 0 to 100) happens in `parse_diagnosis`, and the human review is the PR.
    """
    problems = [
        f"the model named a file that does not exist: {p}"
        for p in affected_files
        if not file_exists(p)
    ]
    if len(affected_files) > max_files:
        problems.append(f"the model named {len(affected_files)} files, which is implausible")
    return problems
