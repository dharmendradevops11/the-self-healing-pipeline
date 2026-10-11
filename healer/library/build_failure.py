"""Ask the model about a build failure (Chapter 3, "What LLMs Do Well, and Where They Stop")."""

from __future__ import annotations

import json
from typing import Any

from healer.llm.base import LLMProvider


def build_failure_prompt(log_excerpt: str, build_context: dict[str, str]) -> str:
    return f"""You are analyzing a CI/CD build failure.

Build context:
- Project: {build_context["project"]}
- Branch: {build_context["branch"]}
- Last successful build: {build_context["last_success"]}

Build log excerpt:
{log_excerpt}

Return a JSON object with:
- rootCauseHypothesis: your best guess at what failed
- confidenceScore: 0-100 integer
- affectedFiles: list of files likely involved
- fixStrategy: concrete next steps

Be specific. Reference actual error messages. If confidence is low, say why."""


def analyze_build_failure(
    llm: LLMProvider, log_excerpt: str, build_context: dict[str, str]
) -> dict[str, Any]:
    # temperature 0: the same log should give the same analysis.
    prompt = build_failure_prompt(log_excerpt, build_context)
    text = llm.invoke(prompt, max_tokens=1000, temperature=0)
    result: dict[str, Any] = json.loads(text)
    return result
