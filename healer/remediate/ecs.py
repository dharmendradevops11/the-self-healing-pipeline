"""Restart an ECS service, but only if it opted in (Appendix F).

The book's `Healer-Remediate-Role` may call `ecs:UpdateService` and `ssm:SendCommand` only on
resources tagged `healer-eligible=true`. That is deliberately a different tag from
`chaos-eligible`, which authorises fault-injection experiments (Chapter 10): a resource being
safe to break in a controlled experiment does not make it safe for unattended remediation.

IAM enforces the tag. This module checks it first as well, so a missing tag is a clear message
and not a bare AccessDenied, and so the same rule holds when the code runs somewhere IAM does
not enforce it (a laptop, LocalStack).
"""

from __future__ import annotations

from typing import Any

ELIGIBLE_TAG = "healer-eligible"
CHAOS_TAG = "chaos-eligible"  # Chapter 10. Never accepted here.


class NotEligible(PermissionError):
    """The resource has not been tagged healer-eligible=true."""


def is_eligible(tags: list[dict[str, str]]) -> bool:
    return any(t.get("key") == ELIGIBLE_TAG and t.get("value") == "true" for t in tags)


def restart_service(ecs: Any, cluster: str, service: str) -> dict[str, Any]:
    """Force a new deployment of the service. Returns a rollback closure like Chapter 9's.

    A restart changes no configuration, so there is nothing to undo; the closure is a no-op
    that records the fact. Reversibility is the point of this class of action.
    """
    described = ecs.describe_services(cluster=cluster, services=[service])["services"]
    if not described:
        raise LookupError(f"no such service: {cluster}/{service}")
    arn = described[0]["serviceArn"]
    tags = ecs.list_tags_for_resource(resourceArn=arn)["tags"]
    if not is_eligible(tags):
        raise NotEligible(
            f"{service} is not tagged {ELIGIBLE_TAG}=true. "
            f"A {CHAOS_TAG} tag does not count: it authorises experiments, not remediation."
        )
    ecs.update_service(cluster=cluster, service=service, forceNewDeployment=True)
    return {"applied": True, "action": "restart", "service": service, "rollback": lambda: None}
