"""Configuration from the environment, and the Services built from it (AWS deployment)."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from healer.fix.git_ops import LocalGit, clone_repo
from healer.guardrails.phases import Phase, PRThrottle
from healer.guardrails.secrets import get_github_token, get_secret
from healer.ingest.enrich import make_log_fetcher, make_metrics_fetcher
from healer.llm.base import LLMProvider
from healer.llm.bedrock import BedrockProvider
from healer.notify.notifiers import (
    ConsoleNotifier,
    MultiNotifier,
    Notifier,
    SlackNotifier,
    SNSNotifier,
)
from healer.pr.hosts import GitHubPRHost, PullRequest
from healer.services import Services


@dataclass(frozen=True)
class Settings:
    """Everything configurable. Each field maps to one environment variable."""

    audit_bucket: str = "healer-audit"
    state_bucket: str = ""
    rate_table: str = "investigation_rate_limits"
    ledger_table: str = "agent-trust-ledger"
    history_table: str = "remediation_history"
    throttle_table: str = "pr-throttle"
    notification_topic_arn: str = ""
    trigger_topic_arn: str = ""
    github_repo_url: str = ""
    github_secret_arn: str = ""
    slack_secret_arn: str = ""
    webhook_secret_arn: str = ""
    github_webhook_secret_arn: str = ""
    previous_webhook_secret_arn: str = ""
    bedrock_model_id: str = ""
    bedrock_region: str = ""
    bedrock_regions: str = ""  # comma separated; round-robin across them (Chapter 14)
    bedrock_fallback_model_id: str = ""  # Chapter 17: the fallback for complex cases
    bedrock_quick_model_id: str = ""  # Chapter 17: a small model for quick analysis
    phase: str = "supervised"
    registry: dict[str, Any] = field(default_factory=dict)
    unknown_service_tier: str = "medium"
    base_branch: str = "main"
    max_daily_prs: int = 3
    investigations_per_hour: int = 3
    fix_threshold: int = 60
    log_lines: int = 20

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = env if env is not None else os.environ
        g = lambda key, default="": e.get(key, default)  # noqa: E731
        registry = json.loads(g("HEALER_SERVICE_REGISTRY", "{}") or "{}")
        return cls(
            audit_bucket=g("HEALER_AUDIT_BUCKET", "healer-audit"),
            state_bucket=g("HEALER_STATE_BUCKET"),
            rate_table=g("HEALER_RATE_TABLE", "investigation_rate_limits"),
            ledger_table=g("HEALER_TRUST_LEDGER_TABLE", "agent-trust-ledger"),
            history_table=g("HEALER_HISTORY_TABLE", "remediation_history"),
            throttle_table=g("HEALER_THROTTLE_TABLE", "pr-throttle"),
            notification_topic_arn=g("HEALER_NOTIFICATION_TOPIC_ARN"),
            trigger_topic_arn=g("HEALER_TRIGGER_TOPIC_ARN"),
            github_repo_url=g("GITHUB_REPO_URL"),
            github_secret_arn=g("GITHUB_TOKEN_SECRET_ARN"),
            slack_secret_arn=g("SLACK_WEBHOOK_SECRET_ARN"),
            webhook_secret_arn=g("SENTRY_WEBHOOK_SECRET_ARN"),
            github_webhook_secret_arn=g("GITHUB_WEBHOOK_SECRET_ARN"),
            previous_webhook_secret_arn=g("SENTRY_WEBHOOK_PREVIOUS_SECRET_ARN"),
            bedrock_model_id=g("BEDROCK_MODEL_ID"),
            bedrock_region=g("BEDROCK_REGION"),
            bedrock_regions=g("BEDROCK_REGIONS"),
            bedrock_fallback_model_id=g("BEDROCK_FALLBACK_MODEL_ID"),
            bedrock_quick_model_id=g("BEDROCK_QUICK_MODEL_ID"),
            phase=g("HEALER_PHASE", "supervised"),
            registry=registry,
            unknown_service_tier=g("HEALER_UNKNOWN_SERVICE_TIER", "medium"),
            base_branch=g("GITHUB_BASE_BRANCH", "main"),
            max_daily_prs=int(g("HEALER_MAX_DAILY_PRS", "3")),
            investigations_per_hour=int(g("HEALER_INVESTIGATIONS_PER_HOUR", "3")),
            fix_threshold=int(g("HEALER_CONFIDENCE_THRESHOLD", "60")),
            log_lines=int(g("HEALER_LOG_LINES", "20")),
        )

    @property
    def repo_owner_and_name(self) -> tuple[str, str]:
        parts = urlparse(self.github_repo_url).path.strip("/").removesuffix(".git").split("/")
        if len(parts) != 2:
            raise ValueError(
                f"GITHUB_REPO_URL must look like https://github.com/owner/repo, "
                f"not {self.github_repo_url!r}"
            )
        return parts[0], parts[1]


class _LazyPRHost:
    """Builds the GitHub client on first use: a stage that opens no PR never reads the token."""

    def __init__(self, factory: Any):
        self._factory = factory
        self._host: GitHubPRHost | None = None

    def _get(self) -> GitHubPRHost:
        if self._host is None:
            self._host = self._factory()
        assert self._host is not None
        return self._host

    def create_branch(self, branch: str, base: str) -> None:
        self._get().create_branch(branch, base)

    def commit_file(self, branch: str, path: str, content: str, message: str) -> None:
        self._get().commit_file(branch, path, content, message)

    def open_pull_request(self, **kwargs: Any) -> PullRequest:
        return self._get().open_pull_request(**kwargs)


class _Unavailable:
    """Stands in for a model in a stage that must never call one."""

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("this stage has no model configured")


def build_model(settings: Settings, session: Any, model_id: str | None = None) -> LLMProvider:
    """The configured model, spread across regions and backed by a fallback model.

    Regions (Chapter 14) are tried round-robin on every request. If the primary model cannot
    answer anywhere, the fallback model (Chapter 17) is asked instead.
    """
    from healer.llm.bedrock import runtime_client
    from healer.llm.router import FallbackProvider, RegionRouter

    def for_model(model: str) -> LLMProvider:
        regions = [r.strip() for r in settings.bedrock_regions.split(",") if r.strip()]
        if len(regions) > 1:
            return RegionRouter({r: BedrockProvider(runtime_client(r), model) for r in regions})
        region = (regions[0] if regions else settings.bedrock_region) or None
        client = (
            runtime_client(region)
            if session is boto3_module()
            else session.client("bedrock-runtime", region_name=region)
        )
        return BedrockProvider(client, model)

    primary = for_model(model_id or settings.bedrock_model_id)
    if settings.bedrock_fallback_model_id and not model_id:
        return FallbackProvider(primary, for_model(settings.bedrock_fallback_model_id))
    return primary


def boto3_module() -> Any:
    import boto3

    return boto3


def build_services(
    settings: Settings, session: Any = None, llm: LLMProvider | None = None
) -> Services:
    """Wire the real AWS clients. Secrets are read lazily, by the stage that needs them."""
    import boto3

    session = session or boto3
    secrets = session.client("secretsmanager")
    token_cache: dict[str, str] = {}

    def token() -> str:
        if "t" not in token_cache:
            token_cache["t"] = get_github_token(secrets, settings.github_secret_arn)
        return token_cache["t"]

    def open_repo() -> tuple[LocalGit, Path]:
        dest = Path(tempfile.mkdtemp(prefix="healer-")) / "repo"
        git = clone_repo(settings.github_repo_url, settings.base_branch, dest, token(), depth=50)
        return git, dest

    def make_pr_host() -> GitHubPRHost:
        owner, repo = settings.repo_owner_and_name
        return GitHubPRHost(owner, repo, token())

    notifiers: list[Notifier] = []
    if settings.notification_topic_arn:
        notifiers.append(SNSNotifier(session.client("sns"), settings.notification_topic_arn))
    if settings.slack_secret_arn:
        # Read when the first message is sent, so only NOTIFY ever needs access to the secret.
        notifiers.append(SlackNotifier(lambda: get_secret(secrets, settings.slack_secret_arn)))
    notifier: Notifier = MultiNotifier(*notifiers) if notifiers else ConsoleNotifier()

    dynamodb = session.resource("dynamodb")
    provider = llm or (
        build_model(settings, session) if settings.bedrock_model_id else _Unavailable()
    )
    return Services(
        llm=provider,
        guardrail_llm=(
            # Chapter 17: a small model does the quick analysis. The classifier is exactly that.
            build_model(settings, session, model_id=settings.bedrock_quick_model_id)
            if settings.bedrock_quick_model_id
            else provider
        )
        if settings.bedrock_model_id
        else None,
        open_repo=open_repo,
        dynamodb=dynamodb,
        s3=session.client("s3"),
        audit_bucket=settings.audit_bucket,
        state_bucket=settings.state_bucket,
        pr_host=_LazyPRHost(make_pr_host),  # type: ignore[arg-type]
        notifier=notifier,
        registry=settings.registry,
        phase=Phase(settings.phase),
        throttle=PRThrottle(dynamodb.Table(settings.throttle_table), settings.max_daily_prs),
        rate_table_name=settings.rate_table,
        ledger_table=settings.ledger_table,
        history_table=settings.history_table,
        base_branch=settings.base_branch,
        unknown_service_tier=settings.unknown_service_tier,
        investigations_per_hour=settings.investigations_per_hour,
        fix_threshold=settings.fix_threshold,
        log_lines=settings.log_lines,
        fetch_logs=make_log_fetcher(session.client("logs")),
        get_metrics=make_metrics_fetcher(session.client("cloudwatch")),
        setup_commands=[["python", "-m", "pip", "install", "--quiet", "-r", "requirements.txt"]]
        if os.environ.get("HEALER_INSTALL_REQUIREMENTS") == "1"
        else None,
    )
