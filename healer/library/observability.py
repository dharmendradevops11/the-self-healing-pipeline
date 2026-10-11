"""Observability building blocks (Chapter 4, "The 47 Dashboards Nobody Looked At")."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

# ------------------------------------------------------------------ structured logs


class StructuredLogger:
    """One JSON object per log line, with the ids that let you join logs, metrics and traces."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)

    def log(self, level: str, message: str, **context: Any) -> None:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "service": self.service_name,
            "level": level,
            "message": message,
            "correlation_id": context.get("correlation_id"),
            "trace_id": context.get("trace_id"),
            "user_id": context.get("user_id"),  # Hashed, not raw
            **context,
        }
        self.logger.log(getattr(logging, level), json.dumps(log_entry))


# ------------------------------------------------------------------ CloudWatch metrics


def get_metric_average(
    cloudwatch: Any,
    service_name: str,
    metric_name: str,
    start: datetime,
    end: datetime,
    namespace: str = "AWS/ECS",
) -> float:
    """Average of a metric over a window. The book uses this helper without defining it."""
    response = cloudwatch.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{"Name": "ServiceName", "Value": service_name}],
        StartTime=start,
        EndTime=end,
        Period=max(60, int((end - start).total_seconds())),
        Statistics=["Average"],
    )
    points = response.get("Datapoints", [])
    return sum(p["Average"] for p in points) / len(points) if points else 0.0


def get_metric_percentile(
    cloudwatch: Any,
    service_name: str,
    metric_name: str,
    percentile: int,
    start: datetime,
    end: datetime,
    namespace: str = "AWS/ECS",
) -> float:
    """A percentile (for example 95) of a metric over a window."""
    stat = f"p{percentile}"
    response = cloudwatch.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{"Name": "ServiceName", "Value": service_name}],
        StartTime=start,
        EndTime=end,
        Period=max(60, int((end - start).total_seconds())),
        ExtendedStatistics=[stat],
    )
    points = response.get("Datapoints", [])
    return max((p["ExtendedStatistics"][stat] for p in points), default=0.0)


# ------------------------------------------------------------------ health and correlation


def calculate_pipeline_health_score(
    cloudwatch: Any, service_name: str, now: datetime | None = None
) -> float:
    """0-100 score. <70: investigate. <50: roll back.

    Two quirks of the printed formula, reproduced as is: the weights (0.4 + 0.3 + 0.2) add up to
    0.9, so a flawless service at 200 ms p95 scores 90, not 100; and the latency component is
    not capped at 100, so a service faster than 200 ms scores higher still. Keep both in mind
    when you choose cut-offs.
    """
    end_time = now or datetime.now(UTC)
    start_time = end_time - timedelta(minutes=5)

    error_rate = get_metric_average(cloudwatch, service_name, "ErrorRate", start_time, end_time)
    error_score = max(0, 100 - (error_rate * 200))

    p95_latency = get_metric_percentile(
        cloudwatch, service_name, "Latency", 95, start_time, end_time
    )
    latency_score = max(0, 100 - ((p95_latency - 200) / 10))

    cpu = get_metric_average(cloudwatch, service_name, "CPUUtilization", start_time, end_time)
    memory = get_metric_average(cloudwatch, service_name, "MemoryUtilization", start_time, end_time)
    resource_score = 100 - max(cpu, memory)

    return round(error_score * 0.4 + latency_score * 0.3 + resource_score * 0.2, 1)


def correlate_deployment_to_metrics(
    service_name: str, deployment_time: datetime, cloudwatch: Any
) -> dict[str, Any]:
    """Did a deployment move the metrics? Compare 5 minutes after it with the 25 before."""
    baseline_start = deployment_time - timedelta(minutes=30)
    baseline_end = deployment_time - timedelta(minutes=5)
    event_start = deployment_time
    event_end = deployment_time + timedelta(minutes=5)

    baseline_errors = get_metric_average(
        cloudwatch, service_name, "ErrorRate", baseline_start, baseline_end
    )
    event_errors = get_metric_average(cloudwatch, service_name, "ErrorRate", event_start, event_end)
    baseline_latency = get_metric_percentile(
        cloudwatch, service_name, "Latency", 95, baseline_start, baseline_end
    )
    event_latency = get_metric_percentile(
        cloudwatch, service_name, "Latency", 95, event_start, event_end
    )

    error_multiplier = event_errors / max(baseline_errors, 0.01)
    latency_multiplier = event_latency / max(baseline_latency, 1)

    return {
        "correlated": error_multiplier > 2.0 or latency_multiplier > 1.5,
        "error_impact": error_multiplier,
        "latency_impact": latency_multiplier,
    }
