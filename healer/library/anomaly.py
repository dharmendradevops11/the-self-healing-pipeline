"""Anomaly detection with an isolation forest (Chapter 3).

"Teaching Machines What 'Normal' Looks Like".

The book's listing pulls a week of request rates from Prometheus. Here the history is an
argument, so you can feed it any series, including one you made up to experiment with.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest


@dataclass(frozen=True)
class AnomalyVerdict:
    score: float
    is_anomalous: bool


def fit_isolation_forest(
    values: list[float] | np.ndarray, contamination: float = 0.05, random_state: int = 42
) -> IsolationForest:
    """Fit on history. `contamination` is the fraction you expect to be anomalous.

    0.05 is a starting point, not a constant: tune it against labeled incidents.
    """
    data = np.asarray(values, dtype=float).reshape(-1, 1)
    return IsolationForest(contamination=contamination, random_state=random_state).fit(data)


def score_current_value(
    model: IsolationForest, current_value: float, threshold: float = -0.5
) -> AnomalyVerdict:
    """Score one new observation. Lower scores are more anomalous; -0.5 is the book's threshold,
    tuned from validation data, so re-tune it for your own."""
    score = float(model.score_samples(np.array([[current_value]]))[0])
    return AnomalyVerdict(score=score, is_anomalous=score < threshold)


def build_context_features(
    values: list[float],
    hours: list[int],
    weekdays: list[int],
    deployed_recently: list[bool],
) -> np.ndarray:
    """Context-aware features (the chapter's second listing).

    A single feature cannot tell 3 AM from 3 PM. Give the model the hour, the day of week and
    whether a deploy just happened, and it can.
    """
    return np.column_stack([values, hours, weekdays, np.asarray(deployed_recently).astype(int)])
