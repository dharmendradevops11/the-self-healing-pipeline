def compute_confidence(signal_strength: float, model_certainty: float,
                       historical_success_rate: float) -> int:
    """
    All inputs are 0.0-1.0. Returns a composite confidence score 0-100.
    signal_strength: completeness/relevance of log and trace context
    model_certainty: model's own stated confidence in the diagnosis
    historical_success_rate: rolling accuracy for this failure category
    """
    weights = {
        "signal": 0.30,
        "model": 0.45,
        "history": 0.25,
    }

    # Fall back to neutral prior if historical data is sparse for a new signature
    if historical_success_rate is None:
        historical_success_rate = 0.5
        weights["model"] += weights["history"] * 0.5
        weights["history"] *= 0.5

    score = (
        signal_strength * weights["signal"]
        + model_certainty * weights["model"]
        + historical_success_rate * weights["history"]
    )
    return round(score * 100)
