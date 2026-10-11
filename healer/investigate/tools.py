"""The tool model: AWS services as agent capabilities (Chapter 8)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class UnknownToolError(KeyError):
    """The model asked for a tool that is not registered."""


class ToolRegistry:
    """The things the agent is allowed to do. If it is not registered, it cannot be called."""

    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}

    def register(
        self, name: str, func: Callable[..., Any], description: str, parameters: dict[str, Any]
    ) -> None:
        self.tools[name] = {"function": func, "description": description, "parameters": parameters}

    def as_bedrock_schema(self) -> list[dict[str, Any]]:
        """Convert tools to Bedrock's tool schema format."""
        return [
            {
                "name": name,
                "description": tool["description"],
                "input_schema": {
                    "type": "object",
                    "properties": tool["parameters"],
                    "required": list(tool["parameters"].keys()),
                },
            }
            for name, tool in self.tools.items()
        ]

    def describe(self) -> str:
        """A plain-text list of the tools for the prompt (the book calls it without defining it)."""
        return "\n".join(f"- {name}: {tool['description']}" for name, tool in self.tools.items())

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self.tools:
            raise UnknownToolError(f"tool {name!r} is not registered")
        return self.tools[name]["function"](**arguments)


def safe_tool_call(
    tool_func: Callable[[], Any], fallback_value: Any = None, required: bool = False
) -> dict[str, Any]:
    """Execute a tool call with failure handling.

    An optional tool that fails degrades the investigation instead of stopping it. A required
    tool (the source code, say) fails fast: there is nothing to diagnose without it.
    """
    name = getattr(tool_func, "__name__", "tool")
    try:
        result = tool_func()
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        logger.exception("Tool call failed: %s", name)

        if required:
            raise  # Fail fast if this tool is critical

        return {"success": False, "data": fallback_value, "error": str(e), "tool": name}
