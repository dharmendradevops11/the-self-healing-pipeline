"""Circuit breakers for remediations (Chapter 7).

Automation that keeps retrying a failing fix makes things worse. These stop the storm.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from typing import Any


class RemediationCircuitBreaker:
    """Prevent remediation storms: at most `max_attempts` per `window`, then a `cooldown`."""

    def __init__(
        self,
        max_attempts: int = 3,
        window: float = 300,
        cooldown: float = 600,
        clock: Callable[[], float] = time.time,
    ):
        self.max_attempts = max_attempts  # 3 tries
        self.window = window  # within 5 minutes
        self.cooldown = cooldown  # then wait 10 minutes
        self.clock = clock
        self.attempts: deque[float] = deque()

    def can_attempt(self, action_id: str | None = None) -> tuple[bool, str | None]:
        """Check if remediation is allowed."""
        now = self.clock()

        # Clear old attempts outside window
        while self.attempts and self.attempts[0] < now - self.window:
            self.attempts.popleft()

        # Too many recent attempts?
        if len(self.attempts) >= self.max_attempts:
            last_attempt = self.attempts[-1]
            if now - last_attempt < self.cooldown:
                return False, f"Circuit open. Cooldown until {last_attempt + self.cooldown}"

        return True, None

    def record_attempt(self) -> None:
        """Track this remediation attempt."""
        self.attempts.append(self.clock())


def count_consecutive_failures(attempts: list[dict[str, Any]]) -> int:
    """Failures at the end of the history, newest last. A success resets the count.

    Each attempt is a dict with a boolean "success". The book uses this helper without defining it.
    """
    count = 0
    for attempt in reversed(attempts):
        if attempt.get("success"):
            break
        count += 1
    return count


def check_circuit_breaker(
    service_name: str,
    get_remediation_history: Callable[..., list[dict[str, Any]]],
    open_circuit: Callable[[str], Any],
    escalate_to_human: Callable[..., Any],
    failure_limit: int = 3,
) -> bool:
    """Open the circuit and escalate after repeated failures. True means it is safe to continue."""
    recent_attempts = get_remediation_history(service_name, window_minutes=10)
    consecutive_failures = count_consecutive_failures(recent_attempts)

    if consecutive_failures >= failure_limit:
        open_circuit(service_name)
        escalate_to_human(
            service_name, reason=f"{consecutive_failures} consecutive remediation failures"
        )
        return False
    return True
