"""AWS Lambda entry points (Figure 2.1).

The webhook receiver, INGEST, the gate's route step, PR and NOTIFY.

INVESTIGATE, FIX and TEST need git and minutes of runtime, so they are Fargate tasks
(`healer.tasks`). Everything here is short and needs no git binary.
"""

from __future__ import annotations

import json
import uuid
from functools import lru_cache
from typing import Any

from healer import stages
from healer.config import Settings, build_services
from healer.guardrails.secrets import get_secret
from healer.ingest.sentry import UnsupportedPayloadError, incident_from_sentry, payload_shape
from healer.ingest.webhook import authenticate_webhook, validate_signature
from healer.ledger.feedback import apply_pr_outcome
from healer.services import Services
from healer.state import PipelineState, S3StateStore


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def _services() -> Services:
    return build_services(_settings())


def _store(s: Services) -> S3StateStore:
    return S3StateStore(s.s3, s.state_bucket_name)


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# --------------------------------------------------------------------------- webhook


def webhook_handler(
    event: dict[str, Any],
    context: Any = None,
    *,
    settings: Settings | None = None,
    secrets_client: Any = None,
    sns_client: Any = None,
) -> dict[str, Any]:
    """API Gateway -> verify the signature, reject replays, publish the incident to SNS."""
    import boto3

    cfg = settings or _settings()
    secrets = secrets_client or boto3.client("secretsmanager")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

    # The secret is read at the moment of use, never from the environment (Chapter 11).
    current = get_secret(secrets, cfg.webhook_secret_arn) if cfg.webhook_secret_arn else ""
    previous = (
        get_secret(secrets, cfg.previous_webhook_secret_arn)
        if cfg.previous_webhook_secret_arn
        else None
    )
    stamp = headers.get("sentry-hook-timestamp")
    result = authenticate_webhook(
        event,
        headers.get("sentry-hook-signature", ""),
        current,
        previous,
        rotated_at=None
        if previous is None
        else float(headers.get("x-secret-rotated-at", 0) or 0) or None,
        timestamp=float(stamp) if stamp else None,
    )
    if not result.accepted:
        return _response(result.status_code, {"error": result.reason})

    print(
        json.dumps(
            {
                "hop": "webhook->received",
                "action": (result.payload or {}).get("action"),
                "shape": payload_shape(result.payload or {}),
            }
        ),
        flush=True,
    )
    try:
        incident = incident_from_sentry(result.payload or {})
    except UnsupportedPayloadError as exc:
        return _response(
            200, {"ignored": str(exc)}
        )  # a webhook type we do not act on is not an error

    execution_id = f"exec-{uuid.uuid4().hex[:8]}"
    published = (sns_client or boto3.client("sns")).publish(
        TopicArn=cfg.trigger_topic_arn,
        Message=json.dumps({"executionId": execution_id, "incident": incident}),
    )
    message_id = published.get("MessageId") if isinstance(published, dict) else None
    # One line per hop, so a run can be followed from the front door onward (scripts/trace.py).
    print(
        json.dumps(
            {
                "hop": "webhook->sns",
                "execution_id": execution_id,
                "sns_message_id": message_id,
                "topic": cfg.trigger_topic_arn,
                "service": incident.get("affectedService"),
                "title": str(incident.get("title"))[:120],
            }
        ),
        flush=True,
    )
    return _response(202, {"executionId": execution_id, "snsMessageId": message_id})


def github_webhook_handler(
    event: dict[str, Any],
    context: Any = None,
    *,
    settings: Settings | None = None,
    secrets_client: Any = None,
    dynamodb: Any = None,
) -> dict[str, Any]:
    """GitHub tells us a pull request closed. Record what the human decided (Chapter 9)."""
    import boto3

    cfg = settings or _settings()
    secrets = secrets_client or boto3.client("secretsmanager")
    if not cfg.github_webhook_secret_arn:
        return _response(401, {"error": "no webhook secret is configured"})  # fail closed
    secret = get_secret(secrets, cfg.github_webhook_secret_arn).encode()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    verdict = validate_signature(event, secret, headers.get("x-hub-signature-256", ""))
    if verdict["statusCode"] != 200:
        return _response(int(verdict["statusCode"]), {"error": verdict["body"]})
    if headers.get("x-github-event") != "pull_request":
        return _response(200, {"ignored": "not a pull_request event"})
    try:
        raw = event["body"]
        if event.get("isBase64Encoded"):
            import base64

            raw = base64.b64decode(raw).decode("utf-8")
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return _response(400, {"error": "body is not JSON"})
    resource = dynamodb or boto3.resource("dynamodb")
    outcome = apply_pr_outcome(resource, payload, cfg.ledger_table, cfg.history_table)
    print(json.dumps({"hop": "github->ledger", **outcome}), flush=True)  # the evidence for this hop
    return _response(200, outcome)


# ---------------------------------------------------------------- state machine steps


def ingest_handler(
    event: dict[str, Any], context: Any = None, services: Services | None = None
) -> dict[str, Any]:
    """Step 1: INGEST. Starts the run's state, then rate-limits, classifies and attaches logs."""
    s = services or _services()
    store = _store(s)
    state = stages.ingest(PipelineState(event["executionId"], event["incident"]), s)
    store.save(state)
    return {"executionId": state.execution_id, "status": state.status, "reason": state.reason}


def route_handler(
    event: dict[str, Any], context: Any = None, services: Services | None = None
) -> dict[str, Any]:
    """The gate: what may the pipeline do next? Also reports whether the run already ended."""
    s = services or _services()
    state = _store(s).load(event["executionId"])
    return {
        "executionId": state.execution_id,
        "status": state.status,
        "fixAction": stages.route(state),
    }


def pr_handler(
    event: dict[str, Any], context: Any = None, services: Services | None = None
) -> dict[str, Any]:
    """Step 4: PR. Commits the reviewer packet and opens the pull request."""
    s = services or _services()
    store = _store(s)
    state = stages.open_pr(store.load(event["executionId"]), s)
    store.save(state)
    return {"executionId": state.execution_id, "status": state.status}


def notify_handler(
    event: dict[str, Any], context: Any = None, services: Services | None = None
) -> dict[str, Any]:
    """Notify. mode is result (a PR waits), escalate (a human decides) or failure (a crash)."""
    s = services or _services()
    store = _store(s)
    mode = event.get("mode", "result")
    try:
        state = store.load(event["executionId"])
    except Exception:  # noqa: BLE001
        if mode != "failure" or "incident" not in event:
            raise
        # The stage crashed before it saved anything (found on real AWS: INGEST failed first).
        # A human must still hear about it, so start the record from the incident itself.
        state = PipelineState(event["executionId"], event["incident"])
    if mode == "escalate":
        state = stages.escalate(
            state, s, event.get("reason", "the escalation matrix does not authorize a fix")
        )
    elif mode == "failure":
        error = event.get("error") or {}
        state = stages.report_failure(
            state,
            s,
            str(event.get("stage", "unknown")),
            str(error.get("Cause") or error.get("Error") or "unknown error"),
        )
    else:
        state = stages.notify_result(state, s)
    store.save(state)
    return {"executionId": state.execution_id, "status": state.status}
