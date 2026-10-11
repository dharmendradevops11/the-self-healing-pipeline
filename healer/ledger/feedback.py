"""Close the loop: what the human decided (Chapter 2 Stage 4, Chapter 9 "The Ledger").

"Persist the outcome of every remediation ... whether a human accepted or rejected the PR."
Without this the trust ledger keeps every row at "pending", the history input to the composite
confidence score never activates, and the pipeline never learns. GitHub tells us when a pull
request closes; this turns that event into a verdict.
"""

from __future__ import annotations

import re
from typing import Any

from healer.ledger.remediation_history import update_decision
from healer.ledger.trust_ledger import update_verdict

EXECUTION = re.compile(r"Execution: `(exec-[A-Za-z0-9]+)`")
# The pull request holds two commits: the fix and the reviewer packet. A third means a human
# edited it. An investigation-only PR holds one.
BASELINE_COMMITS = {"fix": 2, "investigation": 1}
REJECTION_REASONS = (
    "Wrong approach",
    "Wrong root cause",
    "Breaks compliance",
    "Security concern",
    "Doesn't address the root cause",
    "Already fixed elsewhere",
    "Business context the model couldn't see",
)


def rejection_reason(body: str) -> str | None:
    """The reason ticked in the pull request template (docs/templates/pull_request_template.md)."""
    for reason in REJECTION_REASONS:
        if re.search(rf"- \[[xX]\] {re.escape(reason)}", body):
            return reason
    return None


def apply_pr_outcome(
    dynamodb: Any,
    event: dict[str, Any],
    ledger_table: str,
    history_table: str,
) -> dict[str, Any]:
    """Update the ledger and the history from a GitHub `pull_request` webhook payload."""
    pr = event.get("pull_request") or {}
    if event.get("action") != "closed":
        return {"ignored": "only closed pull requests carry a verdict"}
    if not str(pr.get("head", {}).get("ref", "")).startswith("healer/"):
        return {"ignored": "not a healer/ branch"}
    body = str(pr.get("body") or "")
    match = EXECUTION.search(body)
    if not match:
        return {"ignored": "no execution id in the pull request"}
    execution_id = match.group(1)
    if "Investigation only" in body:
        # A report is not a fix; closing it says nothing about whether the diagnosis was right.
        return {"ignored": "investigation-only pull request", "execution_id": execution_id}

    merged = bool(pr.get("merged"))
    edited = merged and int(pr.get("commits", 0)) > BASELINE_COMMITS["fix"]
    verdict = "modified" if edited else "approved" if merged else "rejected"
    decision = "edited_then_merged" if edited else "merged" if merged else "rejected"
    reason = None if merged else rejection_reason(body)
    update_verdict(dynamodb, execution_id, verdict, table_name=ledger_table)
    update_decision(dynamodb, execution_id, decision, reason, table_name=history_table)
    return {"execution_id": execution_id, "verdict": verdict, "reason": reason}
