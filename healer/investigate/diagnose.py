"""Stage 2, Diagnose: root cause, not symptoms (Chapter 2).

The INVESTIGATE stage gathers context beyond the raw error, builds one prompt, and asks the
model for a root-cause hypothesis with a 0-100 confidence score. Everything that reaches the
prompt and could quote attacker-controlled text is sanitized first.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from healer.guardrails.delimiters import BOUNDARY_INSTRUCTION, TAG, neutralize_tag
from healer.guardrails.sanitizer import sanitize_for_prompt
from healer.llm.base import LLMProvider

INVESTIGATION_PROMPT = """You are investigating a production error.

Error: {error_message}
Stack trace: {stack_trace}
Last 20 CloudWatch log lines: {log_context}
Recent deployment: {recent_deployment}
Recent commits touching these files: {commit_context}
Relevant metric history: {metric_context}
Dependency changes since last green build: {dependency_context}
Files read from repository: {file_contents}

Return JSON with exactly these fields:
- rootCauseHypothesis: string, specific to file/line where possible
- confidenceScore: integer 0-100
- evidenceSummary: string, what in the logs/code supports this
- affectedFiles: array of file paths
"""


@dataclass(frozen=True)
class Diagnosis:
    root_cause_hypothesis: str
    confidence_score: int  # the model's own certainty, 0-100. Not the composite score.
    evidence_summary: str
    affected_files: list[str] = field(default_factory=list)
    raw_response: str = ""
    # Chapter 3's four-field answer also carries these. Optional, for the human reviewer only:
    # "we don't parse it or feed it back into anything".
    fix_strategy: str = ""  # revert | config_change | scale | investigate
    reasoning: str = ""


class DiagnosisError(ValueError):
    """The model did not return a usable diagnosis."""


def render_files(file_contents: dict[str, str]) -> str:
    """Lay the files out so the model can tell where each one starts."""
    return "\n".join(f"--- {path} ---\n{content}" for path, content in file_contents.items())


def build_prompt(
    error_event: dict[str, Any],
    log_context: str,
    file_contents: dict[str, str],
    enrichment: dict[str, Any],
) -> str:
    """Build the investigation prompt with every untrusted field sanitized and fenced.

    Chapter 2's prompt is kept as printed. Chapter 11's Layer 1 wraps its data in an
    <untrusted_telemetry> block and tells the model that nothing inside it is an instruction.
    """
    data = INVESTIGATION_PROMPT.format(
        error_message=sanitize_for_prompt(error_event["message"]),
        stack_trace=sanitize_for_prompt(error_event["stack_trace"]),
        log_context=sanitize_for_prompt(log_context),
        recent_deployment=sanitize_for_prompt(str(enrichment.get("recent_deployment", "unknown"))),
        commit_context=sanitize_for_prompt(str(enrichment.get("commits", ""))),
        metric_context=sanitize_for_prompt(str(enrichment.get("metrics", "unavailable"))),
        dependency_context=sanitize_for_prompt(
            str(enrichment.get("dependency_changes", "unavailable"))
        ),
        file_contents=neutralize_tag(render_files(file_contents)),
    )
    return f"{BOUNDARY_INSTRUCTION}\n\n<{TAG}>\n{neutralize_tag(data)}\n</{TAG}>\n"


def parse_diagnosis(text: str) -> Diagnosis:
    """Extract and validate the JSON object the prompt asks for.

    Models sometimes wrap JSON in a code fence or add a sentence around it, so look for the
    outermost object instead of assuming the whole reply parses.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise DiagnosisError("no JSON object in the model response")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise DiagnosisError(f"model response is not valid JSON: {exc}") from exc

    required = ("rootCauseHypothesis", "confidenceScore", "affectedFiles")
    missing = [k for k in required if k not in data]
    if missing:
        raise DiagnosisError(f"model response is missing fields: {missing}")
    try:
        score = int(data["confidenceScore"])
    except (TypeError, ValueError) as exc:
        raise DiagnosisError("confidenceScore is not a number") from exc
    files = data["affectedFiles"]
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise DiagnosisError("affectedFiles must be a list of paths")

    return Diagnosis(
        root_cause_hypothesis=str(data["rootCauseHypothesis"]),
        confidence_score=max(0, min(100, score)),
        evidence_summary=str(data.get("evidenceSummary", "")),
        affected_files=files,
        raw_response=text,
        fix_strategy=str(data.get("fixStrategy", "")),
        reasoning=str(data.get("reasoning", "")),
    )


def diagnose(
    llm: LLMProvider,
    error_event: dict[str, Any],
    log_context: str,
    file_contents: dict[str, str],
    enrichment: dict[str, Any],
) -> Diagnosis:
    """Ask the model for a root cause. `enrichment` carries the context beyond the raw error:

    the deploy that preceded it, commits touching the implicated files, recent metric history,
    and dependency deltas since the last green build. It is assembled from AWS and GitHub APIs
    rather than from the alert payload, but it can still quote text an attacker controls.
    """
    prompt = build_prompt(error_event, log_context, file_contents, enrichment)
    return parse_diagnosis(llm.invoke(prompt, max_tokens=1024))
