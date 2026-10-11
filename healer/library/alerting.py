"""When not to alert (Chapter 3, "The Adoption Roadmap: Observe, Detect, Suggest, Act")."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Anomaly:
    metric: str
    pattern: str
    start_time: datetime
    magnitude: float
    caused_incident: bool = False


@dataclass(frozen=True)
class AlertContext:
    deployment_in_progress: bool
    deployment_time: datetime
    is_business_hours: bool


def should_alert(
    anomaly: Anomaly,
    context: AlertContext,
    find_historical_anomalies: Callable[..., list[Anomaly]],
) -> bool:
    """Suppress alerts during known change windows, expected swings and proven noise.

    `find_historical_anomalies(metric, pattern, lookback_days=30)` is injected: it is your own
    history store, which the book leaves out.
    """
    if context.deployment_in_progress:
        if anomaly.start_time < context.deployment_time + timedelta(minutes=15):
            return False

    if anomaly.metric in ["request_count", "active_users"]:
        if context.is_business_hours and anomaly.magnitude < 3.0:
            return False

    similar = find_historical_anomalies(anomaly.metric, anomaly.pattern, lookback_days=30)
    if len(similar) > 5 and all(not a.caused_incident for a in similar):
        return False

    return True
