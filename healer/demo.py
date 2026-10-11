"""Run the whole pipeline on your laptop. No AWS account, no cost, the same result every time.

    python -m healer.demo                       # the happy path
    python -m healer.demo --registry scenarios/registry-payments.json   # payment-adjacent service
    python -m healer.demo --phase shadow        # watch it decide without acting
    python -m healer.demo --llm bedrock         # use a real model (needs AWS credentials)

AWS is mocked in-process with moto. Git is real: a bare remote and a clone in a temp folder.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any

from healer.fix.git_ops import LocalGit
from healer.guardrails.phases import Phase, PRThrottle, create_throttle_table
from healer.ingest import rate_limiter
from healer.ledger import remediation_history, trust_ledger
from healer.llm import ReplayProvider, get_provider
from healer.notify.notifiers import ConsoleNotifier
from healer.pipeline import PipelineResult, Services, run_pipeline
from healer.pr.hosts import LocalPRHost

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "scenarios"
AUDIT_BUCKET = "healer-audit"
STATE_BUCKET = "healer-state"


def _git(cwd: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Demo",
        "GIT_AUTHOR_EMAIL": "demo@example.com",
        "GIT_COMMITTER_NAME": "Demo",
        "GIT_COMMITTER_EMAIL": "demo@example.com",
    }
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env)


def make_repo(work: Path, app: Path = SCENARIOS / "demo-app") -> tuple[Path, Path]:
    """A bare 'remote' and a working clone of the demo app on `main`."""
    remote, clone = work / "remote.git", work / "clone"
    _git(work, "init", "--bare", "-b", "main", str(remote))
    _git(work, "clone", str(remote), str(clone))
    _git(clone, "checkout", "-b", "main")
    shutil.copytree(
        app,
        clone,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "README.md"),
    )
    _git(clone, "add", "-A")
    _git(clone, "commit", "-m", "Add the demo app")
    _git(clone, "push", "-u", "origin", "main")
    return remote, clone


def _reset_localstack(dynamodb: Any, s3: Any) -> None:
    """LocalStack persists between runs, so start each run from empty tables and bucket."""
    for table in list(dynamodb.tables.all()):
        table.delete()
        table.wait_until_not_exists()
    for bucket in (AUDIT_BUCKET, STATE_BUCKET):
        try:
            for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for obj in page.get("Contents", []):
                    s3.delete_object(Bucket=bucket, Key=obj["Key"])
            s3.delete_bucket(Bucket=bucket)
        except s3.exceptions.NoSuchBucket:
            pass


@contextmanager
def local_services(
    *,
    registry: dict[str, Any] | None = None,
    replay: str | Path = SCENARIOS / "replays" / "null-profile.json",
    llm_name: str | None = None,
    phase: Phase = Phase.SUPERVISED,
    guardrail_reply: str | None = "SAFE",
    work_dir: Path | None = None,
    localstack: str | None = None,
) -> Iterator[tuple[Services, dict[str, Any]]]:
    """Everything the pipeline needs, running locally. Yields (services, handles).

    AWS is moto by default. Pass `localstack="http://localhost:4566"` to use the LocalStack
    container from docker-compose.yml instead (Chapter 17, "Verify Everything Locally").
    """
    import boto3

    own_tmp = work_dir is None
    work = work_dir or Path(tempfile.mkdtemp(prefix="healer-demo-"))
    work.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "demo")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "demo")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    if localstack:
        os.environ["AWS_ENDPOINT_URL"] = localstack  # boto3 reads this natively
        aws: Any = nullcontext()
    else:
        from moto import mock_aws

        aws = mock_aws()
    with aws:
        dynamodb, s3 = boto3.resource("dynamodb"), boto3.client("s3")
        if localstack:
            _reset_localstack(dynamodb, s3)
        rate_limiter.create_table(dynamodb)
        trust_ledger.create_table(dynamodb)
        remediation_history.create_table(dynamodb)
        throttle_table = create_throttle_table(dynamodb)
        s3.create_bucket(Bucket=AUDIT_BUCKET)
        s3.create_bucket(Bucket=STATE_BUCKET)

        remote, clone = make_repo(work)
        llm = get_provider(llm_name or "replay")
        if isinstance(llm, ReplayProvider) and not llm.rules:
            llm = ReplayProvider.from_file(replay)
        guardrail = (
            ReplayProvider([("telemetry payload", guardrail_reply)]) if guardrail_reply else None
        )
        notifier = ConsoleNotifier()
        services = Services(
            llm=llm,
            guardrail_llm=guardrail,
            open_repo=lambda: (LocalGit(clone), clone),
            dynamodb=dynamodb,
            s3=s3,
            audit_bucket=AUDIT_BUCKET,
            state_bucket=STATE_BUCKET,
            pr_host=LocalPRHost(work / "prs", git=LocalGit(clone)),
            notifier=notifier,
            registry=registry
            if registry is not None
            else json.loads((SCENARIOS / "registry.json").read_text()),
            phase=phase,
            throttle=PRThrottle(throttle_table),
        )
        try:
            yield services, {"work": work, "remote": remote, "clone": clone, "notifier": notifier}
        finally:
            if own_tmp:
                shutil.rmtree(work, ignore_errors=True)


def describe(result: PipelineResult) -> str:
    lines = [f"\n=== result: {result.outcome} ===", result.reason]
    d = result.decision
    if d and result.diagnosis:
        lines += [
            f"root cause : {result.diagnosis.root_cause_hypothesis}",
            f"confidence : model said {result.diagnosis.confidence_score}, "
            f"composite score {result.composite_confidence}"
            f" ({d.band})",
            f"blast radius: {d.blast_radius['tier']} ({d.blast_radius['estimated_users']} users)",
            f"decision   : {d.fix_action}, escalation tier {d.tier} -> {d.recipient}",
        ]
    if result.branch:
        lines.append(f"branch     : {result.branch}")
    if result.tests:
        lines.append("tests      : " + ", ".join(result.tests.summary()))
    if result.pr:
        lines.append(f"pull request: {result.pr.url}  labels: {', '.join(result.pr.labels)}")
    lines.append(f"audit steps: {len(result.audit_keys)} written")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the self-healing pipeline locally.")
    parser.add_argument("--incident", default=str(SCENARIOS / "incidents" / "null-profile.json"))
    parser.add_argument("--registry", default=str(SCENARIOS / "registry.json"))
    parser.add_argument("--replay", default=str(SCENARIOS / "replays" / "null-profile.json"))
    parser.add_argument("--phase", choices=[p.value for p in Phase], default="supervised")
    parser.add_argument(
        "--localstack",
        nargs="?",
        const="http://localhost:4566",
        help="use LocalStack (make local-up) instead of in-process mocks",
    )
    parser.add_argument("--llm", choices=["replay", "bedrock"], default="replay")
    parser.add_argument(
        "--keep", action="store_true", help="keep the temp folder and print its path"
    )
    args = parser.parse_args(argv)

    incident = json.loads(Path(args.incident).read_text())
    registry = json.loads(Path(args.registry).read_text())
    work = Path(tempfile.mkdtemp(prefix="healer-demo-")) if args.keep else None
    print(
        f"incident: {incident['title']}  (service {incident['affectedService']}, "
        f"phase {args.phase}, model {args.llm})"
    )
    with local_services(
        registry=registry,
        replay=args.replay,
        llm_name=args.llm,
        phase=Phase(args.phase),
        work_dir=work,
        localstack=args.localstack,
    ) as (services, handles):
        result = run_pipeline(incident, services)
        print(describe(result))
        if result.pr:
            print("\n--- the pull request ---")
            print(Path(result.pr.url).read_text())
        if args.keep:
            print(f"\nkept: {handles['work']}")
    return 0 if result.outcome in ("pr_opened", "escalated", "shadow") else 1


if __name__ == "__main__":
    sys.exit(main())
