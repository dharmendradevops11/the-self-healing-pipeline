"""Multivariate anomaly detection for pipeline runs (Chapter 5, "Isolation Forest")."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

FEATURES = ["duration", "cpu_peak", "memory_peak", "test_failures", "artifact_size_mb"]


def train_pipeline_anomaly_detector(metrics_history: list[dict[str, Any]]) -> IsolationForest:
    """
    metrics_history: [{'duration': 245, 'cpu_peak': 67, 'memory_peak': 2.1,
                       'test_failures': 0, 'artifact_size_mb': 128}, ...]
    """
    x = np.array([[m[f] for f in FEATURES] for m in metrics_history])

    # contamination = expected proportion of outliers in training data
    model = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
    model.fit(x)
    return model


def detect_anomaly(model: IsolationForest, current_metrics: dict[str, Any]) -> tuple[bool, float]:
    """Returns (is_anomaly, anomaly_score). A lower score is more anomalous."""
    x = np.array([[current_metrics[f] for f in FEATURES]])
    prediction = model.predict(x)[0]  # 1 = normal, -1 = anomaly
    score = float(model.score_samples(x)[0])
    return (bool(prediction == -1), score)
