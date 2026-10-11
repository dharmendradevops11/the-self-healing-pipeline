def review_threshold_adjustment(bucket_stats, current_threshold):
    """
    bucket_stats: {confidence_bucket: {"accuracy": float, "sample_size": int}}
    Returns a recommended threshold change, conservative by design.
    """
    MIN_SAMPLE = 15
    ACCURACY_FLOOR = 0.90

    lower_bucket = bucket_stats.get(current_threshold - 10)
    if lower_bucket and lower_bucket["sample_size"] >= MIN_SAMPLE:
        if lower_bucket["accuracy"] >= ACCURACY_FLOOR:
            return current_threshold - 5, "lower: sustained accuracy at lower confidence"

    current_bucket = bucket_stats.get(current_threshold)
    if current_bucket and current_bucket["accuracy"] < ACCURACY_FLOOR:
        return current_threshold + 10, "raise: current threshold underperforming"

    return current_threshold, "hold: insufficient evidence to change"
