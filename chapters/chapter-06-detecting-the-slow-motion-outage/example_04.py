import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
import numpy as np

def predict_resource_exhaustion(metric_data, threshold, hours_ahead=1):
    """
    metric_data: pandas Series with datetime index and metric values,
                 resampled to regular 5-minute intervals
    threshold: the danger level (e.g., 90 for 90% disk usage)
    """
    # (1,1,1) is a good starting point: p=autoregressive, d=difference, q=moving average
    model = ARIMA(metric_data, order=(1, 1, 1))
    fitted = model.fit()

    steps = hours_ahead * 12  # 5-minute intervals
    forecast = fitted.forecast(steps=steps)
    crossing_points = np.where(forecast >= threshold)[0]

    if len(crossing_points) > 0:
        minutes_until_threshold = crossing_points[0] * 5
        return {
            'will_exhaust': True,
            'minutes_until': minutes_until_threshold,
            'predicted_value': forecast[crossing_points[0]],
            'current_value': metric_data.iloc[-1]
        }
    return {'will_exhaust': False, 'forecast': forecast}
