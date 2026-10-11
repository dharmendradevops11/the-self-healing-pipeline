"""The trust ledger (Chapter 9): a cold, hard log of how often the agent was right.

One row per execution. human_verdict starts as "pending" and is updated when a reviewer
approves, rejects or modifies the pull request. Rolling accuracy per failure category feeds
the historical_success_rate input of the composite confidence score.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

TABLE_NAME = "agent-trust-ledger"
CATEGORY_INDEX = "category-timestamp-index"
ROLLING_WINDOW = 50
VERDICTS = ("pending", "approved", "rejected", "modified")


def record_outcome(
    dynamodb: Any,
    execution_id: str,
    hypothesis: str,
    confidence: int,
    human_verdict: str,
    fix_worked: bool | None,
    category: str = "unknown",
    table_name: str = TABLE_NAME,
) -> None:
    """Write one ledger row. `dynamodb` is a boto3 DynamoDB *resource*."""
    dynamodb.Table(table_name).put_item(
        Item={
            "execution_id": execution_id,
            "hypothesis": hypothesis,
            "confidence_score": confidence,
            "human_verdict": human_verdict,  # pending / approved / rejected / modified
            "fix_worked": fix_worked,  # verified post-deployment
            "category": category,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


def update_verdict(
    dynamodb: Any,
    execution_id: str,
    human_verdict: str,
    fix_worked: bool | None = None,
    table_name: str = TABLE_NAME,
) -> None:
    if human_verdict not in VERDICTS:
        raise ValueError(f"human_verdict must be one of {VERDICTS}")
    dynamodb.Table(table_name).update_item(
        Key={"execution_id": execution_id},
        UpdateExpression="SET human_verdict = :v, fix_worked = :w",
        ConditionExpression="attribute_exists(execution_id)",
        ExpressionAttributeValues={":v": human_verdict, ":w": fix_worked},
    )


def success_rate_from_verdicts(verdicts: list[str], min_samples: int = 5) -> float | None:
    """approved = 1, modified = 0.5, rejected = 0. None until there are enough resolved outcomes."""
    resolved = [v for v in verdicts if v in ("approved", "modified", "rejected")]
    if len(resolved) < min_samples:
        return None
    points = sum(1.0 if v == "approved" else 0.5 if v == "modified" else 0.0 for v in resolved)
    return points / len(resolved)


def historical_success_rate(
    dynamodb: Any, category: str, table_name: str = TABLE_NAME, min_samples: int = 5
) -> float | None:
    """Rolling accuracy for a failure category, or None when history is sparse.

    Fails soft: a ledger outage must not stop an investigation, it only removes this input.
    """
    try:
        response = dynamodb.Table(table_name).query(
            IndexName=CATEGORY_INDEX,
            KeyConditionExpression="category = :c",
            ExpressionAttributeValues={":c": category},
            ScanIndexForward=False,
            Limit=ROLLING_WINDOW,
        )
    except Exception:  # noqa: BLE001 - see docstring
        return None
    return success_rate_from_verdicts(
        [item.get("human_verdict", "") for item in response.get("Items", [])], min_samples
    )


def create_table(dynamodb: Any, table_name: str = TABLE_NAME) -> Any:
    """Create the ledger table, for LocalStack and the tests. The CDK stack has the same shape."""
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "execution_id", "AttributeType": "S"},
            {"AttributeName": "category", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "execution_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": CATEGORY_INDEX,
                "KeySchema": [
                    {"AttributeName": "category", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
