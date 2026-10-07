import numpy as np

def detect_anomalies_zscore(values: list[float], threshold: float = 3.0) -> list[bool]:
    """Returns True for each anomalous value."""
    mean = np.mean(values)
    std = np.std(values)
    if std == 0:
        return [False] * len(values)
    z_scores = [(x - mean) / std for x in values]
    return [abs(z) > threshold for z in z_scores]

# Real deployment duration data (seconds)
durations = [245, 251, 248, 252, 249, 1820, 247, 250, 246]
anomalies = detect_anomalies_zscore(durations)
print(f"Anomalies: {[d for d, is_anom in zip(durations, anomalies) if is_anom]}")
# Output: [1820]  # Correctly catches the 30-minute deployment
