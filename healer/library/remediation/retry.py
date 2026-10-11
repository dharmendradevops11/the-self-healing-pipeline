"""Retry with exponential backoff and jitter (Chapter 7)."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

from healer.library.remediation.types import TransientError

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    max_attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 30,
    sleep: Callable[[float], Any] = time.sleep,
    jitter_source: Callable[[float, float], float] = random.uniform,
) -> T:
    """Call fn until it stops raising TransientError, waiting longer each time.

    Only TransientError is retried: anything else is a real bug and should surface at once.
    `sleep` and `jitter_source` are parameters so tests (and your experiments) run instantly.
    """
    for attempt in range(max_attempts):
        try:
            return fn()
        except TransientError:
            if attempt == max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2**attempt))
            jitter = jitter_source(0, delay * 0.3)
            sleep(delay + jitter)
    raise RuntimeError("unreachable")
