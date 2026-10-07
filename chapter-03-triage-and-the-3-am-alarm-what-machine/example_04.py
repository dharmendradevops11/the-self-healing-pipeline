import logging

logger = logging.getLogger(__name__)

def find_delayed_effects(event_times: list[int], metric_anomalies: list[bool],
                         max_lag_minutes: int = 60) -> list[tuple[int, float]]:
    """For each time lag, measure how much more likely a metric anomaly is
    in the minutes following an event than it is overall (lift).
    A lift well above 1.0 at a consistent lag suggests the event
    precedes the anomaly."""
    n = len(metric_anomalies)
    if n < 10 or not event_times:
        logger.warning("Not enough data for a meaningful lift estimate.")
        return []

    base_rate = sum(metric_anomalies) / n
    if base_rate == 0.0:
        logger.info("No anomalies in this series; nothing to correlate.")
        return []

    results = []
    for lag in range(0, max_lag_minutes, 5):
        hits = 0
        windows = 0
        for event_time in event_times:
            index = event_time + lag
            if 0 <= index < n:
                windows += 1
                if metric_anomalies[index]:
                    hits += 1
        if windows < 5:
            continue  # too few observations at this lag to trust
        lift = (hits / windows) / base_rate
        if lift > 2.0:
            results.append((lag, round(lift, 2)))

    return results
