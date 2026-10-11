"""Amazon Bedrock provider, using the invocation shape from Chapter 2."""

from __future__ import annotations

import json
import os
from typing import Any

# Never hardcode this. Bedrock models have published end-of-life dates; keep the identifier
# in configuration so a retirement is a config change. This default is the model the book's
# edition was tested against and may be retired: set BEDROCK_MODEL_ID to a current one.
DEFAULT_MODEL_ID = "anthropic.claude-sonnet-4-20250514-v1:0"


def runtime_client(region: str | None = None) -> Any:
    """A Bedrock client built the way Chapter 14 says: a bigger connection pool, adaptive retries.

    "Pair this with explicit boto3 connection pooling (max_pool_connections=50, adaptive
    retries) to prevent container resource exhaustion."
    """
    import boto3
    from botocore.config import Config

    config = Config(max_pool_connections=50, retries={"mode": "adaptive", "max_attempts": 5})
    return boto3.client("bedrock-runtime", region_name=region, config=config)


class BedrockProvider:
    def __init__(self, client: Any = None, model_id: str | None = None):
        if client is None:
            client = runtime_client()
        self.client = client
        self.model_id = model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)

    def invoke(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None
    ) -> str:
        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            body["temperature"] = temperature
        response = self.client.invoke_model(modelId=self.model_id, body=json.dumps(body))
        return str(json.loads(response["body"].read())["content"][0]["text"])
