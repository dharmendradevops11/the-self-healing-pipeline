"""Audit trails and compliance (Chapter 11: SOC 2, PCI DSS, HIPAA).

Two records. AuditRecord says what the agent did and why. ChangeRecord says who proposed,
approved and executed a change. They are three different actors, and collapsing them into one
field is how an audit log ends up appearing to say the agent approved its own change.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

AI_AGENT = "ai_agent"
OUTCOMES = ("success", "failure", "rollback", "manual_override")
CHANGE_TYPES = ("autonomous_remediation", "manual_deployment")
SEVERITIES = ("low", "medium", "high")


@dataclass
class AuditRecord:
    agent_id: str  # "healer-action-agent-v2.3"
    invocation_id: str
    triggered_by: str  # "sentry:alert:abc123"
    action: str  # "restart_service", "rollback_deployment"
    target_resource: str
    # Observable evidence, tool calls and decision factors. Exclude raw LLM prompts and payloads,
    # which can carry credentials.
    analysis: str
    confidence: float  # 0.0-1.0
    timestamp: str
    duration_ms: int
    outcome: str
    data_accessed: list[str] = field(default_factory=list)
    data_modified: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")


@dataclass
class ChangeRecord:
    change_id: str
    timestamp: str
    change_type: str
    triggered_by: str  # Sentry alert ID or GitHub user
    proposed_by: str  # "ai_agent" or a human IAM principal
    approved_by: str  # ALWAYS a human IAM principal, never the agent
    executed_by: str  # "ai_agent" or a human IAM principal
    repository: str
    commit_sha: str
    deployment_target: str
    severity: str
    rollback_plan: str

    def validate(self) -> None:
        if self.change_type not in CHANGE_TYPES:
            raise ValueError(f"change_type must be one of {CHANGE_TYPES}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}")
        if not self.approved_by or self.approved_by == AI_AGENT:
            raise ValueError("approved_by must be a human principal, never the agent")


def record_change(
    dynamodb: Any,
    s3: Any,
    record: ChangeRecord,
    table_name: str = "ComplianceChangeLog",
    bucket: str = "compliance-evidence",
    kms_key_id: str | None = None,
) -> None:
    """Write the change to the log table and to encrypted, date-partitioned evidence storage."""
    record.validate()
    body = asdict(record)
    dynamodb.Table(table_name).put_item(Item=body)
    extra: dict[str, Any] = {"ServerSideEncryption": "aws:kms"}
    if kms_key_id:
        extra["SSEKMSKeyId"] = kms_key_id
    s3.put_object(
        Bucket=bucket,
        Key=f"changes/{record.timestamp.split('T')[0]}/{record.change_id}.json",
        Body=json.dumps(body, indent=2),
        **extra,
    )
