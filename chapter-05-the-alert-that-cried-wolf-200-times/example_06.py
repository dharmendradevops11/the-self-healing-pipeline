from sklearn.ensemble import IsolationForest
import numpy as np

def train_pipeline_anomaly_detector(metrics_history: list[dict]) -> IsolationForest:
    """
    metrics_history: [{'duration': 245, 'cpu_peak': 67, 'memory_peak': 2.1,
                       'test_failures': 0, 'artifact_size_mb': 128}, ...]
    """
    features = ['duration', 'cpu_peak', 'memory_peak', 'test_failures',
                'artifact_size_mb']
    X = np.array([[m[f] for f in features] for m in metrics_history])

    # contamination = expected proportion of outliers in training data
    model = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
    model.fit(X)
    return model

def detect_anomaly(model: IsolationForest, current_metrics: dict) -> tuple[bool, float]:
    """Returns (is_anomaly, anomaly_score)."""
    features = ['duration', 'cpu_peak', 'memory_peak', 'test_failures',
                'artifact_size_mb']
    X = np.array([[current_metrics[f] for f in features]])
    prediction = model.predict(X)[0]   # 1 = normal, -1 = anomaly
    score = model.score_samples(X)[0]  # Lower = more anomalous
    return (prediction == -1, score)
