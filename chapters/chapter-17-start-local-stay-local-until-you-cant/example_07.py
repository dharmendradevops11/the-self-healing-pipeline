import datetime

import boto3
from botocore.exceptions import ClientError


class PRThrottle:
    """Daily PR cap persisted in DynamoDB.

    An in-memory counter resets on every Lambda cold start, silently
    disabling the cap. A date-keyed DynamoDB item with an atomic ADD
    and a conditional check survives cold starts and concurrent
    invocations alike.
    """

    def __init__(self, table_name: str, max_daily_prs: int = 3):
        self.table = boto3.resource("dynamodb").Table(table_name)
        self.max_daily_prs = max_daily_prs

    def try_open_pr(self) -> bool:
        today = datetime.date.today().isoformat()
        try:
            self.table.update_item(
                Key={"pk": f"pr-count#{today}"},
                UpdateExpression="ADD prs_opened :one",
                ConditionExpression=(
                    "attribute_not_exists(prs_opened) OR prs_opened < :cap"
                ),
                ExpressionAttributeValues={
                    ":one": 1,
                    ":cap": self.max_daily_prs,
                },
            )
            return True
        except ClientError as err:
            if (
                err.response["Error"]["Code"]
                == "ConditionalCheckFailedException"
            ):
                return False  # Daily cap reached — do not open another PR.
            raise
