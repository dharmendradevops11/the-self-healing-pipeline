import pandas as pd
from sklearn.ensemble import IsolationForest

def detect_anomalous_patterns(metrics_df):
    """
    Finds unusual combinations of events that correlate with incidents.
    metrics_df has columns: timestamp, deployment_count, batch_jobs_active,
    cache_hit_rate, error_rate, latency_p99
    """
    for col in ['deployment_count', 'batch_jobs_active', 'cache_hit_rate']:
        metrics_df[f'{col}_lag_1h'] = metrics_df[col].shift(6)
        metrics_df[f'{col}_lag_6h'] = metrics_df[col].shift(36)

    features = [col for col in metrics_df.columns if col != 'timestamp']
    # contamination must be tuned to your environment's real anomaly rate
    model = IsolationForest(contamination=0.05, random_state=42)
    metrics_df['anomaly'] = model.fit_predict(metrics_df[features].fillna(0))

    incidents = metrics_df[
        (metrics_df['anomaly'] == -1) &
        (metrics_df['error_rate'] > metrics_df['error_rate'].quantile(0.90))
    ]
    return incidents[['timestamp', 'deployment_count', 'batch_jobs_active',
                      'cache_hit_rate', 'error_rate']]
