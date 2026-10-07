import logging
import numpy as np

# Configure structured logging
logger = logging.getLogger(__name__)

def exponential_moving_average(values: list[float], alpha: float = 0.3) -> list[float]:
    """Calculate Exponential Moving Average (EMA) of a sequence.
    
    Args:
        values: Sequence of float data points.
        alpha: Smoothing factor, strictly between 0 and 1.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError("Alpha smoothing factor must be strictly between 0.0 and 1.0")
    if not values:
        return []
        
    ema = []
    current = values[0]
    for val in values:
        if not isinstance(val, (int, float)):
            raise TypeError("All input values must be numeric integers or floats")
        current = (alpha * val) + ((1.0 - alpha) * current)
        ema.append(current)
    return ema

def detect_anomalies_ema(values: list[float], alpha: float = 0.3,
                         threshold_std: float = 2.5) -> list[bool]:
    """Detect values that deviate from the trend using EMA and Median Absolute Deviation (MAD).
    
    Args:
        values: Sequence of float data points (minimum 3 required for MAD).
        alpha: Smoothing factor for the EMA trend.
        threshold_std: Deviation multiplier threshold for classification.
    """
    if len(values) < 3:
        logger.warning("Telemetry data sequence too short (< 3 points). Skipping MAD calibration.")
        return [False] * len(values)

    try:
        ema = exponential_moving_average(values, alpha)
        residuals = [actual - predicted for actual, predicted in zip(values, ema)]

        # Use MAD on residuals (robust estimator resilient to outlier contamination)
        median_residual = np.median(residuals)
        abs_deviations = [abs(r - median_residual) for r in residuals]
        mad = np.median(abs_deviations)
        
        # Prevent division-by-zero on ultra-stable baselines
        if mad == 0.0:
            logger.debug("Absolute deviation is zero. Setting default epsilon floor.")
            mad = 1e-5
            
        # Standard Z-score calculation based on MAD scaling factor
        return [0.6745 * abs(r - median_residual) / mad > threshold_std for r in residuals]
    except Exception as e:
        logger.error(f"Failed to execute anomaly detection: {e}", exc_info=True)
        # Fail safe: return no anomalies
        return [False] * len(values)
