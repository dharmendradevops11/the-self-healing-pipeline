#!/usr/bin/env python3
"""Drive each flow of a deployed pipeline, for testing. Sandbox use: it writes test data.

    AWS_PROFILE=... AWS_REGION=us-east-1 python scripts/test_flows.py <command>

  seed-logs                     write realistic application log lines to /aws/ecs/<service>
  alert happy                   send an error to Sentry that the pipeline can fix   (needs SENTRY_DSN)
  alert escalate                send an error with no trace from an unknown service (needs SENTRY_DSN)
  forged                        POST a request with a wrong signature: expect 401, nothing runs
  duplicate                     start a run for a Sentry issue already taken: expect "duplicate"
  reset-limits                  clear the hourly limiter, the daily PR cap and the issue markers
  wait                          wait for the newest run and print its path, decision and PR
  status                        print the newest run without waiting

SENTRY_DSN is the project's public DSN (Sentry: Settings, Client Keys). It is not a secret credential.
Each command prints what it did and what to expect. Nothing here merges or deletes anything real.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3

STACK, STATE_STACK = "SelfHealingPipeline", "SelfHealingState"


def outputs(name: str) -> dict[str, str]:
    cfn = boto3.client("cloudformation")
    return {
        o["OutputKey"]: o["OutputValue"]
        for o in cfn.describe_stacks(StackName=name)["Stacks"][0]["Outputs"]
    }


def table(fragment: str) -> Any:
    db = boto3.resource("dynamodb")
    names = [n for n in db.meta.client.list_tables()["TableNames"] if fragment in n]
    return db.Table(names[0])


def seed_logs(service: str = "demo-app") -> None:
    logs = boto3.client("logs")
    group = f"/aws/ecs/{service}"
    try:
        logs.create_log_group(logGroupName=group)
        logs.put_retention_policy(logGroupName=group, retentionInDays=1)
    except logs.exceptions.ResourceAlreadyExistsException:
        pass
    stream = f"{service}/web/{datetime.now():%H%M%S}"
    logs.create_log_stream(logGroupName=group, logStreamName=stream)
    now = time.time()
    stamp = lambda t: datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    lines = [
        (now - 110 + i * 4, f"{stamp(now - 110 + i * 4)} INFO request {i} ok user={1000 + i}")
        for i in range(26)
    ]
    lines += [
        (now - 9, f"{stamp(now - 9)} WARN profile lookup returned None for user=2041"),
        (
            now - 7,
            f"{stamp(now - 7)} ERROR AttributeError in get_display_name: 'NoneType' object has no attribute 'name' user=2041",
        ),
        (
            now - 6,
            f"{stamp(now - 6)} ERROR request failed for first-time user user=2041 status=500",
        ),
    ]
    logs.put_log_events(
        logGroupName=group,
        logStreamName=stream,
        logEvents=[{"timestamp": int(t * 1000), "message": m} for t, m in sorted(lines)],
    )
    print(f"wrote {len(lines)} lines to {group}, stream {stream}.")
    print("Send the alert within ~10 minutes: INGEST reads the last 20 lines before the failure.")


def send_alert(kind: str) -> None:
    dsn = os.environ.get("SENTRY_DSN", "")
    match = re.match(r"https://(\w+)@([^/]+)/(\d+)", dsn)
    if not match:
        sys.exit("set SENTRY_DSN (Sentry: Settings, Client Keys (DSN))")
    key, host, project = match.groups()
    tag = datetime.now().strftime("%H%M%S")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if kind == "happy":
        service, message = (
            "demo-app",
            f"AttributeError: 'NoneType' object has no attribute 'name' (test {tag})",
        )
        exception = {
            "values": [
                {
                    "type": "AttributeError",
                    "value": message,
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "src/auth.py",
                                "abs_path": "src/auth.py",
                                "lineno": 28,
                                "function": "greet",
                                "in_app": True,
                            },
                            {
                                "filename": "src/auth.py",
                                "abs_path": "src/auth.py",
                                "lineno": 24,
                                "function": "get_display_name",
                                "in_app": True,
                            },
                        ]
                    },
                }
            ]
        }
    else:
        service, message, exception = (
            "mystery-service",
            f"Error: something went wrong (test {tag})",
            None,
        )
    event: dict[str, Any] = {
        "event_id": uuid.uuid4().hex,
        "timestamp": now,
        "platform": "python",
        "level": "error",
        "logger": service,
        "server_name": service,
        "message": message,
        "tags": {"service": service, "source": "self-healing-pipeline-test"},
        "fingerprint": [
            f"healer-test-{kind}-{tag}"
        ],  # a new fingerprint is a new issue, so the alert rule fires
    }
    if exception:
        event["exception"] = exception
    request = urllib.request.Request(
        f"https://{host}/api/{project}/store/",
        data=json.dumps(event).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Sentry-Auth": f"Sentry sentry_version=7, sentry_key={key}, sentry_client=healer-test/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as reply:
        print(f"sent a {kind!r} error to Sentry: HTTP {reply.status}, service tag {service!r}")
    print(
        "Expect: Sentry creates an issue, your alert rule fires, the webhook runs, a Step Functions run starts in ~30 s."
    )
    print("Then:   python scripts/test_flows.py wait")


def forged() -> None:
    url = outputs(STACK)["WebhookUrl"]
    body = json.dumps({"action": "created", "data": {"issue": {"title": "forged"}}}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "sentry-hook-signature": "0" * 64,
            "sentry-hook-timestamp": str(int(time.time())),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            print("UNEXPECTED: accepted", reply.status)
    except urllib.error.HTTPError as err:
        print(f"HTTP {err.code} {err.read().decode()}")
        print("Expect: 401 invalid signature, and no new Step Functions run.")


def duplicate() -> None:
    marker = f"dup-{uuid.uuid4().hex[:8]}"
    table("RateLimit").put_item(
        Item={
            "service": f"sentry-issue#{marker}",
            "hour": "claimed",
            "expires_at": int(time.time()) + 3600,
        }
    )
    run = f"exec-{uuid.uuid4().hex[:8]}"
    incident = {
        "source": "sentry",
        "severity": "high",
        "type": "crash",
        "title": "duplicate test",
        "stackTrace": "duplicate test",
        "affectedService": "demo-app",
        "triggeredAt": datetime.now(UTC).isoformat(),
        "sentryIssueId": marker,
    }
    sfn = boto3.client("stepfunctions")
    sfn.start_execution(
        stateMachineArn=outputs(STACK)["StateMachineArn"],
        name=f"dup-{run}",
        input=json.dumps({"executionId": run, "incident": incident}),
    )
    print(f"issue {marker} was already marked as taken; started run {run} for it.")
    print("Expect: the run ends at Ingest with status 'duplicate' and no PR (about 5 seconds).")
    time.sleep(12)
    show_latest(wait=False)


def reset_limits() -> None:
    for fragment in ("RateLimit", "Throttle"):
        t = table(fragment)
        keys = [k["AttributeName"] for k in t.key_schema]
        items = t.scan()["Items"]
        for item in items:
            t.delete_item(Key={k: item[k] for k in keys})
        print(f"cleared {len(items)} items from {t.name}")


def show_latest(wait: bool) -> None:
    sfn, s3 = boto3.client("stepfunctions"), boto3.client("s3")
    machine = outputs(STACK)["StateMachineArn"]
    latest = sfn.list_executions(stateMachineArn=machine, maxResults=1)["executions"][0]
    arn = latest["executionArn"]
    while wait and sfn.describe_execution(executionArn=arn)["status"] == "RUNNING":
        time.sleep(10)
    described = sfn.describe_execution(executionArn=arn)
    payload = json.loads(described["input"])
    payload = payload[0] if isinstance(payload, list) else payload
    run = payload["executionId"]
    history = sfn.get_execution_history(executionArn=arn, maxResults=500)["events"]
    path = [
        e["stateEnteredEventDetails"]["name"] for e in history if "stateEnteredEventDetails" in e
    ]
    print(f"run {run}: {described['status']}\npath: {' -> '.join(path)}")
    try:
        state = json.loads(
            s3.get_object(
                Bucket=outputs(STATE_STACK)["StateBucketName"],
                Key=f"pipeline-state/{run}/state.json",
            )["Body"].read()
        )
        decision = state.get("decision") or {}
        print(
            f"decision: composite {state.get('composite')}, {decision.get('fix_action')}, status {state['status']}"
            f" ({state['reason'][:70]})"
        )
        print(
            f"log lines attached: {len(state['log_lines'])}; review flags: {len(state['review_flags'])}"
        )
        print(f"PR: {(state.get('pr') or {}).get('url')}")
    except s3.exceptions.NoSuchKey:
        print("(no state file: the run ended before INGEST saved one)")
    print(f"details: python scripts/trace.py {run}")


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
    elif argv[0] == "seed-logs":
        seed_logs(argv[1] if len(argv) > 1 else "demo-app")
    elif argv[0] == "alert" and len(argv) == 2 and argv[1] in ("happy", "escalate"):
        send_alert(argv[1])
    elif argv[0] == "forged":
        forged()
    elif argv[0] == "duplicate":
        duplicate()
    elif argv[0] == "reset-limits":
        reset_limits()
    elif argv[0] == "wait":
        show_latest(wait=True)
    elif argv[0] == "status":
        show_latest(wait=False)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
