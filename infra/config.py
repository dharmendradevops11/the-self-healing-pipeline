"""Deployment settings, read from CDK context: `cdk deploy -c key=value`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeployConfig:
    github_repo_url: str = "https://github.com/OWNER/REPO"
    github_secret_arn: str = (
        ""  # a Secrets Manager secret holding the token (plain string or {"token": ...})
    )
    webhook_secret_arn: str = ""  # the Sentry webhook signing secret
    github_webhook_secret_arn: str = ""  # signs GitHub pull_request events (verdict feedback)
    previous_webhook_secret_arn: str = ""  # kept for the 24 hour rotation overlap
    slack_secret_arn: str = ""  # optional: a secret holding a Slack incoming-webhook URL
    notification_email: str = ""  # optional: subscribed to the notification topic
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-6"
    phase: str = "supervised"  # shadow | supervised | autonomous
    service_registry: str = "{}"  # JSON, for blast radius
    unknown_service_tier: str = "medium"
    base_branch: str = "main"
    max_daily_prs: int = 3
    bedrock_regions: str = ""  # comma separated, for round-robin (Chapter 14)
    bedrock_fallback_model_id: str = ""  # Chapter 17
    bedrock_quick_model_id: str = ""  # Chapter 17
    confidence_threshold: int = 60  # Chapter 18: "the threshold is a CloudFormation parameter"
    log_lines: int = 20
    billing_alarm_usd: int = 0  # >0 adds a billing alarm (Chapter 17: "set a billing alarm too")
    image_tag: str = "latest"
    # Production hardening. Off by default so an experiment can be torn down cleanly.
    audit_object_lock: bool = False
    audit_retention_days: int = 90  # Appendix H: 90 days, GOVERNANCE mode
    retain_data: bool = False

    @classmethod
    def from_context(cls, get: Any) -> DeployConfig:
        """`get` is `node.try_get_context`."""
        defaults = cls()

        def value(name: str) -> Any:
            found = get(f"healer:{name}")
            return getattr(defaults, name) if found is None else found

        def flag(name: str) -> bool:
            return str(value(name)).lower() in ("1", "true", "yes")

        registry = value("service_registry")
        return cls(
            github_repo_url=str(value("github_repo_url")),
            github_secret_arn=str(value("github_secret_arn")),
            webhook_secret_arn=str(value("webhook_secret_arn")),
            github_webhook_secret_arn=str(value("github_webhook_secret_arn")),
            previous_webhook_secret_arn=str(value("previous_webhook_secret_arn")),
            slack_secret_arn=str(value("slack_secret_arn")),
            notification_email=str(value("notification_email")),
            bedrock_model_id=str(value("bedrock_model_id")),
            phase=str(value("phase")),
            service_registry=registry if isinstance(registry, str) else json.dumps(registry),
            unknown_service_tier=str(value("unknown_service_tier")),
            base_branch=str(value("base_branch")),
            max_daily_prs=int(value("max_daily_prs")),
            bedrock_regions=str(value("bedrock_regions")),
            bedrock_fallback_model_id=str(value("bedrock_fallback_model_id")),
            bedrock_quick_model_id=str(value("bedrock_quick_model_id")),
            confidence_threshold=int(value("confidence_threshold")),
            log_lines=int(value("log_lines")),
            billing_alarm_usd=int(value("billing_alarm_usd")),
            image_tag=str(value("image_tag")),
            audit_object_lock=flag("audit_object_lock"),
            audit_retention_days=int(value("audit_retention_days")),
            retain_data=flag("retain_data"),
        )

    def validate(self) -> None:
        if self.phase not in ("shadow", "supervised", "autonomous"):
            raise ValueError("healer:phase must be shadow, supervised or autonomous")
        if self.unknown_service_tier not in ("low", "medium", "high", "critical"):
            raise ValueError("healer:unknown_service_tier must be low, medium, high or critical")
        if not 1 <= self.confidence_threshold <= 100:
            raise ValueError("healer:confidence_threshold must be between 1 and 100")
        json.loads(self.service_registry)  # raises if it is not valid JSON
