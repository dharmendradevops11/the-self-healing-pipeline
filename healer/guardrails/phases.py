"""Earning trust in phases (Chapter 17, "The Cold Start Problem").

Your first deploy will not heal anything well. You can only choose whether the mistakes happen
in staging or in production. The pipeline therefore climbs three rungs:

  SHADOW      two to four weeks, read-only: record what it would have done, act on nothing
  SUPERVISED  open pull requests, capped hard (three a day at first); nothing merges unreviewed
  AUTONOMOUS  with limits: fewer than five files, a diff under 1,000 lines, tests passing, and a
              service that was stable for the preceding hour

The limits come from what you learned while supervised. Loosen them slowly, not in month one.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from botocore.exceptions import ClientError

from healer.gate.decision import Decision

MERGE_RATE_FLOOR = 0.30  # below this, something is broken
REJECTION_REASONS = ("wrong approach", "breaks compliance", "doesn't address root cause")


class Phase(Enum):
    SHADOW = "shadow"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class PRThrottle:
    """Daily PR cap persisted in DynamoDB.

    An in-memory counter resets on every Lambda cold start, silently disabling the cap. A
    date-keyed DynamoDB item with an atomic ADD and a conditional check survives cold starts and
    concurrent invocations alike. `table` is a boto3 DynamoDB Table resource.
    """

    def __init__(self, table: Any, max_daily_prs: int = 3):
        self.table = table
        self.max_daily_prs = max_daily_prs

    def try_open_pr(self, today: datetime.date | None = None) -> bool:
        day = (today or datetime.date.today()).isoformat()
        try:
            self.table.update_item(
                Key={"pk": f"pr-count#{day}"},
                UpdateExpression="ADD prs_opened :one",
                ConditionExpression="attribute_not_exists(prs_opened) OR prs_opened < :cap",
                ExpressionAttributeValues={":one": 1, ":cap": self.max_daily_prs},
            )
            return True
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False  # Daily cap reached: do not open another PR.
            raise


def create_throttle_table(dynamodb: Any, table_name: str = "pr-throttle") -> Any:
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
    )


@dataclass(frozen=True)
class AutonomyLimits:
    """The hard limits for the autonomous phase. All must hold."""

    max_files: int = 5  # fewer than five files changed
    max_diff_lines: int = 1000  # diff under 1,000 lines

    def violations(
        self, files_changed: int, diff_lines: int, tests_passed: bool, stable_for_an_hour: bool
    ) -> list[str]:
        problems = []
        if files_changed >= self.max_files:
            problems.append(f"{files_changed} files changed (limit: fewer than {self.max_files})")
        if diff_lines >= self.max_diff_lines:
            problems.append(f"diff of {diff_lines} lines (limit: under {self.max_diff_lines})")
        if not tests_passed:
            problems.append("tests are not all passing")
        if not stable_for_an_hour:
            problems.append("service was not stable for the preceding hour")
        return problems


@dataclass(frozen=True)
class ActionPlan:
    action: str  # record_only | open_pr | open_pr_autonomous | escalate | cap_reached
    reason: str


@dataclass
class ChangeFacts:
    """What the pipeline knows about the proposed change, for the autonomous limits."""

    files_changed: int = 0
    diff_lines: int = 0
    tests_passed: bool = False
    stable_for_an_hour: bool = False


class PhaseController:
    def __init__(
        self,
        phase: Phase,
        throttle: PRThrottle | None = None,
        limits: AutonomyLimits | None = None,
    ):
        self.phase = phase
        self.throttle = throttle
        self.limits = limits or AutonomyLimits()

    def plan(self, decision: Decision, facts: ChangeFacts | None = None) -> ActionPlan:
        """Turn the gate's decision into what the pipeline may actually do in this phase."""
        if not decision.fix_authorized:
            return ActionPlan("escalate", "the escalation matrix does not authorize a fix")
        if self.phase is Phase.SHADOW:
            return ActionPlan("record_only", "shadow mode: record what would have been done")

        if self.throttle is not None and not self.throttle.try_open_pr():
            return ActionPlan("cap_reached", "the daily PR cap is reached; do not open another")

        if self.phase is Phase.AUTONOMOUS:
            problems = self.limits.violations(
                (facts or ChangeFacts()).files_changed,
                (facts or ChangeFacts()).diff_lines,
                (facts or ChangeFacts()).tests_passed,
                (facts or ChangeFacts()).stable_for_an_hour,
            )
            if problems:
                reason = "autonomous limits not met, supervised review: " + "; ".join(problems)
                return ActionPlan("open_pr", reason)
            return ActionPlan("open_pr_autonomous", "within the autonomous limits")
        return ActionPlan("open_pr", "supervised: a human reviews every pull request")


@dataclass
class ShadowRecord:
    """'If I had been allowed to act, here is what I would have done.'"""

    incident_id: str
    service: str
    would_have: str  # for example "open_pr" or "escalate"
    root_cause: str
    confidence: int
    blast_radius_tier: str
    proposed_files: list[str] = field(default_factory=list)
    recorded_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat()
    )


def record_shadow(s3: Any, bucket: str, record: ShadowRecord) -> str:
    """Store a shadow decision for review in a postmortem. Returns the object key."""
    key = f"shadow/{record.recorded_at.split('T')[0]}/{record.incident_id}.json"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(asdict(record), indent=2),
        ContentType="application/json",
    )
    return key


def merge_rate(outcomes: list[str]) -> float | None:
    """Merged / decided. 'merged' and 'edited_then_merged' count; pending PRs are ignored."""
    decided = [o for o in outcomes if o in ("merged", "edited_then_merged", "rejected")]
    if not decided:
        return None
    return sum(1 for o in decided if o != "rejected") / len(decided)


def merge_rate_health(outcomes: list[str]) -> str:
    """The primary health signal: below 30% merged means bad patches or PRs rotting unowned."""
    rate = merge_rate(outcomes)
    if rate is None:
        return "no data yet"
    if rate >= MERGE_RATE_FLOOR:
        return "healthy"
    return "broken: investigate patch quality and review ownership"
