"""Metrics before logic: a worked memory investigation (Chapter 8, Steps 1 and 2)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

WINDOW_POINTS = 24  # 24 five-minute datapoints = 2 hours
GROWTH_THRESHOLD = 0.3
MEMORY_THRESHOLD_PCT = 70


def detect_memory_anomaly(
    cloudwatch: Any,
    service_name: str,
    lookback_hours: int = 24,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Scan CloudWatch for abnormal memory patterns: 30% growth over two hours, ending above 70%.

    Two guards the book's listing lacks: a service with no datapoints is not anomalous, and a
    window that starts at zero memory is skipped instead of dividing by zero.
    """
    end_time = now or datetime.now(UTC)
    start_time = end_time - timedelta(hours=lookback_hours)

    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/ECS",
        MetricName="MemoryUtilization",
        Dimensions=[{"Name": "ServiceName", "Value": service_name}],
        StartTime=start_time,
        EndTime=end_time,
        Period=300,
        Statistics=["Average", "Maximum"],
    )
    datapoints = sorted(response["Datapoints"], key=lambda x: x["Timestamp"])
    if not datapoints:
        return {"is_anomalous": False, "current_memory_pct": None, "growth_periods": []}

    # Rate of change over 2-hour (24-datapoint) windows
    growth_rates = []
    for i in range(len(datapoints) - WINDOW_POINTS):
        start_mem, end_mem = datapoints[i]["Average"], datapoints[i + WINDOW_POINTS]["Average"]
        if start_mem == 0:
            continue
        growth_rates.append(
            {
                "timestamp": datapoints[i + WINDOW_POINTS]["Timestamp"],
                "growth_rate": (end_mem - start_mem) / start_mem,
                "absolute_memory": end_mem,
            }
        )

    current_memory = datapoints[-1]["Average"]
    suspicious_growth = [g for g in growth_rates if g["growth_rate"] > GROWTH_THRESHOLD]

    return {
        "is_anomalous": len(suspicious_growth) > 0 and current_memory > MEMORY_THRESHOLD_PCT,
        "current_memory_pct": current_memory,
        "growth_periods": suspicious_growth,
    }


ERROR_LOG_QUERY = """
fields @timestamp, @message
| filter @message like /error/ or @message like /exception/
| sort @timestamp desc
| limit 50
"""


def correlate_memory_with_activity(
    service_name: str,
    anomaly_data: dict[str, Any],
    execute_cloudwatch_query: Callable[..., Any],
    get_recent_commits: Callable[..., Any],
) -> list[dict[str, Any]]:
    """Find what was happening in the hour around each growth period: errors and commits."""
    hypotheses = []
    for period in anomaly_data["growth_periods"]:
        window_start = period["timestamp"] - timedelta(minutes=30)
        window_end = period["timestamp"] + timedelta(minutes=30)

        logs = execute_cloudwatch_query(service_name, ERROR_LOG_QUERY, window_start, window_end)
        commits = get_recent_commits(service_name, window_start)
        hypotheses.append({"timestamp": period["timestamp"], "logs": logs, "commits": commits})
    return hypotheses
