import numpy as np
from sklearn.linear_model import LinearRegression

def predict_redis_exhaustion(memory_history):
    """
    memory_history: list of (timestamp, memory_pct) tuples
    Returns: days until memory hits 95%, or None if trend is safe
    """
    if len(memory_history) < 7:
        return None  # Need at least a week of data

    # Fit on days since the first sample, not raw epoch timestamps
    t0 = memory_history[0][0]
    days = np.array(
        [(ts - t0) / 86400.0 for ts, _ in memory_history]
    ).reshape(-1, 1)
    memory_pcts = np.array([pct for _, pct in memory_history])

    model = LinearRegression()
    model.fit(days, memory_pcts)

    current_day = days[-1][0]
    days_ahead = 0
    while days_ahead < 30:
        predicted_memory = model.predict([[current_day + days_ahead]])[0]

        if predicted_memory >= 95:
            if days_ahead < 7:  # Alert if exhaustion within a week
                send_alert(
                    severity="warning",
                    message=f"Redis memory will hit 95% in {days_ahead} days",
                    current_value=memory_pcts[-1],
                    trend=model.coef_[0]  # percent per day
                )
            return days_ahead
        days_ahead += 1

    return None  # No exhaustion predicted in next 30 days

# This fires on day 3, when memory is still at 68%
predict_redis_exhaustion(last_week_data)  # Alert fires, team plans
