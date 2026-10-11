"""Model providers.

Bedrock for real runs, a deterministic replay provider for offline experiments. (Ch 2, 17).
"""

from __future__ import annotations

import os
from typing import Any

from healer.llm.base import LLMProvider
from healer.llm.bedrock import BedrockProvider
from healer.llm.replay import ReplayMiss, ReplayProvider


def get_provider(name: str | None = None, **kwargs: Any) -> LLMProvider:
    """Choose a provider by name, or by the HEALER_LLM environment variable (default: replay).

    Defaulting to replay means nothing reaches AWS, or costs money, unless you ask for it.
    """
    name = (name or os.environ.get("HEALER_LLM", "replay")).lower()
    if name == "bedrock":
        return BedrockProvider(**kwargs)
    if name == "replay":
        return ReplayProvider(**kwargs)
    raise ValueError(f"unknown model provider {name!r}; use 'bedrock' or 'replay'")


__all__ = ["BedrockProvider", "LLMProvider", "ReplayMiss", "ReplayProvider", "get_provider"]
