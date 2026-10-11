"""Stage 4, Learn: the feedback loop that makes it smarter (Chapter 2).

Every incident leaves a row: what was believed, what was changed, how the tests did, and what
the human decided. Without it the pipeline would repeat the same fix forever.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

TABLE_NAME = "remediation_history"
REMEDIATION_TYPES = ("retry", "rollback", "repair")
HUMAN_DECISIONS = ("merged", "rejected", "edited_then_merged")


@dataclass
class RemediationRecord:
    incident_id: str
    service: str
    root_cause_hypothesis: str
    confidence_score: int
    remediation_type: str  # retry | rollback | repair
    files_changed: list[str] = field(default_factory=list)
    test_results: dict[str, str] = field(default_factory=dict)
    human_decision: str | None = None  # merged | rejected | edited_then_merged
    time_to_pr_seconds: int | None = None
    recurrence_of: str | None = None  # incident_id of a prior similar failure, if any
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def validate(self) -> None:
        if self.remediation_type not in REMEDIATION_TYPES:
            raise ValueError(f"remediation_type must be one of {REMEDIATION_TYPES}")
        if self.human_decision is not None and self.human_decision not in HUMAN_DECISIONS:
            raise ValueError(f"human_decision must be one of {HUMAN_DECISIONS}")


def record_remediation(
    dynamodb: Any, record: RemediationRecord, table_name: str = TABLE_NAME
) -> None:
    record.validate()
    dynamodb.Table(table_name).put_item(Item=asdict(record))


def update_decision(
    dynamodb: Any,
    incident_id: str,
    human_decision: str,
    rejection_reason: str | None = None,
    table_name: str = TABLE_NAME,
) -> None:
    """Record what the reviewer did. A rejection keeps its reason, so it teaches something."""
    if human_decision not in HUMAN_DECISIONS:
        raise ValueError(f"human_decision must be one of {HUMAN_DECISIONS}")
    values: dict[str, Any] = {":d": human_decision, ":r": rejection_reason or ""}
    dynamodb.Table(table_name).update_item(
        Key={"incident_id": incident_id},
        UpdateExpression="SET human_decision = :d, rejection_reason = :r",
        ConditionExpression="attribute_exists(incident_id)",
        ExpressionAttributeValues=values,
    )


def recurrences_of(
    dynamodb: Any, service: str, table_name: str = TABLE_NAME
) -> list[dict[str, Any]]:
    """Earlier incidents for a service, newest first, so a repeat failure can be linked."""
    response = dynamodb.Table(table_name).query(
        IndexName="service-created-index",
        KeyConditionExpression="service = :s",
        ExpressionAttributeValues={":s": service},
        ScanIndexForward=False,
    )
    return list(response.get("Items", []))


def create_table(dynamodb: Any, table_name: str = TABLE_NAME) -> Any:
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "incident_id", "AttributeType": "S"},
            {"AttributeName": "service", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "incident_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "service-created-index",
                "KeySchema": [
                    {"AttributeName": "service", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
