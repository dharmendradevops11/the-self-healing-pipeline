"""Composite confidence scoring (Chapter 9, "Keeping the Model Honest").

The model's own certainty is one input, never the decision. It is blended with how much
evidence we gave it (signal strength) and how often the agent has been right before in this
category (historical success rate, from the trust ledger).
"""

from __future__ import annotations

from dataclasses import dataclass

WEIGHTS = {"signal": 0.30, "model": 0.45, "history": 0.25}


def compute_confidence(
    signal_strength: float,
    model_certainty: float,
    historical_success_rate: float | None,
) -> int:
    """All inputs are 0.0-1.0. Returns a composite confidence score 0-100.

    signal_strength: completeness/relevance of log and trace context
    model_certainty: model's own stated confidence in the diagnosis
    historical_success_rate: rolling accuracy for this failure category, or None if sparse
    """
    weights = dict(WEIGHTS)

    # Fall back to neutral prior if historical data is sparse for a new signature
    if historical_success_rate is None:
        historical_success_rate = 0.5
        weights["model"] += weights["history"] * 0.5
        weights["history"] *= 0.5

    score = (
        signal_strength * weights["signal"]
        + model_certainty * weights["model"]
        + historical_success_rate * weights["history"]
    )
    # Python's round() is banker's rounding, exactly as the book's listing uses.
    return round(score * 100)


@dataclass(frozen=True)
class SignalEvidence:
    """What the INVESTIGATE stage managed to gather."""

    log_lines: int
    has_stack_trace: bool
    files_implied: int  # files named by the stack trace
    files_read: int  # of those, how many were found and read in the repository
    has_commit_context: bool


def compute_signal_strength(evidence: SignalEvidence) -> float:
    """Signal strength, 0.0-1.0: did we feed the model enough to make a real diagnosis?

    The book defines this input as "completeness/relevance of log and trace context" without
    prescribing a formula. This repository's weighting: logs 30% (full credit at 20 lines),
    stack trace 30%, implicated files actually read 30%, recent commit context 10%.
    """
    logs = min(evidence.log_lines / 20, 1.0)
    trace = 1.0 if evidence.has_stack_trace else 0.0
    files = 0.0
    if evidence.files_implied > 0:
        files = min(evidence.files_read / evidence.files_implied, 1.0)
    commits = 1.0 if evidence.has_commit_context else 0.0
    return logs * 0.30 + trace * 0.30 + files * 0.30 + commits * 0.10
