"""The one thing the pipeline needs from a model: send a prompt, get text back."""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    def invoke(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None
    ) -> str: ...
