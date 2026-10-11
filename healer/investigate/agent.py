"""The orchestration layer you build yourself (Chapter 8).

An executor that reads its context from S3, asks the model, runs the tool calls the model
requests (and only registered tools), and writes the result back for the next stage.
"""

from __future__ import annotations

import json
from typing import Any

from healer.investigate.tools import ToolRegistry, UnknownToolError
from healer.llm.bedrock import DEFAULT_MODEL_ID

STATE_BUCKET = "pipeline-agent-state"


class AgentExecutor:
    def __init__(
        self,
        bedrock_client: Any,
        s3_client: Any,
        tool_registry: ToolRegistry,
        model_id: str = DEFAULT_MODEL_ID,
        bucket: str = STATE_BUCKET,
    ):
        self.bedrock = bedrock_client
        self.s3 = s3_client
        self.tools = tool_registry
        self.model_id = model_id
        self.bucket = bucket

    def execute(self, state_key: str) -> dict[str, Any]:
        obj = self.s3.get_object(Bucket=self.bucket, Key=f"{state_key}/context.json")
        context = json.loads(obj["Body"].read())
        prompt = self._build_prompt(context, self.tools.describe())

        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": self.tools.as_bedrock_schema(),
                }
            ),
        )

        result = self._execute_tool_calls(response)
        self.s3.put_object(
            Bucket=self.bucket, Key=f"{state_key}/result.json", Body=json.dumps(result, default=str)
        )
        return result

    @staticmethod
    def _build_prompt(context: dict[str, Any], tool_descriptions: str) -> str:
        return (
            "You are investigating a production failure. You may call these tools:\n"
            f"{tool_descriptions}\n\n"
            f"Context:\n{json.dumps(context, indent=2, default=str)}"
        )

    def _execute_tool_calls(self, response: dict[str, Any]) -> dict[str, Any]:
        """Run every tool the model asked for. A tool that is not registered, or that raises,
        is recorded as an error and does not stop the others."""
        body = json.loads(response["body"].read())
        text_parts: list[str] = []
        tool_results: list[dict[str, Any]] = []
        for block in body.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                entry: dict[str, Any] = {"tool": block["name"], "id": block.get("id")}
                try:
                    entry["result"] = self.tools.call(block["name"], block.get("input", {}))
                except UnknownToolError as exc:
                    entry["error"] = str(exc)
                except Exception as exc:
                    entry["error"] = f"{type(exc).__name__}: {exc}"
                tool_results.append(entry)
        return {"text": "\n".join(text_parts), "tool_results": tool_results}
