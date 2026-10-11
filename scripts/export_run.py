#!/usr/bin/env python3
"""Write everything one run left behind into a single Markdown file.

    AWS_PROFILE=... AWS_REGION=us-east-1 python scripts/export_run.py exec-7b31d8bd > run.md

Webhook log, pipe log, every Step Functions state with its input and output, every Lambda and
Fargate log in full, the ECS task details, the audit files and the final state. Read-only.
Do this before `scripts/teardown.sh`: the log groups are deleted with the stack.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from typing import Any

import boto3

STACK, STATE_STACK = "SelfHealingPipeline", "SelfHealingState"
LAMBDA_STATES = {
    "Ingest": "Ingest",
    "Route": "Route",
    "RouteAfterFix": "Route",
    "Escalate": "Notify",
    "OpenPr": "OpenPr",
    "Notify": "Notify",
}
FARGATE_STATES = {"Investigate": "investigate", "Fix": "fix", "Test": "test"}


def outputs(cfn: Any, stack: str) -> dict[str, str]:
    items = cfn.describe_stacks(StackName=stack)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in items}


def mask(text: str, account: str) -> str:
    return text.replace(account, "<account>")


def fence(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text.rstrip()}\n```\n"


def pretty(raw: str) -> str:
    try:
        return json.dumps(json.loads(raw), indent=2)
    except (TypeError, ValueError):
        return raw


def stream_events(logs: Any, group: str, stream: str) -> list[str]:
    out: list[str] = []
    try:
        token = None
        while True:
            kw: dict[str, Any] = {
                "logGroupName": group,
                "logStreamName": stream,
                "startFromHead": True,
            }
            if token:
                kw["nextToken"] = token
            page = logs.get_log_events(**kw)
            for e in page["events"]:
                stamp = datetime.fromtimestamp(e["timestamp"] / 1000).strftime("%H:%M:%S.%f")[:-3]
                out.append(f"{stamp}  {e['message'].rstrip()}")
            if page.get("nextForwardToken") in (None, token) or not page["events"]:
                break
            token = page["nextForwardToken"]
    except logs.exceptions.ResourceNotFoundException:
        out.append("(stream not found)")
    return out


def window_events(
    logs: Any, group: str, start: int, end: int, pattern: str | None = None
) -> list[str]:
    kw: dict[str, Any] = {"logGroupName": group, "startTime": start, "endTime": end, "limit": 200}
    if pattern:
        kw["filterPattern"] = pattern
    try:
        found = logs.filter_log_events(**kw)["events"]
    except logs.exceptions.ResourceNotFoundException:
        return ["(log group not found)"]
    return [
        f"{datetime.fromtimestamp(e['timestamp'] / 1000).strftime('%H:%M:%S.%f')[:-3]}  {e['message'].rstrip()}"
        for e in found
    ]


def main(execution_id: str) -> int:
    s = boto3.Session()
    region = s.region_name or "us-east-1"
    cfn, logs, sfn = s.client("cloudformation"), s.client("logs"), s.client("stepfunctions")
    s3, lam, ecs = s.client("s3"), s.client("lambda"), s.client("ecs")
    account = s.client("sts").get_caller_identity()["Account"]
    out, state_out = outputs(cfn, STACK), outputs(cfn, STATE_STACK)
    md: list[str] = []
    add = md.append

    machine = out["StateMachineArn"]
    execution = None
    for item in sfn.list_executions(stateMachineArn=machine, maxResults=100)["executions"]:
        d = sfn.describe_execution(executionArn=item["executionArn"])
        if execution_id in d.get("input", ""):
            execution = d
            break
    if execution is None:
        print(f"no execution carries {execution_id}", file=sys.stderr)
        return 1
    t0 = int(execution["startDate"].timestamp() * 1000) - 120_000
    t1 = (
        int(
            (execution.get("stopDate") or datetime.now(execution["startDate"].tzinfo)).timestamp()
            * 1000
        )
        + 60_000
    )

    add(f"# Run `{execution_id}`\n")
    add(
        f"Exported {datetime.now():%Y-%m-%d %H:%M} local time from region `{region}`. Account shown as `<account>`.\n"
    )
    add("| | |\n|---|---|")
    add(f"| Step Functions execution | `{execution['name']}` |")
    add(f"| Status | **{execution['status']}** |")
    add(f"| Started | {execution['startDate']:%H:%M:%S} |")
    add(f"| Stopped | {execution.get('stopDate') and execution['stopDate'].strftime('%H:%M:%S')} |")
    add(
        f"| Console | https://{region}.console.aws.amazon.com/states/home?region={region}#/v2/executions/details/{execution['executionArn']} |\n"
    )

    # 1. webhook
    add("## 1. Webhook Lambda (the front door)\n")
    for fn in lam.list_functions()["Functions"]:
        if "WebhookReceiver" in fn["FunctionName"]:
            group = lam.get_function_configuration(FunctionName=fn["FunctionName"])[
                "LoggingConfig"
            ]["LogGroup"]
            add(f"Log group `{group}`\n")
            add(
                fence(
                    "\n".join(window_events(logs, group, t0 - 300_000, t1, f'"{execution_id}"'))
                    or "(no line: this run was not started by the webhook)"
                )
            )

    # 3. pipe
    add("## 2. EventBridge Pipe (queue to Step Functions)\n")
    pipe_group = out.get("PipeLogGroup", "")
    add(f"Log group `{pipe_group}`. The first event holds the raw SQS record the pipe read.\n")
    add(fence(mask("\n".join(window_events(logs, pipe_group, t0, t1)), account)))

    # 4. states
    add("## 3. Step Functions: every state, its time, input and output\n")
    history = sfn.get_execution_history(executionArn=execution["executionArn"], maxResults=1000)[
        "events"
    ]
    entered: dict[str, tuple[Any, str]] = {}
    exited: dict[str, tuple[Any, str]] = {}
    task_ids: dict[str, str] = {}
    order: list[str] = []
    last_state = ""
    for ev in history:
        if "stateEnteredEventDetails" in ev:
            d = ev["stateEnteredEventDetails"]
            last_state = d["name"]
            order.append(last_state)
            entered[last_state] = (ev["timestamp"], d.get("input", ""))
        elif "stateExitedEventDetails" in ev:
            d = ev["stateExitedEventDetails"]
            exited[d["name"]] = (ev["timestamp"], d.get("output", ""))
        elif ev["type"] == "TaskSubmitted":
            try:
                arn = json.loads(ev["taskSubmittedEventDetails"].get("output", "{}"))["Tasks"][0][
                    "TaskArn"
                ]
                task_ids[last_state] = arn.rsplit("/", 1)[-1]
            except (KeyError, IndexError, ValueError):
                pass
    add("| State | Started | Seconds |\n|---|---|---|")
    for name in order:
        a, b = entered[name][0], exited.get(name, (None,))[0]
        add(
            f"| {name} | {a:%H:%M:%S} | {(b - a).total_seconds():.1f} |"
            if b
            else f"| {name} | {a:%H:%M:%S} | - |"
        )
    add("")
    for name in order:
        if name in LAMBDA_STATES or name in FARGATE_STATES:
            add(f"### {name}\n")
            add("Input:\n")
            add(fence(pretty(entered[name][1]), "json"))
            add("Output:\n")
            add(fence(pretty(exited.get(name, (None, ""))[1]), "json"))

    # 5. lambda logs
    add("## 4. Lambda logs (full)\n")
    for name in order:
        if name not in LAMBDA_STATES:
            continue
        match = next(
            (
                f["FunctionName"]
                for f in lam.list_functions()["Functions"]
                if f"SelfHealingPipeline-{LAMBDA_STATES[name]}" in f["FunctionName"]
            ),
            None,
        )
        if not match:
            continue
        group = lam.get_function_configuration(FunctionName=match)["LoggingConfig"]["LogGroup"]
        begin = int(entered[name][0].timestamp() * 1000) - 2000
        finish = int(exited.get(name, (entered[name][0],))[0].timestamp() * 1000) + 5000
        add(f"### {name}: function `{match}`, log group `{group}`\n")
        add(
            fence(
                "\n".join(
                    line
                    for line in window_events(logs, group, begin, finish)
                    if "INIT_START" not in line
                )
            )
        )

    # 6. fargate
    add("## 5. Fargate task logs (full) and task details\n")
    agent_group = out.get("AgentLogGroup", "")
    clusters = ecs.list_clusters()["clusterArns"]
    for name in order:
        if name not in FARGATE_STATES:
            continue
        task_id = task_ids.get(name, "")
        stream = f"{FARGATE_STATES[name]}/healer-{FARGATE_STATES[name]}/{task_id}"
        add(f"### {name}: task `{task_id}`, stream `{stream}`\n")
        for c in clusters:
            try:
                t = ecs.describe_tasks(cluster=c, tasks=[task_id])["tasks"]
            except Exception:  # noqa: BLE001
                t = []
            if t:
                t = t[0]
                add(
                    f"CPU {t['cpu']} / memory {t['memory']} MB, exit code **{t['containers'][0].get('exitCode')}**, started {t['startedAt']:%H:%M:%S}, stopped {t['stoppedAt']:%H:%M:%S}, role `{t.get('overrides', {}).get('taskRoleArn') or 'from the task definition'}`.\n"
                )
                add(
                    f"Console: https://{region}.console.aws.amazon.com/ecs/v2/clusters/{c.rsplit('/', 1)[-1]}/tasks/{task_id}/configuration?region={region}\n"
                )
        add(f"CloudWatch: log group `{agent_group}`, stream above.\n")
        add(fence(mask("\n".join(stream_events(logs, agent_group, stream)), account)))

    # 7. audit + state
    add("## 6. Audit trail (S3) and the final state\n")
    audit_bucket, state_bucket = (
        state_out.get("AuditBucketName", ""),
        state_out.get("StateBucketName", ""),
    )
    if audit_bucket:
        for obj in s3.list_objects_v2(Bucket=audit_bucket, Prefix=f"audit/{execution_id}/").get(
            "Contents", []
        ):
            add(f"### `{obj['Key']}`\n")
            add(
                fence(
                    pretty(
                        s3.get_object(Bucket=audit_bucket, Key=obj["Key"])["Body"].read().decode()
                    ),
                    "json",
                )
            )
    if state_bucket:
        try:
            body = (
                s3.get_object(Bucket=state_bucket, Key=f"pipeline-state/{execution_id}/state.json")[
                    "Body"
                ]
                .read()
                .decode()
            )
            add(f"### Final state `pipeline-state/{execution_id}/state.json`\n")
            add(fence(pretty(body), "json"))
        except s3.exceptions.NoSuchKey:
            add("(no state file)\n")
    sys.stdout.write(mask("\n".join(md), account) + "\n")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or not re.fullmatch(r"exec-[0-9a-f]+", sys.argv[1]):
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
