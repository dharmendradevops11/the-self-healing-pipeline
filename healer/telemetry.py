"""Watch the healer the way the healer watches your services (Chapter 14).

"Track per-stage processing time against a rolling baseline, Bedrock latency and throttle
counts by region, and the one metric that matters more than everything else combined:
end-to-end time from failure detected to remediation applied. Trace it with a single ID."

Each stage prints one CloudWatch Embedded Metric Format line. CloudWatch turns it into metrics
without any extra permission or API call, and the execution id is on the line, so the one trace
id follows the failure through every stage's log.
"""

from __future__ import annotations

import functools
import json
import time
from collections.abc import Callable
from typing import Any

NAMESPACE = "SelfHealingPipeline"


def emf(metric: str, value: float, unit: str, execution_id: str, **dimensions: str) -> str:
    """One EMF record as a JSON line."""
    return json.dumps(
        {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": NAMESPACE,
                        "Dimensions": [list(dimensions)] if dimensions else [[]],
                        "Metrics": [{"Name": metric, "Unit": unit}],
                    }
                ],
            },
            metric: value,
            "execution_id": execution_id,
            **dimensions,
        }
    )


def timed(stage: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Time a stage and report its duration. The stage's own behaviour is untouched."""

    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(state: Any, *args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                return fn(state, *args, **kwargs)
            finally:
                print(
                    emf(
                        "StageSeconds",
                        round(time.monotonic() - start, 3),
                        "Seconds",
                        state.execution_id,
                        Stage=stage,
                    ),
                    flush=True,
                )

        return inner

    return wrap


def report_end_to_end(state: Any, now: float | None = None) -> None:
    """From the moment the failure was detected to the pipeline's last word."""
    from datetime import datetime

    try:
        triggered = datetime.fromisoformat(
            str(state.incident["triggeredAt"]).replace("Z", "+00:00")
        )
    except (KeyError, ValueError):
        return
    seconds = (now if now is not None else time.time()) - triggered.timestamp()
    if seconds >= 0:
        print(
            emf(
                "EndToEndSeconds",
                round(seconds, 1),
                "Seconds",
                state.execution_id,
                Outcome=state.status,
            ),
            flush=True,
        )
