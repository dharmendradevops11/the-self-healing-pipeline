"""The INVESTIGATE stage: cheap signals first (Chapter 8, "Multi-Tool Agents").

Read the cheap, fast signal (the stack trace), then only the implicated files, then recent
changes. Pay for metrics only if the source hints at a resource problem. If an optional tool
fails, say so and carry on; if the source cannot be read, stop.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from healer.gate.confidence import SignalEvidence
from healer.investigate.diagnose import Diagnosis, diagnose
from healer.investigate.tools import safe_tool_call
from healer.llm.base import LLMProvider

MAX_FILES = 5

RESOURCE_KEYWORDS = (
    "memory", "heap", "cache", "pool", "connection", "buffer", "thread", "queue",
    "disk", "cpu", "leak", "oom", "ttl", "timeout",
)  # fmt: skip

_PATH = re.compile(r"(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|jsx|java|go|rb|rs|kt)")


def extract_stack_trace(log_text: str) -> str:
    """The stack trace portion of a log stream: from the first traceback marker onward.

    The book calls this helper without defining it. If no marker is found, the whole text is
    returned, since a bad guess here costs less than discarding the evidence.
    """
    for marker in ("Traceback (most recent call last)", "Error:", "Exception", "    at "):
        index = log_text.find(marker)
        if index != -1:
            return log_text[index:]
    return log_text


def parse_file_paths_from_trace(stack_trace: str) -> list[str]:
    """Repository-relative source paths named in a stack trace, in order, without duplicates."""
    paths: list[str] = []
    for match in _PATH.findall(stack_trace):
        # Reject traversal before normalizing: stripping "../" first would turn it into a
        # perfectly ordinary-looking path.
        if ".." in match.split("/") or match.startswith("/"):
            continue
        path = match[2:] if match.startswith("./") else match
        if path not in paths:
            paths.append(path)
    return paths


def contains_resource_keywords(source_context: dict[str, str]) -> bool:
    """Does the implicated source mention memory, pools, caches, timeouts and the like?"""
    text = " ".join(source_context.values()).lower()
    return any(keyword in text for keyword in RESOURCE_KEYWORDS)


@dataclass
class InvestigationResult:
    diagnosis: Diagnosis
    evidence: SignalEvidence
    source_files: dict[str, str]
    metrics_used: bool
    degraded: list[str]  # optional tools that failed, so the answer is based on less


def investigate_failure(
    failure_event: dict[str, Any],
    llm: LLMProvider,
    read_file: Callable[[str, str], str],
    get_git_history: Callable[..., str],
    get_cloudwatch_metrics: Callable[..., Any] | None = None,
    log_context: str = "",
    log_line_count: int | None = None,
    get_recent_deployment: Callable[[], str] | None = None,
    get_dependency_changes: Callable[[], str] | None = None,
) -> InvestigationResult:
    """Investigate one failure.

    failure_event: {"log_stream": str, "repo": str, "timestamp": datetime, "message": str}
    read_file(repo, path) -> str   reads one file from the repository
    get_git_history(repo=, file_paths=, since=) -> str   recent commits touching those files
    get_cloudwatch_metrics(namespace=, metrics=, start=, end=) -> Any   optional
    get_recent_deployment() -> str, get_dependency_changes() -> str   optional (Chapter 2's
        prompt asks for both; each is best effort and never stops an investigation)
    """
    # Cheap, fast signal first
    stack_trace = extract_stack_trace(failure_event["log_stream"])
    affected_files = parse_file_paths_from_trace(stack_trace)

    # Targeted read of just the implicated files. Without source there is nothing to diagnose.
    source_context: dict[str, str] = {}
    for file_path in affected_files[:MAX_FILES]:

        def read(path: str = file_path) -> str:
            return read_file(failure_event["repo"], path)

        result = safe_tool_call(read, fallback_value="", required=False)
        if result["success"] and result["data"]:
            source_context[file_path] = result["data"]
    if affected_files and not source_context:
        raise RuntimeError("could not read any of the implicated source files")

    degraded: list[str] = []
    history = safe_tool_call(
        lambda: get_git_history(
            repo=failure_event["repo"],
            file_paths=affected_files,
            since=failure_event["timestamp"] - timedelta(days=7),
        ),
        fallback_value="Recent commits unavailable during investigation",
    )
    if not history["success"]:
        degraded.append("git_history")

    # Only pay for metrics if the source hints at a resource issue
    metrics_context: Any = "not requested: source shows no resource-related code"
    metrics_used = False
    if get_cloudwatch_metrics is not None and contains_resource_keywords(source_context):
        end: datetime = failure_event["timestamp"]
        metrics = safe_tool_call(
            lambda: get_cloudwatch_metrics(
                namespace="AWS/ECS",
                metrics=["CPUUtilization", "MemoryUtilization"],
                start=end - timedelta(hours=2),
                end=end,
            ),
            fallback_value={"note": "Metrics unavailable during investigation"},
        )
        metrics_context = metrics["data"]
        metrics_used = metrics["success"]
        if not metrics["success"]:
            degraded.append("metrics")

    def optional(tool: Callable[[], str] | None, name: str, missing: str) -> str:
        if tool is None:
            return missing
        result = safe_tool_call(tool, fallback_value=missing)
        if not result["success"]:
            degraded.append(name)
        return str(result["data"] or missing)

    deployment = optional(get_recent_deployment, "deployment", "unknown")
    dependencies = optional(get_dependency_changes, "dependencies", "unavailable")

    diagnosis = diagnose(
        llm,
        {
            "message": failure_event.get("message", stack_trace.split("\n")[0]),
            "stack_trace": stack_trace,
        },
        log_context,
        source_context,
        {
            "commits": history["data"],
            "metrics": metrics_context,
            "recent_deployment": deployment,
            "dependency_changes": dependencies,
        },
    )

    lines = log_line_count if log_line_count is not None else len(log_context.splitlines())
    evidence = SignalEvidence(
        log_lines=lines,
        has_stack_trace=bool(stack_trace.strip()),
        files_implied=len(affected_files[:MAX_FILES]),
        files_read=len(source_context),
        has_commit_context=history["success"] and bool(str(history["data"]).strip()),
    )
    return InvestigationResult(diagnosis, evidence, source_context, metrics_used, degraded)
