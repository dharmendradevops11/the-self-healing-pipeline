"""Fetch only the logs that matter (Chapter 4, "The Self-Healing Blocker").

Diagnosis needs the minimal context around the failure, not the whole history. Both queries
are bounded in time and in count.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def fetch_relevant_logs(
    logs_client: Any, log_group: str, failure_time: int, window_seconds: int = 120, limit: int = 100
) -> str:
    """Logs from two minutes before the failure up to it, as one block of text.

    `failure_time` is epoch seconds. The book's listing also takes a task ARN it never uses,
    so it is left out here. `logs_client` is a boto3 CloudWatch Logs client.
    """
    response = logs_client.filter_log_events(
        logGroupName=log_group,
        startTime=(failure_time - window_seconds) * 1000,
        endTime=failure_time * 1000,
        limit=limit,  # Bounded: we don't need the entire history
    )
    return "\n".join(f"[{e['timestamp']}] {e['message']}" for e in response["events"])


def get_relevant_logs(
    logs_client: Any, service_name: str, failure_timestamp: datetime, limit: int = 100
) -> list[str]:
    """ERROR and FATAL lines from two minutes before to one minute after the failure."""
    start_time = failure_timestamp - timedelta(minutes=2)
    end_time = failure_timestamp + timedelta(minutes=1)
    response = logs_client.filter_log_events(
        logGroupName=f"/aws/ecs/{service_name}",
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000),
        filterPattern="[level=ERROR || level=FATAL]",  # only the lines that carry signal
        limit=limit,  # Cap it: we don't need the entire crash dump
    )
    return [str(event["message"]) for event in response["events"]]


def last_log_lines(
    logs_client: Any,
    service_name: str,
    failure_timestamp: datetime,
    count: int = 20,
    window_minutes: int = 10,
    group_template: str = "/aws/ecs/{service}",
) -> list[str]:
    """The last `count` lines the service wrote up to the failure, of every level.

    Chapter 2: "the last 20 CloudWatch log lines for the affected service". Found on real
    CloudWatch: `get_relevant_logs` above, with the book's printed pattern `[level=ERROR ||
    level=FATAL]`, returns nothing for ordinary log lines. A space-delimited pattern with one field
    only matches events that have exactly one word, so a line such as `2026-10-09T20:50:01Z ERROR
    request failed` never matches. This takes everything in the window and keeps the newest lines,
    which also shows the INFO and WARN lines that led up to the error.
    """
    end_ms = int((failure_timestamp + timedelta(minutes=1)).timestamp() * 1000)
    start_ms = int((failure_timestamp - timedelta(minutes=window_minutes)).timestamp() * 1000)
    events: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {
        "logGroupName": group_template.format(service=service_name),
        "startTime": start_ms,
        "endTime": end_ms,
    }
    for _ in range(10):  # bounded: at most ten pages
        page = logs_client.filter_log_events(**kwargs)
        events += page.get("events", [])
        token = page.get("nextToken")
        if not token:
            break
        kwargs["nextToken"] = token
    events.sort(key=lambda e: e["timestamp"])
    return [str(e["message"]).rstrip() for e in events[-count:]]


def last_lines(lines: list[str], count: int = 20) -> list[str]:
    """The pipeline attaches the last 20 log lines to every investigation (Chapter 2)."""
    return lines[-count:]
