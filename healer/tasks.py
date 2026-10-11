"""Fargate task entry point: INVESTIGATE, FIX and TEST.

    python -m healer.tasks investigate

The state machine starts each task with EXECUTION_ID in its environment. The task loads the run's
state from S3, does its stage, and saves the state back. Step Functions cannot read a task's
output, so S3 is the only channel between stages.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from healer import stages
from healer.config import Settings, build_services
from healer.services import Services
from healer.state import PipelineState, S3StateStore

TASKS = {
    "investigate": stages.investigate,
    "fix": stages.fix,
    "test": stages.run_tests,
}


def run_task(name: str, execution_id: str, services: Services) -> PipelineState:
    if name not in TASKS:
        raise SystemExit(f"unknown task {name!r}; choose one of {sorted(TASKS)}")
    store = S3StateStore(services.s3, services.state_bucket_name)
    state = TASKS[name](store.load(execution_id), services)
    store.save(state)
    return state


def main(argv: list[str] | None = None, env: Any = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if len(argv) != 1:
        print("usage: python -m healer.tasks {investigate|fix|test}", file=sys.stderr)
        return 2
    execution_id = env.get("EXECUTION_ID")
    if not execution_id:
        print("EXECUTION_ID is required", file=sys.stderr)
        return 2
    state = run_task(argv[0], execution_id, build_services(Settings.from_env(env)))
    print(f"[{argv[0]}] execution {execution_id}: status={state.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
