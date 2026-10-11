"""Situations that always put a human in the loop (Chapter 14, "Monitoring the Healer").

"Confidence score should decide speed. It should never decide whether a human sees the issue
at all." Every outcome of this pipeline already ends with a person (a pull request or a
message), so these flags do not add a gate. They make the reason visible and raise the
urgency, so a critical service, a pattern the system has never handled, or a failure that keeps
coming back despite a merged fix is never treated as routine.
"""

from __future__ import annotations

from typing import Any


def human_review_flags(
    blast_radius_tier: str,
    history: float | None,
    prior_incidents: list[dict[str, Any]],
    affected_files: list[str],
    owner: str = "",
) -> list[str]:
    flags: list[str] = []
    if owner in ("", "unassigned"):
        # Chapter 16: "we adopted a policy requiring every Sentry project to have a named team
        # and a named on-call rotation. Unowned alerts became impossible to ignore."
        flags.append("unowned service: it has no named team or on-call rotation in the registry")
    if blast_radius_tier == "critical":
        flags.append("critical service: a human always reviews")
    if history is None:
        flags.append("new failure pattern: the ledger has too little history for this category")
    changed = set(affected_files)
    for prior in prior_incidents:
        files = prior.get("files_changed") or []
        if prior.get("human_decision") in ("merged", "edited_then_merged") and changed & set(files):
            flags.append(
                f"recurring failure: {prior.get('incident_id', 'an earlier incident')} "
                "was merged and the same files failed again"
            )
            break
    return flags
