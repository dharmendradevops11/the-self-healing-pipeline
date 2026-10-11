"""Test flakiness prediction (Chapter 6, "Spotting the Next Failure Early")."""

from __future__ import annotations

from typing import Any

import pandas as pd


def calculate_flakiness_scores(
    test_runs: list[dict[str, Any]], window_size: int = 50
) -> dict[str, dict[str, Any]]:
    """
    test_runs: list of dicts with 'test_name', 'timestamp', 'passed' (bool)
    Returns: dict of test_name -> {flakiness_score, pass_rate, sample_size}

    A test that always passes or always fails is not flaky. Flakiness peaks at a 50% pass
    rate. Tests with fewer than 10 recent runs are skipped: too little to judge.
    """
    df = pd.DataFrame(test_runs).sort_values("timestamp")
    scores: dict[str, dict[str, Any]] = {}

    for test_name in df["test_name"].unique():
        test_data = df[df["test_name"] == test_name].tail(window_size)
        if len(test_data) < 10:
            continue

        pass_rate = float(test_data["passed"].mean())
        # Flakiness is highest near 0.5, lowest at the extremes
        flakiness = 0.0 if pass_rate in (0.0, 1.0) else 1 - abs(2 * pass_rate - 1)

        scores[test_name] = {
            "flakiness_score": flakiness,
            "pass_rate": pass_rate,
            "sample_size": len(test_data),
        }
    return scores
