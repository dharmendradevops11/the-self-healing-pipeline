"""The state that travels between stages (Chapter 2, "the S3 state bus").

Each stage of Figure 2.1 can run in a different process: a Lambda, a Fargate container, or
your laptop. They hand work to one another through this object, saved as JSON. Step Functions
cannot return a Fargate task's output, so S3 carries the state, and Step Functions carries only
the execution id.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from healer.gate.decision import Decision
from healer.investigate.diagnose import Diagnosis
from healer.pr.hosts import PullRequest
from healer.test.runner import CheckResult, TestReport

TERMINAL = {
    "rate_limited",
    "duplicate",
    "blocked",
    "escalated",
    "shadow",
    "cap_reached",
    "pr_opened",
}


@dataclass
class PipelineState:
    execution_id: str
    incident: dict[str, Any]
    status: str = "running"  # running, or one of TERMINAL
    reason: str = ""
    log_lines: list[str] = field(default_factory=list)
    diagnosis: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    degraded: list[str] = field(default_factory=list)
    category: str = ""
    history: float | None = None
    signal: float | None = None
    composite: int | None = None
    decision: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    plan_action: str = ""
    branch: str | None = None
    fix_commit: str | None = None
    tests: dict[str, Any] | None = None
    pr: dict[str, Any] | None = None
    notified: bool = False
    review_flags: list[str] = field(default_factory=list)
    constraint_problems: list[str] = field(default_factory=list)
    end_to_end_reported: bool = False
    audit_keys: list[str] = field(default_factory=list)

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL

    @property
    def service(self) -> str:
        return str(self.incident["affectedService"])

    # ---- typed views over the JSON-friendly fields ----
    def decision_obj(self) -> Decision | None:
        return Decision(**self.decision) if self.decision else None

    def diagnosis_obj(self) -> Diagnosis | None:
        return Diagnosis(**self.diagnosis) if self.diagnosis else None

    def pr_obj(self) -> PullRequest | None:
        return PullRequest(**self.pr) if self.pr else None

    def tests_obj(self) -> TestReport | None:
        if self.tests is None:
            return None
        return TestReport([CheckResult(**c) for c in self.tests["checks"]])

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)

    @classmethod
    def from_json(cls, text: str) -> PipelineState:
        return cls(**json.loads(text))


class StateStore(Protocol):
    def load(self, execution_id: str) -> PipelineState: ...
    def save(self, state: PipelineState) -> None: ...


class MemoryStateStore:
    def __init__(self) -> None:
        self._states: dict[str, str] = {}

    def load(self, execution_id: str) -> PipelineState:
        return PipelineState.from_json(self._states[execution_id])

    def save(self, state: PipelineState) -> None:
        self._states[state.execution_id] = state.to_json()


class S3StateStore:
    """The S3 state bus: `pipeline-state/{execution_id}/state.json`."""

    def __init__(self, s3: Any, bucket: str):
        self.s3, self.bucket = s3, bucket

    @staticmethod
    def key(execution_id: str) -> str:
        return f"pipeline-state/{execution_id}/state.json"

    def load(self, execution_id: str) -> PipelineState:
        body = self.s3.get_object(Bucket=self.bucket, Key=self.key(execution_id))["Body"].read()
        return PipelineState.from_json(body.decode("utf-8"))

    def save(self, state: PipelineState) -> None:
        if state.terminal and not state.end_to_end_reported:
            from healer.telemetry import report_end_to_end

            report_end_to_end(state)  # once, when the pipeline gives its last word
            state.end_to_end_reported = True
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self.key(state.execution_id),
            Body=state.to_json().encode("utf-8"),
            ContentType="application/json",
        )
