"""State rollbacks (Chapter 9): every action registers its undo before it runs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class RollbackStack:
    """Collects rollback callbacks and unwinds them newest-first if something goes wrong."""

    def __init__(self) -> None:
        self._callbacks: list[tuple[str, Callable[[], None]]] = []

    def register(self, description: str, rollback: Callable[[], None]) -> None:
        self._callbacks.append((description, rollback))

    def __len__(self) -> int:
        return len(self._callbacks)

    def rollback_all(self) -> list[str]:
        """Run every callback, newest first. One failing rollback does not stop the rest."""
        undone: list[str] = []
        while self._callbacks:
            description, callback = self._callbacks.pop()
            try:
                callback()
                undone.append(description)
            except Exception as exc:  # noqa: BLE001 - keep unwinding
                undone.append(f"{description} (FAILED: {exc})")
        return undone


def apply_ecs_scaling(ecs: Any, cluster: str, service_name: str, new_memory: int) -> dict[str, Any]:
    """Change a service's memory limit and return a closure that puts it back."""
    # Capture the current task definition before touching anything.
    current = ecs.describe_task_definition(taskDefinition=service_name)
    old_task_def_arn = current["taskDefinition"]["taskDefinitionArn"]

    # ECS task definitions are immutable, so a change always means a new revision.
    td = current["taskDefinition"]
    new_revision = ecs.register_task_definition(
        family=td["family"],
        containerDefinitions=td["containerDefinitions"],
        cpu=td.get("cpu"),
        memory=str(new_memory),
        networkMode=td.get("networkMode"),
        requiresCompatibilities=td.get("requiresCompatibilities", []),
        executionRoleArn=td.get("executionRoleArn"),
        taskRoleArn=td.get("taskRoleArn"),
    )

    ecs.update_service(
        cluster=cluster,
        service=service_name,
        taskDefinition=new_revision["taskDefinition"]["taskDefinitionArn"],
    )

    def rollback() -> None:
        # Rolling back is just pointing the service at the old revision.
        ecs.update_service(cluster=cluster, service=service_name, taskDefinition=old_task_def_arn)

    return {"applied": True, "rollback": rollback}
