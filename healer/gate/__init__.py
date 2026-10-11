"""The Figure 2.1 fork.

Composite confidence, blast radius and the escalation matrix decide: fix, or escalate to
a human. (Ch 2, 9).
"""

from healer.gate.blast_radius import blast_radius_or_default, estimate_blast_radius
from healer.gate.confidence import SignalEvidence, compute_confidence, compute_signal_strength
from healer.gate.decision import Decision, decide
from healer.gate.escalation import (
    ESCALATION_MATRIX,
    TIERS,
    confidence_band,
    route_escalation,
)

__all__ = [
    "ESCALATION_MATRIX",
    "TIERS",
    "Decision",
    "SignalEvidence",
    "blast_radius_or_default",
    "compute_confidence",
    "compute_signal_strength",
    "confidence_band",
    "decide",
    "estimate_blast_radius",
    "route_escalation",
]
