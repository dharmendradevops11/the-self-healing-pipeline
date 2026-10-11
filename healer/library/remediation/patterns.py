"""A remediation library: common patterns with real code (Chapter 7).

Each pattern checks a precondition, supports a dry run, and can undo itself. The book's
listings use helpers it never shows (`get_disk_usage`, `kubectl_exec`, ...). Here every
collaborator is a named argument, so each pattern runs against your platform or a test double.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

from healer.library.remediation.types import RemediationResult

logger = logging.getLogger(__name__)

POOL_STEP = 10


def remediate_unresponsive(
    service_name: str,
    platform: str,
    *,
    ecs: Any,
    ec2: Any,
    service_clusters: dict[str, str],
    get_instance_id: Callable[[str], str],
    log_remediation: Callable[..., Any],
) -> None:
    """Restart an unresponsive service on ECS (new deployment) or EC2 (reboot)."""
    if platform == "ecs":
        ecs.update_service(
            cluster=service_clusters[service_name], service=service_name, forceNewDeployment=True
        )
    elif platform == "ec2":
        instance_id = get_instance_id(service_name)
        ec2.reboot_instances(InstanceIds=[instance_id])
    log_remediation(service_name, "restart", platform)


def disk_cleanup_commands(dry_run: bool) -> list[str]:
    """The cleanup shell commands. In a dry run they only list what they would delete."""
    return [
        "find /var/log -name '*.log' -mtime +7 -type f" + ("" if dry_run else " -delete"),
        # Exclusion rule: protect systemd's own directories under /tmp
        "find /tmp -mtime +1 -type f -not -path '/tmp/systemd*'" + ("" if dry_run else " -delete"),
        "echo '[dry-run] docker system prune'"
        if dry_run
        else "docker system prune -f --filter until=48h",
    ]


def remediate_disk_exhaustion(
    instance_id: str,
    *,
    ssm: Any,
    get_disk_usage: Callable[[str], float],
    log_remediation: Callable[..., Any],
    threshold_pct: float = 85,
    dry_run: bool = True,
) -> RemediationResult:
    """Free disk space, but only if the disk really is above the threshold. Dry run by default."""
    # Precondition: check if disk usage actually exceeds threshold
    current_usage = get_disk_usage(instance_id)
    if current_usage < threshold_pct:
        logger.info(
            "Precondition not met: Disk usage (%s%%) under threshold (%s%%)",
            current_usage,
            threshold_pct,
        )
        return RemediationResult.SKIPPED

    ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": disk_cleanup_commands(dry_run)},
    )
    log_remediation(instance_id, "disk_cleanup", threshold_pct, dry_run=dry_run)
    return RemediationResult.SUCCESS


def remediate_memory_leak(
    service_name: str,
    pod_name: str,
    *,
    kubectl_exec: Callable[..., Any],
    wait_for_heapsnapshot_file: Callable[..., Any],
    upload_heap_dump: Callable[..., Any],
    kubectl_delete_pod: Callable[..., Any],
    log_remediation: Callable[..., Any],
    clock: Callable[[], float] = time.time,
) -> str:
    """Capture a heap dump, upload it, then restart the pod gracefully. Returns the dump path.

    The container must start with `node --heapsnapshot-signal=SIGUSR2 server.js`; that startup
    flag is what makes the signal below produce a snapshot without a restart.
    """
    dump_path = f"s3://heap-dumps/{service_name}/{pod_name}-{int(clock())}.heapsnapshot"
    kubectl_exec(pod_name, "kill -USR2 1")
    wait_for_heapsnapshot_file(pod_name, timeout_s=60)
    upload_heap_dump(pod_name, dump_path)
    kubectl_delete_pod(pod_name, grace_period=30)
    log_remediation(service_name, "graceful_restart_with_dump", dump_path)
    return dump_path


class PoolOps(Protocol):
    """What the connection-pool remediation needs from your platform."""

    ceiling: dict[str, int]

    def was_resized_in_last_30_minutes(self, service_name: str) -> bool: ...
    def get_pool_config(self, service_name: str) -> dict[str, Any]: ...
    def reset_connection_pool(self, service_name: str) -> None: ...
    def resize_pool(self, service_name: str, new_max: int) -> None: ...
    def verify_database_health(self, service_name: str) -> bool: ...


def remediate_pool_exhaustion(
    service_name: str,
    pool: PoolOps,
    log_remediation: Callable[..., Any],
    dry_run: bool = True,
) -> RemediationResult:
    """Reset the connection pool and grow it by 10, rolling back if the database gets unhealthy."""
    # Idempotency & precondition check: prevent rapid consecutive resizes
    if pool.was_resized_in_last_30_minutes(service_name):
        logger.warning(
            "Connection pool for %s was already resized recently. Skipping.", service_name
        )
        return RemediationResult.SKIPPED

    config = pool.get_pool_config(service_name)
    current_size = config["max_connections"]

    if dry_run:
        logger.info(
            "[Dry-run] Would reset connection pool and resize from %s to %s",
            current_size,
            current_size + POOL_STEP,
        )
        return RemediationResult.SKIPPED

    # Execution phase with backup of state
    pool.reset_connection_pool(service_name)
    if current_size < pool.ceiling[service_name]:
        pool.resize_pool(service_name, new_max=current_size + POOL_STEP)

        # Rollback behavior: if database health drops, put the old size back
        if not pool.verify_database_health(service_name):
            logger.error(
                "Post-remediation health check failed. Rolling back pool size to %s", current_size
            )
            pool.resize_pool(service_name, new_max=current_size)
            return RemediationResult.FAILED

    log_remediation(service_name, "pool_reset_and_resize", current_size)
    return RemediationResult.SUCCESS


def remediate_failed_deployment(
    service_name: str,
    *,
    ecs: Any,
    service_clusters: dict[str, str],
    get_last_known_good_version: Callable[[str], Any],
    service_has_feature_flag: Callable[[str], bool],
    toggle_flag: Callable[..., Any],
    log_remediation: Callable[..., Any],
) -> None:
    """Roll back: flag off if there is one, otherwise redeploy the last known good version."""
    last_good = get_last_known_good_version(service_name)
    if service_has_feature_flag(service_name):
        toggle_flag(service_name, enabled=False)
    else:
        ecs.update_service(
            cluster=service_clusters[service_name],
            service=service_name,
            taskDefinition=last_good.task_def_arn,
        )
    log_remediation(service_name, "rollback", last_good.version)
