"""Filter Amazon DevOps Guru insights down to the ones worth a human's time (Chapter 5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def fetch_and_filter_insights(
    devops_guru: Any, is_critical_resource: Callable[[dict[str, Any]], bool]
) -> list[dict[str, Any]]:
    """Get recent insights and filter out known noise patterns.

    `devops_guru` is a boto3 client. `is_critical_resource` is yours: the book leaves it out
    because "critical" is whatever you have tagged as critical.
    """
    response = devops_guru.list_insights(
        StatusFilter={"Ongoing": {"Type": "REACTIVE"}, "Closed": {"Type": "REACTIVE"}},
        MaxResults=100,
    )

    actionable_insights = []
    for insight in response["ReactiveInsights"]:
        severity = insight.get("Severity", "LOW")
        resource_collection = insight.get("ResourceCollection", {})

        # Ignore LOW severity unless it touches a resource we've tagged critical
        if severity == "LOW" and not is_critical_resource(resource_collection):
            continue
        actionable_insights.append(insight)

    return actionable_insights
