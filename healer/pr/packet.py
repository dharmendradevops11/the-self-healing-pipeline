"""The reviewer packet (Chapter 9, "Designing for Human Speed").

If the pipeline needs a human review it has to make that review fast: what broke, how sure the
system is, and what the proposed patch is. A short YAML summary, attached to the pull request
as HEALER_REPORT.md.
"""

from __future__ import annotations

import json
import re
from typing import Any

from healer.gate.decision import Decision


def _q(value: str) -> str:
    return json.dumps(value)  # a JSON string is a valid YAML double-quoted scalar


def _flow(items: list[str]) -> str:
    return "[" + ", ".join(_q(i) for i in items) + "]"


def incident_id_from(event: dict[str, Any], fallback: str) -> str:
    match = re.search(r"/issues/(\d+)", event.get("sentryIssueUrl", "") or "")
    return f"SENTRY-{match.group(1)}" if match else fallback


def build_reviewer_packet(
    *,
    event: dict[str, Any],
    execution_id: str,
    root_cause: str,
    confidence: int,
    evidence: str,
    decision: Decision,
    files_changed: list[str],
    diff_summary: str,
    tests_run: list[str],
    fix_commit: str | None = None,
) -> str:
    is_fix = bool(files_changed)
    blast = decision.blast_radius
    rollback = (
        f"git revert {fix_commit or '<commit-sha>'}; no schema or state changes involved"
        if is_fix
        else "No code change to roll back."
    )
    return "\n".join(
        [
            "incident:",
            f"  sentry_event_id: {_q(incident_id_from(event, execution_id))}",
            f"  service: {_q(event['affectedService'])}",
            f"  first_seen: {_q(event['triggeredAt'])}",
            f"  affected_users_estimate: {blast['estimated_users']}",
            "",
            "diagnosis:",
            f"  root_cause: {_q(root_cause)}",
            f"  confidence_score: {confidence}",
            f"  evidence: {_q(evidence)}",
            "",
            "proposed_fix:",
            f"  files_changed: {_flow(files_changed)}",
            f"  diff_summary: {_q(diff_summary)}",
            f"  tests_run: {_flow(tests_run)}",
            "",
            "blast_radius:",
            f"  tier: {_q(blast['tier'])}",
            f"  affected_services: {blast['affected_services']}",
            f"  sensitive_data_at_risk: {str(blast['sensitive_data_at_risk']).lower()}",
            "",
            f"rollback_plan: {_q(rollback)}",
            "",
        ]
    )
