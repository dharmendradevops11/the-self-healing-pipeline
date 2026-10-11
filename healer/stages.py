"""The stages of Figure 2.1, each one runnable on its own.

    ingest -> investigate (+ gate) -> route --(fix authorized)--> fix -> run_tests
                                                                   -> open_pr -> notify_result
                                          \\--(otherwise)--> escalate (report-only PR + message)

A stage takes the PipelineState and the injected Services, does its work, and returns the
updated state. It can run in-process, in a Lambda, or in a Fargate container: the only thing
shared between stages is the state saved to the store.
"""

from __future__ import annotations

import datetime
import json
import re
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from healer.fix.generate import fix_context, generate_fix
from healer.fix.remediation import apply_remediation, diff_summary
from healer.gate import compute_confidence, compute_signal_strength, decide
from healer.gate.confidence import SignalEvidence
from healer.gate.human_review import human_review_flags
from healer.guardrails.classifier import classify_payload
from healer.guardrails.phases import (
    AutonomyLimits,
    Phase,
    PhaseController,
    ShadowRecord,
    record_shadow,
)
from healer.guardrails.sanitizer import sanitize_for_prompt
from healer.guardrails.scrubber import scrub_sensitive_data, summarise_error
from healer.guardrails.validator import check_constraints
from healer.ingest.logs import last_lines
from healer.ingest.rate_limiter import claim_issue, hour_bucket, try_acquire_investigation_slot
from healer.investigate import investigate_failure
from healer.ledger.audit import AgentAuditLogger
from healer.ledger.remediation_history import (
    RemediationRecord,
    record_remediation,
    recurrences_of,
)
from healer.ledger.trust_ledger import historical_success_rate, record_outcome
from healer.notify.notifiers import build_message
from healer.pr.hosts import build_labels
from healer.pr.packet import build_reviewer_packet
from healer.services import Services
from healer.state import PipelineState
from healer.telemetry import timed
from healer.test.runner import run_checks


def category_of(event: dict[str, Any]) -> str:
    """The failure category the trust ledger tracks, for example `crash:AttributeError`."""
    error_class = event["title"].split(":")[0].strip()
    ok = re.fullmatch(r"[A-Za-z]+(Error|Exception)", error_class)
    return f"{event.get('type', 'crash')}:{error_class if ok else 'unknown'}"


