"""What pipeline ML actually looks like in practice (Chapter 3, "The Sparse Data Problem").

With little data, a few honest rules beat a model that has nothing to learn from.
"""

from __future__ import annotations

from typing import Any


def predict_deployment_success(deployment_metadata: dict[str, Any]) -> dict[str, Any]:
    if deployment_metadata.get("day_of_week") == "Friday":
        return {"success_probability": 0.2, "reason": "historical_pattern"}
    if deployment_metadata.get("files_changed", 0) > 100:
        return {"success_probability": 0.5, "reason": "large_changeset"}
    return {"success_probability": 0.7, "reason": "no_strong_signal"}
