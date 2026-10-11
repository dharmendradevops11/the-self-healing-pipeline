"""Step-level audit logging (Chapter 9, "Building Trust in Production").

Every tool execution, LLM call and raw payload is written to S3 under an execution-based key,
so a developer can replay the agent's reasoning step by step:
audit/{execution_id}/step_NNN_{step_type}.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


class AgentAuditLogger:
    def __init__(self, s3_client: Any, bucket: str, execution_id: str, start_step: int = 0):
        self.s3 = s3_client
        self.bucket = bucket
        self.execution_id = execution_id
        self.step_counter = start_step

    @classmethod
    def resume(cls, s3_client: Any, bucket: str, execution_id: str) -> AgentAuditLogger:
        """Continue numbering where earlier stages stopped.

        The book's logger keeps its counter in memory. The pipeline runs each stage in a
        separate process, so a later stage must pick up the count already written to S3.
        """
        prefix = f"audit/{execution_id}/"
        count = 0
        pages = s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
        for page in pages:
            count += len(page.get("Contents", []))
        return cls(s3_client, bucket, execution_id, start_step=count)

    def log_reasoning_step(
        self,
        step_type: str,
        input_data: Any,
        output_data: Any,
        tool_calls: list[Any] | None = None,
        confidence: int | None = None,
    ) -> str:
        self.step_counter += 1
        audit_record = {
            "execution_id": self.execution_id,
            "step_number": self.step_counter,
            "timestamp": datetime.now(UTC).isoformat(),
            "step_type": step_type,
            "input": input_data,
            "output": output_data,
            "tool_calls": tool_calls or [],
            "confidence_score": confidence,
        }
        key = f"audit/{self.execution_id}/step_{self.step_counter:03d}_{step_type}.json"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(audit_record, indent=2, default=str),
            ContentType="application/json",
        )
        return key