def _compact(value: Any, limit: int = 200) -> Any:
    """Shorten long text field by field, so a log line stays valid JSON and never ends mid-value."""
    if isinstance(value, dict):
        return {k: _compact(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_compact(v, limit) for v in value[:10]]
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [{len(value)} chars]"
    return value


def _audit(state: PipelineState, s: Services) -> Callable[..., None]:
    """A logger that continues the step numbering earlier stages left in S3."""
    logger = AgentAuditLogger.resume(s.s3, s.audit_bucket, state.execution_id)

    def log(step: str, i: Any, o: Any, confidence: int | None = None) -> None:
        state.audit_keys.append(logger.log_reasoning_step(step, i, o, confidence=confidence))
        # The same step, one line in the stage's own log, so a run reads top to bottom in
        # CloudWatch (scripts/trace.py). Outputs here are already sanitised and scrubbed.
        print(
            json.dumps(
                {
                    "execution_id": state.execution_id,
                    "step": step,
                    "confidence": confidence,
                    "output": _compact(o),
                }
            ),
            flush=True,
        )

    return log


def _packet(
    state: PipelineState, files: list[str], summary: str, tests_run: list[str], commit: str | None
) -> str:
    diagnosis, decision = state.diagnosis_obj(), state.decision_obj()
    assert diagnosis is not None and decision is not None
    return build_reviewer_packet(
        event=state.incident,
        execution_id=state.execution_id,
        root_cause=diagnosis.root_cause_hypothesis,
        confidence=state.composite or 0,
        evidence=diagnosis.evidence_summary or "stack trace and source",
        decision=decision,
        files_changed=files,
        diff_summary=summary,
        tests_run=tests_run,
        fix_commit=commit,
    )


# ------------------------------------------------------------------------ 1. INGEST


@timed("ingest")
def ingest(state: PipelineState, s: Services) -> PipelineState:
    """Rate-limit the flood, run the guardrail classifier, keep the last 20 log lines."""
    log = _audit(state, s)
    incident = state.incident
    table = s.dynamodb.Table(s.rate_table_name)
    issue_id = incident.get("sentryIssueId")
    if issue_id and not claim_issue(table, str(issue_id)):
        state.status = "duplicate"
        state.reason = f"Sentry issue {issue_id} is already being handled"
        log("ingest", {"service": state.service}, {"outcome": "duplicate", "issue": issue_id})
        return state
    if not try_acquire_investigation_slot(
        table, state.service, hour_bucket(), limit=s.investigations_per_hour
    ):
        state.status, state.reason = "rate_limited", "investigation limit reached for this hour"
        log("ingest", {"service": state.service}, {"outcome": "rate_limited"})
        return state

    if not incident.get("logs") and s.fetch_logs is not None:
        incident["logs"] = s.fetch_logs(
            incident
        )  # INGEST attaches the logs the alert did not carry

    untrusted = f"{incident['title']}\n{incident.get('stackTrace', '')}\n{incident.get('logs', '')}"
    if s.guardrail_llm is not None:
        verdict = classify_payload(s.guardrail_llm, sanitize_for_prompt(untrusted))
        if verdict.malicious:
            # A MALICIOUS verdict is worth acting on: stop before the main prompt sees it.
            state.status = "blocked"
            state.reason = "the guardrail classifier flagged the payload"
            log("guardrail", {"verdict": verdict.raw}, {"outcome": "blocked"})
            return state

    state.log_lines = last_lines(incident.get("logs", "").splitlines(), s.log_lines)
    log(
        "ingest",
        {"service": state.service, "log_lines": len(state.log_lines)},
        {"outcome": "accepted"},
    )
    return state


# ---------------------------------------------------- 2. INVESTIGATE, then the gate


@timed("investigate")
def investigate(state: PipelineState, s: Services) -> PipelineState:
    """Clone, read, ask the model, then blend its certainty into a composite score and decide."""
    log = _audit(state, s)
    incident = state.incident
    git, _ = s.open_repo()
    when = datetime.datetime.fromisoformat(incident["triggeredAt"].replace("Z", "+00:00"))
    investigation = investigate_failure(
        {
            "log_stream": incident.get("stackTrace", ""),
            "repo": state.service,
            "timestamp": when,
            "message": incident["title"],
        },
        s.llm,
        read_file=lambda repo, path: git.read_file(path),
        get_git_history=lambda **kw: git.log_for(kw["file_paths"]),
        get_cloudwatch_metrics=s.get_metrics,
        get_recent_deployment=git.recent_deployment,
        get_dependency_changes=git.dependency_changes,
        log_context="\n".join(state.log_lines),
        log_line_count=len(state.log_lines),
    )
    diagnosis = investigation.diagnosis
    state.diagnosis = asdict(diagnosis)
    state.evidence = asdict(investigation.evidence)
    state.degraded = investigation.degraded

    def exists(path: str) -> bool:
        try:
            git.read_file(path)
            return True
        except (OSError, PermissionError):
            return False

    state.constraint_problems = check_constraints(diagnosis.affected_files, exists)

    # the gate: composite confidence, blast radius, escalation matrix (Chapter 9)
    state.category = category_of(incident)
    state.history = historical_success_rate(s.dynamodb, state.category, table_name=s.ledger_table)
    state.signal = compute_signal_strength(investigation.evidence)
    state.composite = compute_confidence(
        state.signal, diagnosis.confidence_score / 100, state.history
    )
    decision = decide(
        state.service, state.composite, s.registry, s.unknown_service_tier, s.fix_threshold
    )
    state.decision = decision.to_dict()
    state.review_flags = human_review_flags(
        decision.blast_radius["tier"],
        state.history,
        recurrences_of(s.dynamodb, state.service, table_name=s.history_table),
        diagnosis.affected_files,
        decision.owner,
    )
    state.review_flags += state.constraint_problems
    log(
        "investigate",
        {"files": list(investigation.source_files), "degraded": investigation.degraded},
        {
            "root_cause": diagnosis.root_cause_hypothesis,
            "model_certainty": diagnosis.confidence_score,
            "signal": round(state.signal, 3),
            "history": state.history,
            "composite": state.composite,
            "decision": decision.to_dict(),
        },
        confidence=state.composite,
    )
    return state


def route(state: PipelineState) -> str:
    """What the escalation matrix lets the pipeline do. Fails closed if there is no decision."""
    decision = state.decision_obj()
    return decision.fix_action if decision else "investigation_only"


# ------------------------------------------------------------------- escalate / notify


def _open_report_pr(state: PipelineState, s: Services, reason: str, packet: str) -> str | None:
    """Below the fix threshold the pipeline is a detective (Chapters 1, 2, 18): it pushes a branch
    holding only HEALER_REPORT.md and opens a pull request. No source file changes.

    Returns a note when the pull request could not be opened. The Slack message still goes out.
    """
    from healer.fix.remediation import slugify
    from healer.gate import Decision

    decision = state.decision_obj()
    assert isinstance(decision, Decision)
    suffix = state.execution_id.split("-")[-1][-6:]
    branch = (
        f"healer/{s.today or datetime.date.today()}-{slugify(state.incident['title'])}-{suffix}"
    )
    try:
        s.pr_host.create_branch(branch, s.base_branch)  # the API: the Escalate step is a Lambda
        s.pr_host.commit_file(
            branch,
            "HEALER_REPORT.md",
            packet,
            "chore(healer): investigation report\n\nNo code fix generated.",
        )
        labels = build_labels(decision, state.composite or 0, human_review=bool(state.review_flags))
        if "healer: investigation-only" not in labels:
            labels.append("healer: investigation-only")
        pr = s.pr_host.open_pull_request(
            title=f"[HEALER] investigation: {state.incident['title'][:70]}",
            body=(
                "## Self-Healing Pipeline: Investigation only\n\n"
                f"No source code was changed. {reason}\n\n"
                f"Composite confidence {state.composite}/100 ({decision.band}), blast radius "
                f"{decision.blast_radius['tier']}, action `{decision.fix_action}`.\n\n"
                f"### Reviewer packet\n\n```yaml\n{packet}```\n\n"
                f"_Execution: `{state.execution_id}`_\n"
            ),
            branch=branch,
            base=s.base_branch,
            labels=labels,
            draft=False,
        )
    except Exception as exc:  # the human must still hear about it
        return f"the report PR could not be opened ({type(exc).__name__}: {str(exc)[:120]})"
    state.branch, state.pr = branch, asdict(pr)
    return None


@timed("escalate")
def escalate(
    state: PipelineState,
    s: Services,
    reason: str,
    outcome: str = "escalated",
    open_report: bool = True,
) -> PipelineState:
    """Hand the analysis to a human: an investigation-only PR (HEALER_REPORT.md) plus a message.

    The book says both. The prose (Chapters 1, 2, 18) opens a report-only PR below the fix
    threshold. Figure 2.1 shows the Escalate/Slack branch. The message carries the PR link.
    """
    log = _audit(state, s)
    diagnosis, decision = state.diagnosis_obj(), state.decision_obj()
    assert diagnosis is not None and decision is not None
    packet = _packet(state, [], "No code change: investigation only", ["not run"], None)
    note = _open_report_pr(state, s, reason, packet) if open_report else None
    pr = state.pr_obj()
    subject, body = build_message(
        decision=decision,
        service=state.service,
        title=state.incident["title"],
        root_cause=diagnosis.root_cause_hypothesis,
        confidence=state.composite or 0,
        escalated=True,
        packet=packet,
        pr_url=pr.url if pr else None,
        review_flags=state.review_flags,
    )
    s.notifier.send(subject, body + (f"\n{note}" if note else ""), decision)
    state.status, state.reason, state.notified = outcome, reason, True
    record_outcome(
        s.dynamodb,
        state.execution_id,
        diagnosis.root_cause_hypothesis,
        state.composite or 0,
        "pending",
        None,
        category=state.category,
        table_name=s.ledger_table,
    )
    log(
        "escalate",
        {"reason": reason},
        {"notified": decision.recipient, "pr": pr.url if pr else note},
        confidence=state.composite,
    )
    return state


def report_failure(state: PipelineState, s: Services, stage: str, error: str) -> PipelineState:
    """A stage crashed. Tell a human, plainly, and stop. No fix is attempted."""
    log = _audit(state, s)
    decision = decide(state.service, 0, s.registry, s.unknown_service_tier)
    subject = f"[{decision.tier.upper()}] [Healer] {state.service}: pipeline error in {stage}"
    # What goes to a chat channel is the short, redacted form: no ARNs, no account number, no stack.
    # The full error stays in the stage's log and the audit file.
    summary = summarise_error(error)
    body = (
        f"The self-healing pipeline hit an error in the {stage} stage and stopped.\n"
        f"Service: {state.service}\nIssue: {state.incident.get('title', '')}\n"
        f"Error: {summary}\nExecution: {state.execution_id}"
    )
    s.notifier.send(subject, body, decision)
    state.status, state.reason, state.notified = (
        "escalated",
        f"error in {stage}: {summary[:200]}",
        True,
    )
    log("failure", {"stage": stage}, {"error": error[:500]})
    return state


@timed("notify")
def notify_result(state: PipelineState, s: Services) -> PipelineState:
    """Tell the owner a pull request is waiting."""
    diagnosis, decision, pr = state.diagnosis_obj(), state.decision_obj(), state.pr_obj()
    assert diagnosis is not None and decision is not None and pr is not None
    subject, message = build_message(
        decision=decision,
        service=state.service,
        title=state.incident["title"],
        root_cause=diagnosis.root_cause_hypothesis,
        confidence=state.composite or 0,
        pr_url=pr.url,
        review_flags=state.review_flags,
    )
    s.notifier.send(subject, message, decision)
    state.notified = True
    return state


# ---------------------------------------------------------------------------- 3. FIX


@timed("fix")
def fix(state: PipelineState, s: Services) -> PipelineState:
    """Ask for a patch, check it against the allowlist, apply it on a healer/ branch."""
    log = _audit(state, s)
    diagnosis, decision = state.diagnosis_obj(), state.decision_obj()
    assert diagnosis is not None and decision is not None
    git, _ = s.open_repo()

    sources: dict[str, str] = {}
    for path in diagnosis.affected_files:
        try:
            sources[path] = git.read_file(path)
        except (OSError, PermissionError):
            continue
    context = fix_context(sources, diagnosis.affected_files)
    tests: dict[str, str] = {}
    for path in git.related_tests(list(context)):
        try:
            tests[path] = git.read_file(path)[:6000]  # reference only, and bounded
        except (OSError, PermissionError):
            continue
    proposal = generate_fix(
        s.llm, diagnosis.root_cause_hypothesis, diagnosis.evidence_summary, context, tests
    )
    state.proposal = asdict(proposal)
    log(
        "fix",
        {"files": list(context), "tests_shown": list(tests)},
        {"type": proposal.type, "files": proposal.affected_files},
    )
    if not proposal.is_code_fix:
        return escalate(
            state, s, f"the model did not produce a code fix: {proposal.explanation[:120]}"
        )

    if s.phase is Phase.SHADOW:
        key = record_shadow(
            s.s3,
            s.audit_bucket,
            ShadowRecord(
                state.execution_id,
                state.service,
                "open_pr",
                diagnosis.root_cause_hypothesis,
                state.composite or 0,
                decision.blast_radius["tier"],
                proposal.affected_files,
            ),
        )
        state.status, state.reason = "shadow", f"shadow mode: recorded at {key}"
        record_outcome(
            s.dynamodb,
            state.execution_id,
            diagnosis.root_cause_hypothesis,
            state.composite or 0,
            "pending",
            None,
            category=state.category,
            table_name=s.ledger_table,
        )
        return state

    plan = PhaseController(s.phase, s.throttle).plan(decision)
    state.plan_action = f"{plan.action}: {plan.reason}"
    if plan.action == "cap_reached":
        return escalate(state, s, plan.reason, outcome="cap_reached", open_report=False)

    applied = apply_remediation(
        proposal.diff,
        proposal.affected_files,
        git,
        base=s.base_branch,
        today=s.today,
        suffix=state.execution_id.split("-")[-1][-6:],
    )
    log(
        "remediate",
        {"files": proposal.affected_files},
        {k: v for k, v in applied.items() if k != "rollback"},
    )
    if not applied["applied"]:
        return escalate(state, s, f"the fix could not be applied safely: {applied['reason']}")
    state.branch = applied["branch"]
    state.fix_commit = git.head_sha()
    return state


# --------------------------------------------------------------------------- 3b. TEST


@timed("test")
def run_tests(state: PipelineState, s: Services) -> PipelineState:
    """Type-check, unit tests and lint, on the branch the FIX stage pushed."""
    log = _audit(state, s)
    assert state.branch is not None
    git, repo_path = s.open_repo()
    git.checkout_remote_branch(state.branch)
    report = run_checks(repo_path, s.check_commands, setup=s.setup_commands)
    state.tests = {"checks": [asdict(c) for c in report.checks]}
    # The checks' own output, so a reader sees the passing tests and not only the word "pass".
    # Bounded to the last 1500 characters and scrubbed of secrets, like everything we log.
    for check in report.checks:
        tail = scrub_sensitive_data(check.output.strip()[-1500:])
        print(f"[test:{check.name}] {check.status}\n{tail}", flush=True)
    log(
        "test",
        {"branch": state.branch},
        {
            "checks": report.summary(),
            "passed": report.overall_passed,
            "output": {
                c.name: scrub_sensitive_data(c.output.strip()[-1500:]) for c in report.checks
            },
        },
    )
    return state


# ----------------------------------------------------------------------------- 4. PR


@timed("pr")
def open_pr(state: PipelineState, s: Services) -> PipelineState:
    """Attach the reviewer packet to the branch and open the pull request."""
    log = _audit(state, s)
    diagnosis, decision = state.diagnosis_obj(), state.decision_obj()
    tests, proposal = state.tests_obj(), state.proposal
    assert diagnosis and decision and tests and proposal and state.branch
    files = list(proposal["affected_files"])
    diff_lines = len(str(proposal["diff"]).splitlines())
    labels = build_labels(
        decision,
        state.composite or 0,
        large_diff=diff_lines > 400,
        human_review=bool(state.review_flags),
    )

    autonomy = ""
    if s.phase is Phase.AUTONOMOUS:
        problems = AutonomyLimits().violations(
            len(files), diff_lines, tests.overall_passed, stable_for_an_hour=True
        )
        autonomy = (
            "within the autonomous limits"
            if not problems
            else "outside the autonomous limits: " + "; ".join(problems)
        )

    summary = str(proposal["explanation"]).split("\n")[0] or diff_summary(str(proposal["diff"]))
    packet = _packet(state, files, summary, tests.summary(), state.fix_commit)
    s.pr_host.commit_file(
        state.branch, "HEALER_REPORT.md", packet, "chore(healer): add reviewer packet"
    )

    incident = state.incident
    body = (
        f"## Self-Healing Pipeline: Fix\n\n**Issue:** {incident['title']}\n"
        f"**Service:** {state.service}\n\n### Routing decision\n\n"
        f"Composite confidence {state.composite}/100 ({decision.band}), "
        f"blast radius {decision.blast_radius['tier']}, "
        f"action `{decision.fix_action}`. Escalation: {decision.tier} -> {decision.recipient}.\n"
        f"{('Autonomy: ' + autonomy) if autonomy else ''}\n\n"
        + "".join(f"> **Human review required:** {flag}\n" for flag in state.review_flags)
        + "\n"
        f"### Reviewer packet\n\n```yaml\n{packet}```\n\n"
        f"### Test results\n\n"
        + "\n".join(f"- {line}" for line in tests.summary())
        + (
            "\n\nSome checks failed. Review carefully."
            if not tests.overall_passed
            else "\n\nAll checks passed."
        )
        + f"\n\n_Execution: `{state.execution_id}`_\n"
    )
    pr = s.pr_host.open_pull_request(
        title=f"[HEALER] fix: {incident['title'][:70]}",
        body=body,
        branch=state.branch,
        base=s.base_branch,
        labels=labels,
        draft=not tests.overall_passed,
    )
    state.pr = asdict(pr)
    log(
        "pr", {"branch": state.branch}, {"pr": pr.url, "labels": labels}, confidence=state.composite
    )

    record_outcome(
        s.dynamodb,
        state.execution_id,
        diagnosis.root_cause_hypothesis,
        state.composite or 0,
        "pending",
        None,
        category=state.category,
        table_name=s.ledger_table,
    )
    record_remediation(
        s.dynamodb,
        RemediationRecord(
            incident_id=state.execution_id,
            service=state.service,
            root_cause_hypothesis=diagnosis.root_cause_hypothesis,
            confidence_score=state.composite or 0,
            remediation_type="repair",
            files_changed=files,
            test_results={c.name: c.status for c in tests.checks},
        ),
        table_name=s.history_table,
    )
    state.status, state.reason = "pr_opened", state.plan_action
    return state


__all__ = [
    "SignalEvidence",
    "category_of",
    "escalate",
    "fix",
    "ingest",
    "investigate",
    "notify_result",
    "report_failure",
    "open_pr",
    "route",
    "run_tests",
]
