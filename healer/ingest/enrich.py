"""Attach the last log lines the alert did not carry (Chapter 2, Step 1: INGEST)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from healer.ingest.logs import last_log_lines


def make_log_fetcher(logs_client: Any) -> Callable[[dict[str, Any]], str]:
    """A fetcher for Services.fetch_logs: the last lines the service logged before the failure.

    A log outage must not stop an investigation, so any failure yields an empty string and the
    pipeline continues with less evidence (which lowers the signal-strength input).
    """

    def fetch(incident: dict[str, Any]) -> str:
        try:
            when = datetime.fromisoformat(str(incident["triggeredAt"]).replace("Z", "+00:00"))
            lines = last_log_lines(logs_client, incident["affectedService"], when)
            return "\n".join(lines)
        except Exception:  # noqa: BLE001
            return ""

    return fetch


def make_metrics_fetcher(cloudwatch: Any, max_series: int = 3) -> Callable[..., Any]:
    """A fetcher for Services.get_metrics: recent CPU and memory history from CloudWatch.

    Chapter 8 pays for metrics only when the source hints at a resource problem. This is the
    call it makes then. It looks up the series that exist (an ECS service has one per cluster
    and service), reads the last two hours at five-minute resolution, and returns a compact
    summary a model can read: the latest value and the peak.
    """

    def fetch(*, namespace: str, metrics: list[str], start: datetime, end: datetime) -> Any:
        summary: dict[str, Any] = {}
        for metric in metrics:
            found = cloudwatch.list_metrics(Namespace=namespace, MetricName=metric)["Metrics"]
            for series in found[:max_series]:
                points = cloudwatch.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric,
                    Dimensions=series["Dimensions"],
                    StartTime=start,
                    EndTime=end,
                    Period=300,
                    Statistics=["Average", "Maximum"],
                )["Datapoints"]
                if not points:
                    continue
                points.sort(key=lambda p: p["Timestamp"])
                label = ",".join(f"{d['Name']}={d['Value']}" for d in series["Dimensions"])
                summary[f"{metric}[{label}]"] = {
                    "latest_avg": round(points[-1]["Average"], 2),
                    "peak": round(max(p["Maximum"] for p in points), 2),
                    "points": len(points),
                }
        if not summary:
            raise LookupError(f"no {namespace} datapoints in the window")
        return summary

    return fetch
