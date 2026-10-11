#!/usr/bin/env python3
"""Follow one execution through every hop, with the evidence at each one.

    AWS_PROFILE=... python scripts/trace.py exec-1a2b3c4d

Front door (API Gateway, webhook Lambda), SNS, SQS, the EventBridge Pipe, Step Functions, every
state's Lambda or Fargate task logs, the audit trail, and the final state. Each section ends with
a link to the same thing in the AWS console. Read-only: it changes nothing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

import boto3

STACK = "SelfHealingPipeline"
STATE_STACK = "SelfHealingState"


def title(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def short(value: Any, limit: int = 600) -> str:
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= limit else text[:limit] + f"... [{len(text)} chars]"


def stack_outputs(cfn: Any, name: str) -> dict[str, str]:
    out = cfn.describe_stacks(StackName=name)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in out}


def log_group_of(lam: Any, function_name: str) -> str:
    """Each function writes to a log group the stack created, not to /aws/lambda/<name>."""
    config = lam.get_function_configuration(FunctionName=function_name)
    return config.get("LoggingConfig", {}).get("LogGroup") or f"/aws/lambda/{function_name}"


def console(region: str, path: str) -> str:
    return f"https://{region}.console.aws.amazon.com/{path}"


def events(
    logs: Any,
    group: str,
    start_ms: int,
    end_ms: int,
    pattern: str | None = None,
    stream_prefix: str | None = None,
    limit: int = 40,
) -> list[str]:
    kwargs: dict[str, Any] = {
        "logGroupName": group,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
    }
    if pattern:
        kwargs["filterPattern"] = pattern
    if stream_prefix:
        kwargs["logStreamNamePrefix"] = stream_prefix
    try:
        found = logs.filter_log_events(**kwargs)["events"]
    except logs.exceptions.ResourceNotFoundException:
        return []
    return [
        f"{datetime.fromtimestamp(e['timestamp'] / 1000):%H:%M:%S}  {e['message'].rstrip()}"
        for e in found
    ]


def main(execution_id: str) -> int:
    session = boto3.Session()
    region = session.region_name or "us-east-1"
    cfn, logs = session.client("cloudformation"), session.client("logs")
    sfn, s3 = session.client("stepfunctions"), session.client("s3")
    sqs, lam = session.client("sqs"), session.client("lambda")
    out, state_out = stack_outputs(cfn, STACK), stack_outputs(cfn, STATE_STACK)

    # ---- locate the Step Functions execution whose input carries this id
    machine = out["StateMachineArn"]
    execution = None
    for item in sfn.list_executions(stateMachineArn=machine, maxResults=50)["executions"]:
        described = sfn.describe_execution(executionArn=item["executionArn"])
        if execution_id in described.get("input", ""):
            execution = described
            break
    if execution is None:
        print(f"no Step Functions execution carries {execution_id}")
        return 1
    started = int(execution["startDate"].timestamp() * 1000) - 60_000
    ended = (
        int(
            (execution.get("stopDate") or datetime.now(execution["startDate"].tzinfo)).timestamp()
            * 1000
        )
        + 60_000
    )

    title(f"1. FRONT DOOR: API Gateway -> WebhookReceiver Lambda        ({execution_id})")
    print("Sentry POSTs to:", out.get("WebhookUrl"))
    webhook_group = ""
    for fn in lam.list_functions()["Functions"]:
        if "WebhookReceiver" in fn["FunctionName"]:
            webhook_group = log_group_of(lam, fn["FunctionName"])
    lines = events(logs, webhook_group, started - 300_000, ended, pattern=f'"{execution_id}"')
    print(
        "\n".join(lines)
        or "(no webhook log line: this run was started directly on the state machine)"
    )
    print(
        "console:",
        console(
            region,
            f"cloudwatch/home?region={region}#logsV2:log-groups/log-group/{webhook_group.replace('/', '$252F')}",
        ),
    )

    title("2. SNS: the topic the receiver published to (fan-out point)")
    print("topic:", out.get("TriggerTopicArn"))
    hop = [line for line in lines if "webhook->sns" in line]
    print(hop[0] if hop else "(SNS keeps no copy of a message; the publish is the line above)")
    print(
        "console:",
        console(region, f"sns/v3/home?region={region}#/topic/{out.get('TriggerTopicArn')}"),
    )

    title("3. SQS: the queue subscribed to the topic (raw delivery) and its dead-letter queue")
    queue_url = out.get("TriggerQueueUrl", "")
    if queue_url:
        attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])["Attributes"]
        print(f"queue: {queue_url}")
        print(
            f"  waiting={attrs.get('ApproximateNumberOfMessages')}  in-flight={attrs.get('ApproximateNumberOfMessagesNotVisible')}"
            f"  (0 and 0 means the pipe already took every message)"
        )
        redrive = json.loads(attrs.get("RedrivePolicy", "{}"))
        print(
            f"  dead-letter after {redrive.get('maxReceiveCount')} failed deliveries -> {redrive.get('deadLetterTargetArn')}"
        )
    print("console:", console(region, f"sqs/v3/home?region={region}#/queues"))

    title("4. EVENTBRIDGE PIPE: read from the queue, reshaped, started the workflow")
    pipe_group = out.get("PipeLogGroup", "")
    pipe_lines = (
        events(logs, pipe_group, started - 300_000, ended, pattern=f'"{execution_id}"', limit=15)
        if pipe_group
        else []
    )
    print("\n".join(short(line, 900) for line in pipe_lines) or "(no pipe log line for this run)")
    print("console:", console(region, f"events/home?region={region}#/pipes"))

    title("5. STEP FUNCTIONS: the workflow")
    print("execution:", execution["executionArn"])
    print("status   :", execution["status"])
    print("input    :", short(execution["input"], 400))
    history = sfn.get_execution_history(executionArn=execution["executionArn"], maxResults=500)[
        "events"
    ]
    entered: dict[str, Any] = {}
    task_arns: dict[str, str] = {}
    windows: list[tuple[str, int, int]] = []
    for ev in history:
        stamp = ev["timestamp"]
        if "stateEnteredEventDetails" in ev:
            name = ev["stateEnteredEventDetails"]["name"]
            entered[name] = stamp
            print(f"  {stamp:%H:%M:%S}  enter  {name}")
        elif "stateExitedEventDetails" in ev:
            name = ev["stateExitedEventDetails"]["name"]
            took = (stamp - entered[name]).total_seconds() if name in entered else 0
            print(f"  {stamp:%H:%M:%S}  exit   {name}   ({took:.1f}s)")
            windows.append(
                (
                    name,
                    int(entered[name].timestamp() * 1000) - 2000,
                    int(stamp.timestamp() * 1000) + 5000,
                )
            )
        elif ev["type"] == "TaskSubmitted":
            details = ev.get("taskSubmittedEventDetails", {})
            try:
                task_arns[str(ev["id"])] = json.loads(details.get("output", "{}")).get(
                    "TaskArn", ""
                )
            except ValueError:
                pass
        elif ev["type"] in ("ExecutionFailed", "TaskFailed", "LambdaFunctionFailed"):
            print("  FAILURE:", short(ev, 500))
    print(
        "console:",
        console(
            region,
            f"states/home?region={region}#/v2/executions/details/{execution['executionArn']}",
        ),
    )

    title("6. EACH STATE'S OWN LOGS")
    lambdas = {
        "Ingest": "Ingest",
        "Route": "Route",
        "RouteAfterFix": "Route",
        "OpenPr": "OpenPr",
        "Notify": "Notify",
        "Escalate": "Notify",
    }
    functions = {fn["FunctionName"]: fn for fn in lam.list_functions()["Functions"]}
    for name, begin, finish in windows:
        if name in lambdas:
            match = next(
                (f for f in functions if lambdas[name] in f and "SelfHealingPipeline" in f), None
            )
            if match:
                print(f"\n--- {name}  (Lambda {match})")
                for line in events(logs, log_group_of(lam, match), begin, finish, limit=12):
                    if "START" in line or "END" in line or "REPORT" in line:
                        continue
                    print("  " + short(line, 400))
    agent_group = out.get("AgentLogGroup", "")
    for name, begin, finish in windows:
        if name in ("Investigate", "Fix", "Test") and agent_group:
            print(f"\n--- {name}  (Fargate task, log group {agent_group})")
            for line in events(
                logs, agent_group, begin, finish, stream_prefix=name.lower(), limit=40
            ):
                print("  " + short(line, 300))
    print("\nconsole:", console(region, f"ecs/v2/clusters?region={region}"))
    print("         ", console(region, f"cloudwatch/home?region={region}#logsV2:log-groups"))

    title("7. AUDIT TRAIL (S3, one file per step) and the final state")
    audit_bucket = state_out.get("AuditBucketName", "")
    state_bucket = state_out.get("StateBucketName", "")
    if audit_bucket:
        listing = s3.list_objects_v2(Bucket=audit_bucket, Prefix=f"audit/{execution_id}/").get(
            "Contents", []
        )
        for obj in listing:
            body = json.loads(s3.get_object(Bucket=audit_bucket, Key=obj["Key"])["Body"].read())
            print(f"  {obj['Key'].split('/')[-1]:<34} output={short(body.get('output'), 160)}")
    if state_bucket:
        try:
            state = json.loads(
                s3.get_object(Bucket=state_bucket, Key=f"pipeline-state/{execution_id}/state.json")[
                    "Body"
                ].read()
            )
            print(f"\nfinal status : {state['status']}  ({state['reason'][:120]})")
            print(
                f"composite    : {state['composite']}  action={state['decision']['fix_action']}  blast={state['decision']['blast_radius']['tier']}"
            )
            print(f"review flags : {state['review_flags']}")
            print(f"branch / PR  : {state['branch']} / {state['pr'] and state['pr']['url']}")
        except s3.exceptions.NoSuchKey:
            print("(no state file yet)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
