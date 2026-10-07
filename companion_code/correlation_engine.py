import logging
import numpy as np
from scipy.stats import pearsonr

logger = logging.getLogger(__name__)

def find_delayed_correlations(event_times: list[int], metric_timeseries: list[float], 
                              max_lag_minutes: int = 60) -> list[tuple[int, float, float]]:
    """Find correlations between discrete events and metric changes at various time lags.
    
    Args:
        event_times: Indices of events inside telemetry windows.
        metric_timeseries: Floating-point metric values to analyze.
        max_lag_minutes: Max lag window boundaries to analyze.
    """
    if len(metric_timeseries) < 10:
        logger.warning("Metric timeseries too short for statistical significance.")
        return []
        
    # Prevent execution on zero variance metrics (scipy pearsonr raises ConstantInputWarning)
    if np.var(metric_timeseries) == 0.0:
        logger.info("Metric timeseries has zero variance. Correlation cannot be calculated.")
        return []

    correlations = []
    # Step in 5-minute increments
    for lag in range(0, max_lag_minutes, 5):
        try:
            event_series = np.zeros(len(metric_timeseries))
            for event_time in event_times:
                index = event_time + lag
                if 0 <= index < len(event_series):
                    event_series[index] = 1.0
                    
            if event_series.sum() > 0:
                corr, p_value = pearsonr(event_series, metric_timeseries)
                
                # Check for standard statistical significance thresholds (p < 0.05)
                if abs(corr) > 0.3 and p_value < 0.05:
                    correlations.append((lag, float(corr), float(p_value)))
        except Exception as e:
            logger.error(f"Error evaluating lag window correlation at T+{lag}: {e}")
            
    return correlations
