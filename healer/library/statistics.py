"""Three ways to call a value anomalous (Chapter 5, "The Alert That Cried Wolf 200 Times").

Z-score is the default everyone reaches for and the one that fails on skewed data. MAD
survives outliers. An exponential moving average follows a trend. Know which you are using.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def detect_anomalies_zscore(values: list[float], threshold: float = 3.0) -> list[bool]:
    """Returns True for each anomalous value.

    With n points the largest possible |z| is sqrt(n - 1), so a threshold of 3.0 can never
    fire on fewer than 11 points. The chapter's nine-point example therefore returns no
    anomalies at all, whatever the data.
    """
    mean = np.mean(values)
    std = np.std(values)
    if std == 0:
        return [False] * len(values)
    z_scores = [(x - mean) / std for x in values]
    return [bool(abs(z) > threshold) for z in z_scores]


def detect_anomalies_mad(values: list[float], threshold: float = 3.5) -> list[bool]:
    """MAD-based detection. Threshold of 3.5 is about 3 sigma for normal distributions."""
    median = np.median(values)
    deviations = [abs(x - median) for x in values]
    mad = np.median(deviations)
    if mad == 0:
        mad = np.mean(deviations) or 1.0
    modified_z_scores = [0.6745 * (x - median) / mad for x in values]
    return [bool(abs(z) > threshold) for z in modified_z_scores]


def exponential_moving_average(values: list[float], alpha: float = 0.3) -> list[float]:
    """Calculate Exponential Moving Average (EMA) of a sequence."""
    if not (0.0 < alpha < 1.0):
        raise ValueError("Alpha smoothing factor must be strictly between 0.0 and 1.0")
    if not values:
        return []
    ema = []
    current = values[0]
    for val in values:
        current = (alpha * val) + ((1.0 - alpha) * current)
        ema.append(current)
    return ema


def detect_anomalies_ema(
    values: list[float], alpha: float = 0.3, threshold_std: float = 2.5
) -> list[bool]:
    """Detect values that deviate from the trend using EMA and Median Absolute Deviation (MAD).

    The moving average is pulled toward a spike, so the points just after a spike can be
    flagged too. Lower alpha makes the trend slower to follow it.
    """
    if len(values) < 3:
        logger.warning("Telemetry data sequence too short. Skipping MAD.")
        return [False] * len(values)

    try:
        ema = exponential_moving_average(values, alpha)
        residuals = [actual - predicted for actual, predicted in zip(values, ema, strict=True)]
        median_residual = np.median(residuals)
        mad = np.median([abs(r - median_residual) for r in residuals])
        if mad == 0.0:
            mad = 1e-5
        return [bool(0.6745 * abs(r - median_residual) / mad > threshold_std) for r in residuals]
    except Exception:
        logger.exception("Failed to execute anomaly detection")
        return [False] * len(values)
