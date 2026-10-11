# How to see everything a run did

Every box in the architecture leaves something you can read. This page says where, in the AWS console and from the command
line, and what you should see when it is working. The recorded example is run `exec-7b31d8bd`: see
[runs/exec-7b31d8bd.md](runs/exec-7b31d8bd.md) (every log, input and output, saved as text) and the guided tour in
[aws-walkthrough.md](aws-walkthrough.md).

**Region us-east-1. Console times are UTC; this account's local time was Chicago (CDT, UTC minus 5).**
Sign in to the AWS account first; links do nothing without a session.

## The fastest ways

| I want to | Do this |
|---|---|
| See the whole run as a picture | Step Functions console, the state machine, the newest execution, *Graph view* |
| Print one run as text | `AWS_PROFILE=... python scripts/trace.py exec-XXXXXXXX` |
| Save one run's every log to a file | `AWS_PROFILE=... python scripts/export_run.py exec-XXXXXXXX > run.md` |
| Find the newest run id | the `executionId` in the webhook response, or the newest object under `audit/` in the audit bucket |
| Save it before tearing down | run `export_run.py` first: the log groups are deleted with the stack |

## Where each box's evidence is

| Box | What to open | What you should see |
|---|---|---|
| **Sentry** (the source) | Sentry website: the issue under *Issues*; the integration's **Request Log** (Settings, Developer Settings, Custom Integrations); the alert rule under *Alerts* | the issue, and one delivery per alert with our response code (`202`) |
| **API Gateway** `/webhook` | API Gateway console, the API, *Stages*, *prod* (no access log is kept) | the URL Sentry calls. The Lambda log below is the receipt |
| **Webhook Lambda** | CloudWatch, log group `SelfHealingPipeline-WebhookReceiverLogs…`, newest stream | one line `{"hop": "webhook->sns", "execution_id": ..., "sns_message_id": ...}` |
| **SNS** | SNS console, topic `SelfHealingPipeline-TriggerTopic…`, *Subscriptions* | one subscription: the SQS queue, protocol `sqs`. SNS keeps no copy of messages, so the evidence is the Lambda line above |
| **SQS** | SQS console, queue `SelfHealingPipeline-TriggerQueue…`, *Send and receive messages*, **Poll for messages**, click the message id, *Body* | the incident JSON. **Poll once** (3 receives send it to the dead-letter queue). Normally the pipe takes the message within a second, so the queue is empty |
| **Dead-letter queue** | SQS console, queue `…TriggerDeadLetters…` | empty. A message here means 3 failed deliveries |
| **EventBridge Pipe** | EventBridge console, *Pipes*, `TriggerPipe-…`; log group `SelfHealingPipeline-PipeLogs…` | four events: `ExecutionStarted` (holds the raw SQS record), `TargetStageEntered`, `TargetStageSucceeded`, `ExecutionSucceeded` |
| **Step Functions** | Step Functions console, the state machine, the execution. Click a state: *Input*, *Output*, *Details* | green states in order; durations; each state's JSON |
| **Ingest / Route / OpenPr / Notify (Lambda)** | In the execution's state table, the *Logs* link on each row; or CloudWatch log groups `…IngestLogs…`, `…RouteLogs…`, `…OpenPrLogs…`, `…NotifyLogs…` | one JSON line per step, a `StageSeconds` metric line, and a `REPORT` line with duration and memory |
| **Investigate / Fix / Test (Fargate)** | ECS console, the cluster, *Tasks*, filter **Stopped**; log group `SelfHealingPipeline-AgentLogs…`, streams `investigate/…`, `fix/…`, `test/…` | *Exit code 0* and 2 to 3 log lines per task |
| **Audit trail** | S3, bucket `self-healing-pipeline-audit-logs-<account>`, folder `audit/exec-…/` | `step_001_ingest.json` … `step_006_pr.json`, one file per step |
| **Run state** | S3, bucket `self-healing-pipeline-state-<account>`, `pipeline-state/exec-…/state.json` | the full decision: composite, band, blast radius, flags, branch, PR url |
| **Learning loop** | DynamoDB, tables `…TrustLedger…` and `…RemediationHistory…`, *Explore items* | one row per run; `human_verdict` is `pending` until the PR is merged or closed |
| **The result** | GitHub, the repository's *Pull requests* | a PR named `[HEALER] fix: …` (or `[HEALER] investigation: …`) from a `healer/…` branch |

## Fargate task logs: use CloudWatch, not the ECS "Logs" tab

The ECS console's **Logs** tab on a stopped task can show nothing even though the logs exist. The logs are in CloudWatch:

1. CloudWatch console, *Log groups*, open `SelfHealingPipeline-AgentLogs…`.
2. Open the stream whose name ends in the task id (the id is in the ECS task page URL, or in the Step Functions state's *Details*).
3. If the page looks empty, widen the time range at the top (try *1h* or *Custom*).

To find a task: ECS console, the cluster `SelfHealingPipeline-Cluster…`, *Tasks* tab, change the filter to **Stopped** (finished
tasks are not shown under *Running*). Open one for its exit code, CPU and memory, and start and stop times.

## From the command line

```bash
export AWS_PROFILE=...  AWS_REGION=us-east-1

# the newest Step Functions executions
aws stepfunctions list-executions --max-results 5 \
  --state-machine-arn $(aws stepfunctions list-state-machines --query 'stateMachines[0].stateMachineArn' --output text)

# a Fargate task's log (stream = <stage>/healer-<stage>/<task id>)
aws logs get-log-events --log-group-name <AgentLogs group> --log-stream-name investigate/healer-investigate/<task id> --start-from-head

# a Lambda's recent log
aws logs tail <log group name> --since 30m

# the message waiting in the queue (peek: it stays in the queue)
aws sqs receive-message --queue-url <TriggerQueue url> --visibility-timeout 0 --max-number-of-messages 1
```

The group, queue and topic names change on every deploy. `aws cloudformation describe-stacks --stack-name SelfHealingPipeline
--query 'Stacks[0].Outputs'` lists the current ones.

## How to tell a healthy run from a broken one

| Healthy | Broken |
|---|---|
| every state green; final state `PullRequestOpened` (or `EscalatedToHuman`) | a red state, or the path `NotifyFailure…` then `Fail` |
| Fargate exit code 0 | exit code 1: read that stream, the last lines are the traceback |
| webhook answers 202 | 401 means the signature or timestamp failed; 502 means the Lambda crashed (read its log) |
| `ingest` output `status: running` | `rate_limited` (3 per service per hour) or `blocked` (the classifier) |
| queue empty, dead-letter queue empty | messages in the dead-letter queue |
| `Succeeded` plus a PR | `Succeeded` does not mean the fix is good. Read the PR: failed tests make it a draft |
