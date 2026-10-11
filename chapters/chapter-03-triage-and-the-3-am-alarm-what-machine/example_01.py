import numpy as np
from sklearn.ensemble import IsolationForest
from prometheus_api_client import PrometheusConnect

prom = PrometheusConnect(url="http://prometheus:9090")
query = 'rate(http_requests_total[5m])'
data = prom.custom_query_range(query, start_time='2024-01-01', end_time='2024-01-08')

values = np.array([float(point[1]) for point in data[0]['values']]).reshape(-1, 1)

# contamination is the fraction of your data you expect to be anomalous.
# 0.05 is a starting point, not a constant — tune it against labeled incidents.
model = IsolationForest(contamination=0.05, random_state=42)
model.fit(values)

current_value = np.array([[get_current_metric()]])
anomaly_score = model.score_samples(current_value)[0]

if anomaly_score < -0.5:  # threshold tuned from validation data
    alert(f"Anomalous request rate detected: {current_value[0][0]:.2f} req/s")
