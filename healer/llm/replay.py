"""A deterministic model for offline experiments.

Reads canned answers instead of calling Bedrock, so anyone can run the whole pipeline on a
laptop with no AWS account, no cost, and the same result every time. Each rule pairs a
substring of the prompt with the text to answer; the first match wins.
"""

from __future__ import annotations

import json
from pathlib import Path


class ReplayMiss(LookupError):
    """No canned answer matches this prompt."""


class ReplayProvider:
    def __init__(self, rules: list[tuple[str, str]] | None = None):
        self.rules = rules or []
        self.prompts: list[str] = []  # everything it was asked, for inspection in experiments

    @classmethod
    def from_file(cls, path: str | Path) -> ReplayProvider:
        """Load rules from JSON: [{"when": "<prompt substring>", "reply": <text or object>}]."""
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
        rules = [
            (e["when"], e["reply"] if isinstance(e["reply"], str) else json.dumps(e["reply"]))
            for e in entries
        ]
        return cls(rules)

    def invoke(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None
    ) -> str:
        self.prompts.append(prompt)
        for when, reply in self.rules:
            if when in prompt:
                return reply
        raise ReplayMiss(
            "no replay rule matches this prompt; add a rule or use the Bedrock provider"
        )
