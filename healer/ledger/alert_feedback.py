"""Alert feedback: was it a real problem or noise? (Chapter 5, "Reducing False Positives").

Calibration never ends. Every alert a human investigates is recorded, so the false-positive
rate per alert type can be measured and the noisy ones tuned or silenced.
"""

from __future__ import annotations

import time
from typing import Any

TABLE_NAME = "alert_feedback"
INDEX_NAME = "service_error_index"


def record_alert_feedback(
    dynamodb: Any,
    alert_id: str,
    service_name: str,
    error_type: str,
    was_false_positive: bool,
    investigated_by: str,
    now: float | None = None,
) -> None:
    """Record whether an alert was legitimate or noise. `dynamodb` is a low-level boto3 client."""
    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={
            "alert_id": {"S": alert_id},
            "service_name": {"S": service_name},
            "error_type": {"S": error_type},
            "false_positive": {"BOOL": was_false_positive},
            "investigated_by": {"S": investigated_by},
            "timestamp": {"N": str(int(now if now is not None else time.time()))},
        },
    )


def get_false_positive_rate(
    dynamodb: Any,
    service_name: str,
    error_type: str,
    days: int = 7,
    now: float | None = None,
) -> float:
    """False-positive rate for one alert type over a rolling window. 0.0 when there is no data."""
    cutoff = int((now if now is not None else time.time()) - (days * 86400))
    response = dynamodb.query(
        TableName=TABLE_NAME,
        IndexName=INDEX_NAME,
        KeyConditionExpression="service_name = :svc AND error_type = :err",
        FilterExpression="#ts > :cutoff",
        ExpressionAttributeNames={"#ts": "timestamp"},
        ExpressionAttributeValues={
            ":svc": {"S": service_name},
            ":err": {"S": error_type},
            ":cutoff": {"N": str(cutoff)},
        },
    )
    items = response.get("Items", [])
    if not items:
        return 0.0
    false_positives = sum(1 for item in items if item["false_positive"]["BOOL"])
    return false_positives / len(items)


def create_table(dynamodb: Any, table_name: str = TABLE_NAME) -> Any:
    """Create the feedback table and its index. `dynamodb` is a low-level client."""
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "alert_id", "AttributeType": "S"},
            {"AttributeName": "service_name", "AttributeType": "S"},
            {"AttributeName": "error_type", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "alert_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": INDEX_NAME,
                "KeySchema": [
                    {"AttributeName": "service_name", "KeyType": "HASH"},
                    {"AttributeName": "error_type", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
