"""The Figure 2.1 fork: may the pipeline write a fix, or must it escalate to a human?"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from healer.gate.blast_radius import Registry, blast_radius_or_default
from healer.gate.escalation import DEFAULT_FIX_THRESHOLD, route_escalation


@dataclass(frozen=True)
class Decision:
    composite_confidence: int
    band: str
    blast_radius: dict[str, Any]
    tier: str  # escalation tier: informational / warning / critical
    fix_action: str
    recipient: str
    page: bool | str
    channel: str
    owner: str

    @property
    def fix_authorized(self) -> bool:
        """True when the matrix lets the pipeline generate a fix and open a pull request."""
        return self.fix_action != "investigation_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide(
    service: str,
    composite_confidence: int,
    registry: Registry,
    unknown_service_tier: str = "medium",
    fix_threshold: int = DEFAULT_FIX_THRESHOLD,
) -> Decision:
    blast = blast_radius_or_default(service, registry, unknown_service_tier)
    entry = registry.get(service, {})
    owner: str = entry.get("owner", "unassigned")
    oncall: str = entry.get("oncall", owner)
    route = route_escalation(
        composite_confidence, blast["tier"], owner, lambda _owner: oncall, fix_threshold
    )
    if entry.get("pci_scoped") and route["fix_action"] != "investigation_only":
        # Chapter 11: PCI DSS 6.2.3 and 6.2.4 require code review and change control before
        # release, and an autonomous fix bypasses that by design. "Tag any PCI-scoped service
        # and require human approval before the agent touches it. Check the tag before it even
        # thinks about committing." The agent investigates and reports; a person writes the fix.
        route = {**route, "fix_action": "investigation_only"}

    return Decision(
        composite_confidence=composite_confidence,
        band=route["band"],
        blast_radius=blast,
        tier=route["tier"],
        fix_action=route["fix_action"],
        recipient=route["recipient"],
        page=route["page"],
        channel=route["channel"],
        owner=owner,
    )
