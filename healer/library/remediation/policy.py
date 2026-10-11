"""Remediation policies as configuration (Chapter 7, "Tier 1: Zero-Touch Remediation").

A policy says when to act, what to do, and what makes it safe. Keeping it as YAML means a
reviewer can read and change what the automation is allowed to do without reading code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_SECTIONS = ("trigger", "action", "safety")


@dataclass(frozen=True)
class RemediationPolicy:
    name: str
    trigger: dict[str, Any]
    action: dict[str, Any]
    safety: dict[str, Any]

    @property
    def needs_approval(self) -> bool:
        return self.safety.get("approval", "required") != "none"

    @property
    def zero_touch_eligible(self) -> bool:
        """No approval needed, and the change is reversible and confined to one instance.

        This stricter reading is this repository's, not the book's. The book shows the
        configuration; the check above is a conservative way to use it.
        """
        return (
            not self.needs_approval
            and self.safety.get("reversible") is True
            and self.safety.get("blast_radius") == "single_instance"
        )


def load_policies(yaml_text: str) -> dict[str, RemediationPolicy]:
    """Parse a `remediations:` document, rejecting any policy that is missing a section."""
    import yaml

    document = yaml.safe_load(yaml_text) or {}
    policies: dict[str, RemediationPolicy] = {}
    for name, body in (document.get("remediations") or {}).items():
        missing = [section for section in REQUIRED_SECTIONS if section not in (body or {})]
        if missing:
            raise ValueError(f"policy {name!r} is missing sections: {missing}")
        policies[name] = RemediationPolicy(name, body["trigger"], body["action"], body["safety"])
    return policies
