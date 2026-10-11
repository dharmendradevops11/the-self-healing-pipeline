"""Chapter 12: DORA metrics, SLOs for a non-deterministic system, and the retrospective.

The printed DORA script calls GitHub and PagerDuty at import time with hard-coded token
placeholders. Here the two HTTP calls take a `get` function and a token, so the same logic runs
against your accounts, or against test data, and never runs on import.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

Get = Callable[..., Any]  # requests.get-compatible: get(url, headers=..., params=...)


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC)


def get_deployments(
    get: Get, repo: str, github_token: str, days: int = 30, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Production deployments in the window, following GitHub's pagination."""
    since = (now or datetime.now(UTC)) - timedelta(days=days)
    deployments: list[dict[str, Any]] = []
    page = 1
    while True:
        resp = get(
            f"https://api.github.com/repos/{repo}/deployments",
            headers={"Authorization": f"token {github_token}"},
            params={"environment": "production", "per_page": 100, "page": page},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        deployments += [d for d in batch if _parse(d["created_at"]) > since]
        # Stop paging once the oldest item on the page is outside the window
        if _parse(batch[-1]["created_at"]) < since:
            break
        page += 1
    return deployments


def get_incidents(
    get: Get,
    pagerduty_token: str,
    service_ids: list[str],
    days: int = 30,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Resolved incidents, scoped to the services this pipeline owns."""
    since = ((now or datetime.now(UTC)) - timedelta(days=days)).isoformat()
    incidents: list[dict[str, Any]] = []
    offset = 0
    while True:
        resp = get(
            "https://api.pagerduty.com/incidents",
            headers={"Authorization": f"Token token={pagerduty_token}"},
            params={
                "since": since,
                "statuses[]": "resolved",
                "service_ids[]": service_ids,
                "limit": 100,
                "offset": offset,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        incidents.extend(data["incidents"])
        if not data.get("more"):
            break
        offset += 100
    return incidents


def dora_summary(
    deployments: list[dict[str, Any]], incidents: list[dict[str, Any]], days: int = 30
) -> dict[str, float]:
    """Deployment frequency (per day) and mean time to recover (minutes)."""
    mttr_seconds = [
        (_parse(i["last_status_change_at"]) - _parse(i["created_at"])).total_seconds()
        for i in incidents
    ]
    mttr_minutes = sum(mttr_seconds) / len(mttr_seconds) / 60 if mttr_seconds else 0.0
    return {
        "deployment_frequency_per_day": len(deployments) / days,
        "mttr_minutes": mttr_minutes,
        "incident_count": float(len(incidents)),
    }


@dataclass
class Investigation:
    timestamp: datetime
    confidence: int
    outcome: str  # "merged_clean" | "merged_edited" | "rejected" | "investigation_only"


def compute_slo(
    investigations: list[Investigation],
    window_days: int = 30,
    confidence_floor: int = 60,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """ "Error" for an AI component means confidently wrong, not occasionally low-confidence."""
    cutoff = (now or datetime.now(UTC).replace(tzinfo=None)) - timedelta(days=window_days)
    recent = [i for i in investigations if i.timestamp > cutoff]

    high_conf = [i for i in recent if i.confidence >= confidence_floor]
    if not high_conf:
        return None

    correct = sum(1 for i in high_conf if i.outcome in ("merged_clean", "merged_edited"))
    accuracy = correct / len(high_conf)

    error_budget = 0.05  # target: no more than 5% confidently-wrong fixes
    burn_rate = (1 - accuracy) / error_budget

    return {
        "window_accuracy": round(accuracy, 3),
        "sample_size": len(high_conf),
        "burn_rate": round(burn_rate, 2),
        "alert": burn_rate > 2.0,  # burning budget 2x faster than sustainable
    }


def review_threshold_adjustment(
    bucket_stats: dict[int, dict[str, float]], current_threshold: int
) -> tuple[int, str]:
    """A recommended threshold change, conservative by design.

    bucket_stats: {confidence_bucket: {"accuracy": float, "sample_size": int}}
    """
    min_sample = 15
    accuracy_floor = 0.90

    lower_bucket = bucket_stats.get(current_threshold - 10)
    if lower_bucket and lower_bucket["sample_size"] >= min_sample:
        if lower_bucket["accuracy"] >= accuracy_floor:
            return current_threshold - 5, "lower: sustained accuracy at lower confidence"

    current_bucket = bucket_stats.get(current_threshold)
    if current_bucket and current_bucket["accuracy"] < accuracy_floor:
        return current_threshold + 10, "raise: current threshold underperforming"

    return current_threshold, "hold: insufficient evidence to change"


def bucket_stats_from_ledger(
    items: list[dict[str, Any]], bucket_size: int = 10
) -> dict[int, dict[str, float]]:
    """Accuracy per confidence bucket, from trust-ledger rows: the input to the retrospective.

    Chapter 16: "a scheduled job generates a confidence distribution report every ninety days
    as part of the quarterly pipeline review." Only rows a human has resolved count. Approved
    is correct, modified is half, rejected is wrong (the same weights the composite score uses).
    """
    points = {"approved": 1.0, "modified": 0.5, "rejected": 0.0}
    grouped: dict[int, list[float]] = {}
    for item in items:
        verdict = item.get("human_verdict")
        if verdict not in points:
            continue
        bucket = int(item["confidence_score"]) // bucket_size * bucket_size
        grouped.setdefault(bucket, []).append(points[verdict])
    return {
        bucket: {"accuracy": round(sum(v) / len(v), 3), "sample_size": len(v)}
        for bucket, v in sorted(grouped.items())
    }
