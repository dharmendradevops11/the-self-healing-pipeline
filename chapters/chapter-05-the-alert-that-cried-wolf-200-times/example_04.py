import numpy as np

def detect_anomalies_mad(values: list[float], threshold: float = 3.5) -> list[bool]:
    """MAD-based detection. Threshold of 3.5 ≈ 3σ for normal distributions."""
    median = np.median(values)
    deviations = [abs(x - median) for x in values]
    mad = np.median(deviations)
    if mad == 0:
        mad = np.mean(deviations) or 1.0
    modified_z_scores = [0.6745 * (x - median) / mad for x in values]
    return [abs(z) > threshold for z in modified_z_scores]

# Realistic skewed data: 50ms typical, occasional 2s timeouts
latencies = [48, 52, 51, 49, 2100, 50, 53, 2050, 51, 48, 52]
anomalies_latency = detect_anomalies_mad(latencies, threshold=3.0)
print(f"Timeout anomalies: {[l for l, a in zip(latencies, anomalies_latency) if a]}")
# Output: [2100, 2050]  # Catches both timeouts
