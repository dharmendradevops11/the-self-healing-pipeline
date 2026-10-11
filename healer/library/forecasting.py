"""Detecting the slow-motion outage (Chapter 6).

A threshold alert fires when you are already in trouble. A forecast fires while there is still
time to plan: three days before the disk fills, not three minutes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.arima.model import ARIMA

Alert = Callable[..., Any]

SECONDS_PER_DAY = 86400.0


def check_redis_memory(current_memory_pct: float, send_alert: Alert, threshold: float = 85) -> bool:
    """Reactive: alert when memory exceeds a threshold, when you are already in trouble."""
    if current_memory_pct > threshold:
        send_alert(severity="critical", message=f"Redis memory at {current_memory_pct}%")
        return True
    return False


def predict_redis_exhaustion(
    memory_history: list[tuple[float, float]], send_alert: Alert | None = None
) -> int | None:
    """
    memory_history: list of (timestamp, memory_pct) tuples
    Returns: days until memory hits 95%, or None if the trend is safe.
    """
    if len(memory_history) < 7:
        return None  # Need at least a week of data

    # Fit on days since the first sample, not raw epoch timestamps
    t0 = memory_history[0][0]
    days = np.array([(ts - t0) / SECONDS_PER_DAY for ts, _ in memory_history]).reshape(-1, 1)
    memory_pcts = np.array([pct for _, pct in memory_history])

    model = LinearRegression()
    model.fit(days, memory_pcts)

    current_day = days[-1][0]
    days_ahead = 0
    while days_ahead < 30:
        predicted_memory = model.predict([[current_day + days_ahead]])[0]

        if predicted_memory >= 95:
            if days_ahead < 7 and send_alert is not None:  # Alert if exhaustion within a week
                send_alert(
                    severity="warning",
                    message=f"Redis memory will hit 95% in {days_ahead} days",
                    current_value=memory_pcts[-1],
                    trend=model.coef_[0],  # percent per day
                )
            return days_ahead
        days_ahead += 1

    return None  # No exhaustion predicted in next 30 days


def predict_resource_exhaustion(
    metric_data: pd.Series, threshold: float, hours_ahead: int = 1
) -> dict[str, Any]:
    """Forecast an ARIMA model forward and report when, if ever, it crosses the threshold.

    metric_data: pandas Series with a datetime index and metric values, resampled to regular
                 5-minute intervals.
    threshold: the danger level (for example 90 for 90% disk usage).
    """
    # (1,1,1) is a good starting point: p=autoregressive, d=difference, q=moving average
    fitted = ARIMA(metric_data, order=(1, 1, 1)).fit()

    steps = hours_ahead * 12  # 5-minute intervals
    forecast = fitted.forecast(steps=steps)
    crossing_points = np.where(forecast >= threshold)[0]

    if len(crossing_points) > 0:
        first = int(crossing_points[0])
        return {
            "will_exhaust": True,
            "minutes_until": first * 5,
            # The forecast has a datetime index, so index it by position, not by label.
            "predicted_value": float(forecast.iloc[first]),
            "current_value": metric_data.iloc[-1],
        }
    return {"will_exhaust": False, "forecast": forecast}


def predict_with_seasonality(
    metric_data: pd.Series, threshold: float, hours_ahead: int = 1
) -> dict[str, Any]:
    """The same question with Prophet, which also learns daily and weekly rhythm.

    Needs the optional `prophet` package (see requirements-analytics.txt). The book's listing
    stops after `model.fit(df)`; the forecast and threshold check below complete it in the
    same shape as predict_resource_exhaustion.
    """
    from prophet import Prophet  # imported here because the install is heavy and optional

    df = pd.DataFrame({"ds": metric_data.index, "y": metric_data.values})

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,  # not useful for pipeline metrics
        changepoint_prior_scale=0.05,  # how flexible the trend is
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=hours_ahead * 12, freq="5min")
    forecast = model.predict(future)
    upcoming = forecast[forecast["ds"] > df["ds"].max()].reset_index(drop=True)
    crossing = upcoming[upcoming["yhat"] >= threshold]

    if len(crossing) > 0:
        first = int(crossing.index[0])
        return {
            "will_exhaust": True,
            "minutes_until": (first + 1) * 5,
            "predicted_value": float(crossing.iloc[0]["yhat"]),
            "current_value": metric_data.iloc[-1],
        }
    return {"will_exhaust": False, "forecast": upcoming}


class ForecastEngine:
    """Runs every 6 hours (Chapter 6, "Building a Predictive Failure Dashboard").

    `metrics_client.get_metric_history(metric_name, namespace, days=30)` returns a pandas
    Series with a datetime index. The book builds a CloudWatchClient inline; here it is
    passed in. `prophet_factory` defaults to the real Prophet class.
    """

    def __init__(self, metrics_client: Any, prophet_factory: Callable[[], Any] | None = None):
        self.metrics_client = metrics_client
        if prophet_factory is None:
            from prophet import Prophet

            prophet_factory = Prophet
        self.prophet = prophet_factory()
        self.alert_threshold_days = 7  # warn if exhaustion within a week

    def forecast_resource(
        self, metric_name: str, namespace: str, days_ahead: int = 14
    ) -> pd.DataFrame:
        history = self.metrics_client.get_metric_history(metric_name, namespace, days=30)
        df = pd.DataFrame({"ds": history.index, "y": history.values})
        self.prophet.fit(df)
        future = self.prophet.make_future_dataframe(periods=days_ahead, freq="D")
        forecast: pd.DataFrame = self.prophet.predict(future)
        return forecast[forecast["ds"] > df["ds"].max()]
