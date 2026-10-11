"""Spread and survive: regions (Chapter 14) and models (Chapter 17).

Chapter 14: "Build a router that round-robins across regions on every request, not just on
failure, and distinguishes throttling (try another region now) from hard failures (skip this
region for a while). Otherwise everyone fails over to us-west-2 simultaneously, and you have
just exhausted that quota too."

Chapter 17's prerequisites name a primary model, a fallback for complex cases and a cheap one
for quick analysis. `FallbackProvider` is the primary-then-fallback pair.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from healer.llm.base import LLMProvider

THROTTLE_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceQuotaExceededException",
}


def error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str(response.get("Error", {}).get("Code", ""))
    return type(exc).__name__


class AllRegionsFailed(RuntimeError):
    """Every region was throttled, down, or cooling off."""


class RegionRouter:
    """Round-robin over providers, one per region."""

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        cooldown_seconds: float = 120.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not providers:
            raise ValueError("at least one region is required")
        self.providers = providers
        self.regions = list(providers)
        self.cooldown, self.clock = cooldown_seconds, clock
        self._next = 0
        self._down_until: dict[str, float] = {}
        self.throttled: dict[str, int] = {r: 0 for r in providers}  # a metric worth watching

    def invoke(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None
    ) -> str:
        start = self._next
        self._next = (self._next + 1) % len(self.regions)  # advance on every request
        last: Exception | None = None
        for offset in range(len(self.regions)):
            region = self.regions[(start + offset) % len(self.regions)]
            if self._down_until.get(region, 0) > self.clock():
                continue
            try:
                return self.providers[region].invoke(
                    prompt, max_tokens=max_tokens, temperature=temperature
                )
            except Exception as exc:  # noqa: BLE001
                last = exc
                if error_code(exc) in THROTTLE_CODES:
                    self.throttled[region] += 1  # throttling: try the next region right now
                else:
                    self._down_until[region] = self.clock() + self.cooldown  # hard failure
        raise AllRegionsFailed(f"no region could answer: {last}") from last


class FallbackProvider:
    """Ask the primary model; if it cannot answer, ask the fallback."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary, self.fallback = primary, fallback
        self.fallbacks_used = 0

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        try:
            return self.primary.invoke(prompt, **kwargs)
        except Exception:  # noqa: BLE001
            self.fallbacks_used += 1
            return self.fallback.invoke(prompt, **kwargs)
