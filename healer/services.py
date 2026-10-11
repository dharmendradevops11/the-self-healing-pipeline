"""Everything a stage touches, injected (so one code path runs anywhere)."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from healer.fix.git_ops import LocalGit
from healer.guardrails.phases import Phase, PRThrottle
from healer.llm.base import LLMProvider
from healer.notify.notifiers import Notifier
from healer.pr.hosts import PullRequestHost


@dataclass
class Services:
    """Build one for a laptop, LocalStack or AWS."""

    llm: LLMProvider
    open_repo: Callable[[], tuple[LocalGit, Path]]  # a fresh clone the stage owns
    dynamodb: Any  # boto3 DynamoDB *resource*
    s3: Any  # boto3 S3 client
    audit_bucket: str
    pr_host: PullRequestHost
    notifier: Notifier
    registry: dict[str, dict[str, Any]]
    guardrail_llm: LLMProvider | None = None  # Layer 2 classifier; None skips it
    phase: Phase = Phase.SUPERVISED
    throttle: PRThrottle | None = None
    rate_table_name: str = "investigation_rate_limits"
    ledger_table: str = "agent-trust-ledger"
    history_table: str = "remediation_history"
    base_branch: str = "main"
    unknown_service_tier: str = "medium"
    check_commands: dict[str, list[str]] | None = None
    setup_commands: list[list[str]] | None = None  # for example install the repo's own dependencies
    get_metrics: Callable[..., Any] | None = None  # CloudWatch metric history (Chapter 8)
    fetch_logs: Callable[[dict[str, Any]], str] | None = None  # CloudWatch, when the alert has none
    investigations_per_hour: int = 3
    fix_threshold: int = 60  # the composite score at which a fix may be written (Chapter 2)
    log_lines: int = 20  # how many CloudWatch lines INGEST attaches (Chapter 2)
    state_bucket: str = ""  # inter-stage state (Chapter 8); defaults to the audit bucket
    today: datetime.date | None = None

    @property
    def state_bucket_name(self) -> str:
        """Inter-stage state. Chapter 17 keeps it apart from the locked audit bucket."""
        return self.state_bucket or self.audit_bucket
