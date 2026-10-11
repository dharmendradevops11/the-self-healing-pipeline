"""Stage 3, Fix: ask the model for a patch (Chapter 2)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from healer.guardrails.delimiters import BOUNDARY_INSTRUCTION, TAG, neutralize_tag
from healer.investigate.diagnose import render_files
from healer.llm.base import LLMProvider

FIX_PROMPT = """You are fixing a production bug.

Root cause: {root_cause}
Evidence: {evidence}

Files you were shown (the only files you may change):
{file_contents}

Existing tests that exercise those files. They are READ-ONLY: do not change them, and do not
return them in affectedFiles. Your fix must make them pass, including any exact values they expect:
{test_contents}

Return JSON with exactly these fields:
- type: "code-fix" or "investigation-only"
- diff: a unified diff in git diff format that applies to the files above, with full headers
  (`diff --git a/<path> b/<path>`, `--- a/<path>`, `+++ b/<path>`); empty if investigation-only
- affectedFiles: array of the file paths the diff changes
- explanation: one short paragraph on what the change does and why

Change only what the root cause requires. If you cannot produce a safe fix, return
"investigation-only" and say why in the explanation.
"""


class FixError(ValueError):
    """The model did not return a usable fix."""


@dataclass(frozen=True)
class FixProposal:
    type: str  # "code-fix" | "investigation-only"
    diff: str
    affected_files: list[str] = field(default_factory=list)
    explanation: str = ""
    raw_response: str = ""

    @property
    def is_code_fix(self) -> bool:
        return self.type == "code-fix" and bool(self.diff.strip())


def build_fix_prompt(
    root_cause: str,
    evidence: str,
    file_contents: dict[str, str],
    test_contents: dict[str, str] | None = None,
) -> str:
    data = FIX_PROMPT.format(
        root_cause=root_cause,
        evidence=evidence,
        file_contents=render_files(file_contents),
        test_contents=render_files(test_contents) if test_contents else "(none found)",
    )
    return f"{BOUNDARY_INSTRUCTION}\n\n<{TAG}>\n{neutralize_tag(data)}\n</{TAG}>\n"


def parse_fix(text: str) -> FixProposal:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise FixError("no JSON object in the model response")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise FixError(f"model response is not valid JSON: {exc}") from exc
    kind = data.get("type")
    if kind not in ("code-fix", "investigation-only"):
        raise FixError(f"unknown fix type {kind!r}")
    files = data.get("affectedFiles", [])
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise FixError("affectedFiles must be a list of paths")
    return FixProposal(
        type=kind,
        diff=str(data.get("diff", "")),
        affected_files=files,
        explanation=str(data.get("explanation", "")),
        raw_response=text,
    )


def generate_fix(
    llm: LLMProvider,
    root_cause: str,
    evidence: str,
    file_contents: dict[str, str],
    test_contents: dict[str, str] | None = None,
) -> FixProposal:
    prompt = build_fix_prompt(root_cause, evidence, file_contents, test_contents)
    return parse_fix(llm.invoke(prompt, max_tokens=4096))


def fix_context(file_contents: dict[str, str], affected: list[str]) -> dict[str, Any]:
    """Only the files the diagnosis named, so the model is shown nothing it need not change."""
    return {p: file_contents[p] for p in affected if p in file_contents}
