"""Turn a Sentry webhook into the incident the pipeline investigates (Chapter 2, Stage 1)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

PERFORMANCE_WORDS = ("timeout", "timed out", "latency", "slow", "deadline")


class UnsupportedPayloadError(ValueError):
    """The payload is not a Sentry issue or event webhook the pipeline understands."""


def _severity(level: str) -> str:
    return {"fatal": "critical", "critical": "critical", "error": "high"}.get(
        level.lower(), "medium"
    )


def _issue_type(title: str) -> str:
    lowered = title.lower()
    return "performance" if any(word in lowered for word in PERFORMANCE_WORDS) else "crash"


def _frames(event: dict[str, Any]) -> list[str]:
    """Render the exception frames of an event, oldest call first, in a traceback-like shape."""
    lines: list[str] = []
    for exc in (event.get("exception") or {}).get("values", []) or []:
        for frame in (exc.get("stacktrace") or {}).get("frames", []) or []:
            where = frame.get("filename") or frame.get("abs_path") or "?"
            lines.append(
                f'  File "{where}", line {frame.get("lineno", "?")}, '
                f"in {frame.get('function', '?')}"
            )
    return lines


def incident_from_sentry(
    payload: dict[str, Any], log_group_template: str = "/aws/ecs/{service}"
) -> dict[str, Any]:
    """Map a Sentry `issue` or `event` webhook to an incident dict."""
    data = payload.get("data") or {}
    issue = data.get("issue") or data.get("event") or {}
    if not issue:
        raise UnsupportedPayloadError("payload has neither data.issue nor data.event")
    is_issue_webhook = "issue" in data
    action = str(payload.get("action", ""))
    if is_issue_webhook and action != "created":
        # An issue webhook also fires on resolve, assign and ignore. Only a new issue is a failure.
        raise UnsupportedPayloadError(f"issue action {action!r} is not a new failure")

    title = str(issue.get("title") or (issue.get("metadata") or {}).get("value") or "unknown error")
    tags = _tags(issue)
    project = issue.get("project")
    # Issue webhooks send {"slug": ...}. Alert-rule event webhooks send a numeric project id, so
    # the service name comes from the event's own `service` tag or server_name when it has one.
    slug = project.get("slug") if isinstance(project, dict) else None
    service = str(
        tags.get("service")
        or issue.get("server_name")
        or slug
        or issue.get("project_name")
        or project
        or "unknown"
    )
    culprit = str(issue.get("culprit") or "")

    frames = _frames(data.get("event") or issue)
    stack = [title] + (["Traceback (most recent call last)"] + frames if frames else [])
    if culprit and not frames:
        stack.append(f"  at {culprit}")
    triggered = (
        issue.get("lastSeen")
        or issue.get("firstSeen")
        or _event_time(issue)
        or datetime.now(UTC).isoformat()
    )

    incident: dict[str, Any] = {
        "source": "sentry",
        "severity": _severity(str(issue.get("level", "error"))),
        "type": _issue_type(title),
        "title": title,
        "stackTrace": "\n".join(stack),
        "affectedService": service,
        "cloudwatchLogGroup": log_group_template.format(service=service),
        "triggeredAt": str(triggered),
    }
    url = issue.get("permalink") or issue.get("web_url") or issue.get("url")
    if url:
        incident["sentryIssueUrl"] = str(url)
    issue_id = issue.get("issue_id") or issue.get("id") or _issue_id_from(str(url or ""))
    if issue_id:
        incident["sentryIssueId"] = str(issue_id)
    return incident


def _tags(issue: dict[str, Any]) -> dict[str, str]:
    """Event tags arrive as [[key, value], ...] or as a dict."""
    raw = issue.get("tags") or []
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {str(t[0]): str(t[1]) for t in raw if isinstance(t, (list, tuple)) and len(t) == 2}


def _event_time(issue: dict[str, Any]) -> str | None:
    """When the error happened, from an event's `datetime` (ISO) or `timestamp` (epoch seconds)."""
    if issue.get("datetime"):
        return str(issue["datetime"])
    stamp = issue.get("timestamp")
    if isinstance(stamp, (int, float)):
        return datetime.fromtimestamp(stamp, UTC).isoformat()
    return str(stamp) if stamp else None


def _issue_id_from(url: str) -> str | None:
    match = re.search(r"/issues/(\d+)", url)
    return match.group(1) if match else None


def payload_shape(value: Any, depth: int = 3) -> Any:
    """The keys of a payload, never its values: safe to log, enough to see what Sentry sent."""
    if depth == 0 or not isinstance(value, (dict, list)):
        return type(value).__name__
    if isinstance(value, list):
        return [payload_shape(value[0], depth - 1)] if value else []
    return {k: payload_shape(v, depth - 1) for k, v in value.items()}
