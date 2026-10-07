import logging
import numpy as np

logger = logging.getLogger(__name__)

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

def detect_anomalies_ema(values: list[float], alpha: float = 0.3,
                         threshold_std: float = 2.5) -> list[bool]:
    """Detect values that deviate from the trend using EMA and Median Absolute Deviation (MAD)."""
    if len(values) < 3:
        logger.warning("Telemetry data sequence too short. Skipping MAD.")
        return [False] * len(values)

    try:
        ema = exponential_moving_average(values, alpha)
        residuals = [actual - predicted for actual, predicted in zip(values, ema)]
        median_residual = np.median(residuals)
        mad = np.median([abs(r - median_residual) for r in residuals])
        if mad == 0.0:
            mad = 1e-5
        return [0.6745 * abs(r - median_residual) / mad > threshold_std for r in residuals]
    except Exception as e:
        logger.error(f"Failed to execute anomaly detection: {e}", exc_info=True)
        return [False] * len(values)
