"""The whole pipeline, wired together (Figure 2.1).

    INGEST -> INVESTIGATE -> gate --(fix authorized)--> FIX -> TEST -> PR -> NOTIFY
                                  \\--(otherwise)--> investigation-only PR + Slack

`run_pipeline` runs the stages one after another in this process, saving the state between
them exactly as separate Lambdas and Fargate tasks would. Every side effect is injected, so the
same code runs offline on a laptop, against LocalStack, or on AWS. Nothing here merges
anything: only a human can merge.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from healer import stages
from healer.gate import Decision
from healer.investigate import Diagnosis
from healer.pr.hosts import PullRequest
from healer.services import Services
from healer.state import PipelineState, S3StateStore, StateStore
from healer.test.runner import TestReport

__all__ = ["PipelineResult", "Services", "run_pipeline"]


@dataclass
class PipelineResult:
    execution_id: str
    outcome: (
        str  # pr_opened | escalated | shadow | rate_limited | duplicate | blocked | cap_reached
    )
    reason: str = ""
    decision: Decision | None = None
    diagnosis: Diagnosis | None = None
    composite_confidence: int | None = None
    branch: str | None = None
    pr: PullRequest | None = None
    tests: TestReport | None = None
    audit_keys: list[str] = field(default_factory=list)
    notified: bool = False

    @classmethod
    def from_state(cls, state: PipelineState) -> PipelineResult:
        return cls(
            execution_id=state.execution_id,
            outcome=state.status,
            reason=state.reason,
            decision=state.decision_obj(),
            diagnosis=state.diagnosis_obj(),
            composite_confidence=state.composite,
            branch=state.branch,
            pr=state.pr_obj(),
            tests=state.tests_obj(),
            audit_keys=state.audit_keys,
            notified=state.notified,
        )


def run_pipeline(
    incident: dict[str, Any],
    services: Services,
    execution_id: str | None = None,
    store: StateStore | None = None,
) -> PipelineResult:
    s = services
    store = store or S3StateStore(s.s3, s.state_bucket_name)
    state = PipelineState(execution_id or f"exec-{uuid.uuid4().hex[:8]}", incident)

    def step(stage: Any, *args: Any) -> PipelineState:
        """One stage, the way a separate process would run it: load, work, save."""
        store.save(state)
        loaded = store.load(state.execution_id)
        updated: PipelineState = stage(loaded, *args)
        store.save(updated)
        return updated

    state = step(stages.ingest, s)
    if state.terminal:
        return PipelineResult.from_state(state)

    state = step(stages.investigate, s)
    if stages.route(state) == "investigation_only":
        state = step(stages.escalate, s, "the escalation matrix does not authorize a fix")
        return PipelineResult.from_state(state)

    state = step(stages.fix, s)
    if state.terminal:
        return PipelineResult.from_state(state)

    state = step(stages.run_tests, s)
    state = step(stages.open_pr, s)
    state = step(stages.notify_result, s)
    return PipelineResult.from_state(state)
