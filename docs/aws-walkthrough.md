# AWS walkthrough: one alert, hop by hop

A real run on a real AWS account, one hop at a time, with the request or log line at each. Recorded 2026-10-09
(us-east-1). Step 1 was captured for `exec-73ff3286`; from Step 2 on the walkthrough follows `exec-7b31d8bd`, the same
alert sent again (see the note under the status table). The account number is shown as `<account>`.

Same flow as Figure 2.1:

```
Sentry ─► API Gateway ─► Webhook Lambda ─► SNS ─► SQS ─► EventBridge Pipe ─► Step Functions
                                                                              ├─ Ingest      (Lambda)
                                                                              ├─ Investigate (Fargate)
                                                                              ├─ Route       (Lambda)
                                                                              ├─ Fix         (Fargate)
                                                                              ├─ Test        (Fargate)
                                                                              ├─ OpenPr      (Lambda)
                                                                              └─ Notify      (Lambda)
```

## Start here: the flows and where each is recorded

Run IDs, PRs and the order things happened are in the sections below. Each section ends with a "how to check it yourself" table.

| Flow | Section | Run | PR |
|---|---|---|---|
| The alert's journey, hop by hop: Sentry, API Gateway, SNS, SQS, Pipe, Step Functions | Real Sentry as the source; Steps 1 to 6 | `exec-18c81a71`, `exec-7b31d8bd`, `exec-4fb06009`, `exec-62698225` | #15, #10, #11, #16 |
| INGEST reading real CloudWatch log lines | The CloudWatch Logs hop | `exec-810f0a1b` | #17 |
| Below 60: Escalate (report-only PR and message) | The Escalate branch; Escalate reaching Slack | `exec-4898e06c`, `exec-633686c4` | #18, #20 |
| Notify to Slack | Slack | `exec-ec2eb471` | #19 |
| A human merges and the ledger learns | Human merges the PR | `exec-ec2eb471` | #19 (merged) |
| A duplicate alert, a forged webhook | Other flows: duplicate, forged, failure | `exec-307c9e03` | none |
| The fix already on `main` (the model declines a patch) | Test each flow yourself, note under the table | `exec-522182e6` | #21 |

**Reading order for the alert's journey:** Real Sentry as the source, then Steps 1 to 6 (they were recorded on slightly different runs; each
says which). The sections after that are the other flows.

**Files that go with this one**

| File | What it is |
|---|---|
| [runs/](runs/) | every log, input and output of each run, saved as text (survives teardown) |
| [viewing-logs.md](viewing-logs.md) | how to read each console page |
| [sentry-setup.md](sentry-setup.md) | connecting Sentry |
| [aws-test-log.md](aws-test-log.md) | the earlier AWS tests, the bugs only AWS could find |
| `scripts/test_flows.py`, `trace.py`, `export_run.py` | test, trace and export |

---

## Coverage against Figure 2.1 (what is shown in this file, what is not)

Box by box, against the architecture figure. "Shown" means the request or log is recorded here with where to see it in the console.

| Box in Figure 2.1 | Status | Where in this file |
|---|---|---|
| Sentry Error Event, Webhook | shown, with **real Sentry** (the error itself is a test event sent through Sentry's ingest) | Real Sentry as the source; Step 1 |
| AWS SNS (fan-out) | shown | Step 1, Step 2 |
| AWS SQS Queue | shown; the message was read raw | Step 2 |
| Trigger (EventBridge Pipe) | shown | Step 3 |
| AWS Step Functions | shown, every state with time, input and output | Steps 3 to 6 |
| Step 1 INGEST: Lambda Log Enrichment | shown | Step 4 |
| Pull last 20 lines from CloudWatch Logs | shown, with a real log group and 29 real lines | The CloudWatch Logs hop |
| Step 2 INVESTIGATE: Fargate Clone and Analyze | shown | Step 4 |
| Query and Confidence Score, Bedrock: Claude Sonnet | shown (the model call has no log of its own; see "The Bedrock hop") | Step 4; The Bedrock hop |
| Score at or above 60: FIX task, apply patch, push `healer/` branch | shown, with the diff and the commits | Step 5 |
| Step 3 TEST: Fargate Unit Test and Lint | shown, including pytest's own output | Step 5 |
| Step 4 PR: Lambda Open PR, GitHub Pull Request (Report and Diff) | shown, PR checked on GitHub | Step 6 |
| Notify, Slack Channel | shown: the message goes to **SNS and to Slack** (Slack answered HTTP 200). The SNS email subscription is still unconfirmed | Step 6; Slack |
| Score below 60: Escalate / Slack | shown: real runs took this branch. The message goes to **SNS and Slack** (Slack answered 200) | The Escalate branch; Escalate to Slack |
| Human Merges PR | **not done yet** (a person does it) | **remaining** |
| Production Deploy | outside this pipeline: your own deploy process, after a merge | n/a |
| The learning loop (GitHub webhook to the trust ledger) | shown: `pending` became `approved` | Human merges the PR |

### What is left

Every box in Figure 2.1 up to "Human Merges PR" is now shown and recorded. Open items:

1. **Confirm the SNS email subscription** (still `PendingConfirmation`; not drawn in the figure), then run flow 1 to see it delivered.
2. **Reset the demo repository's `main`** to its first commit so flow 1 produces a fix again (the fix from PR #19 is on `main`).
3. **Replace the Slack webhook URL** that was pasted into a chat.
4. **Export the logs and tear the sandbox down** (`scripts/teardown.sh`).

### One thing that is easy to misread: when the PR appears

The walkthrough takes the pipeline's states one at a time, but the pipeline does not wait: a whole run takes 3 to 4 minutes and
finishes on its own. We read the runs afterwards, so PRs from earlier runs were already on GitHub. **A PR is created only in the
OpenPr state (Step 6).** Steps 1 to 4 read and decide; Step 5 pushes a branch, which is not a PR. Compare any PR's creation time with the
OpenPr row of its execution: they agree to within seconds. Each run opens its own PR (`exec-7b31d8bd` opened #10, `exec-4fb06009` #11,
`exec-18c81a71` #15, `exec-62698225` #16).

### The Bedrock hop

Calling Claude leaves no log line of its own: Bedrock model-invocation logging is off, deliberately, because it would store prompts
(which hold incident text and source code). The evidence is in three places:

| Evidence | Where |
|---|---|
| What each stage asked and decided | the stage's own log and the audit file, not the raw prompt: `audit/<exec>/step_002_investigate.json` (root cause, certainty, composite) and `step_003_fix.json` (fix type, files, tests shown) |
| That the call happened, and how often | CloudWatch, **Metrics**, namespace `AWS/Bedrock`, metric `Invocations`, dimension `ModelId = us.anthropic.claude-sonnet-4-5-20250929-v1:0`. Also `InvocationLatency`, `InputTokenCount`, `OutputTokenCount` |
| Which model and region | the stack setting `healer:bedrock_model_id` (`BEDROCK_MODEL_ID` in each function and task); the model is configuration, not code |

A run makes **three** model calls: the injection classifier in INGEST (the same model, since no quick model is configured), the
diagnosis in INVESTIGATE, and the patch in FIX. In the hour these runs were made, the metric shows 12 invocations for the Sonnet 4.5
profile, consistent with four runs. (The same account also shows earlier test traffic.)

---

## Every log, with its CloudWatch URL

Region us-east-1, account <account> (sign in first). These work while the sandbox stack exists; **they stop working after teardown**
(the log groups are deleted with the stack), so every run's logs are also saved as text in [runs/](runs/).
Open a group, then its **newest stream**. Times in the console are UTC.

| Hop | Log group (click for the URL) | What you will find |
|---|---|---|
| Webhook Lambda (the front door) | [`SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo) | `webhook->received` (shape of Sentry's payload), `webhook->sns` (execution id, SNS message id) |
| EventBridge Pipe | [`SelfHealingPipeline-PipeLogs8633E6FA-TZkhQ2nzKvyr`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-PipeLogs8633E6FA-TZkhQ2nzKvyr) | `ExecutionStarted` (the raw SQS record), `TargetStageEntered`, `TargetStageSucceeded`, `ExecutionSucceeded` |
| Step Functions (every state's input and output) | [`SelfHealingPipeline-StateMachineLogs3CB16D3C-AuS7KaClkLQJ`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-StateMachineLogs3CB16D3C-AuS7KaClkLQJ) | one event per state transition, with the data. The execution page in the console shows the same as a picture |
| INGEST Lambda | [`SelfHealingPipeline-IngestLogs7327CBDC-uNlWWsY2cDq7`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-IngestLogs7327CBDC-uNlWWsY2cDq7) | `step: ingest` with `outcome: accepted` / `duplicate` / `rate_limited` / `blocked`, `StageSeconds` |
| ROUTE Lambda | [`SelfHealingPipeline-RouteLogs174AF25A-hN541QyQ5Bpa`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-RouteLogs174AF25A-hN541QyQ5Bpa) | only the `REPORT` line (it logs nothing else); its result is in the state's Output |
| INVESTIGATE, FIX, TEST (Fargate tasks) | [`SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS) | streams `investigate/…`, `fix/…`, `test/…`: the step lines, `[test:unit] pass` with pytest's output, `StageSeconds` |
| OPEN PR Lambda | [`SelfHealingPipeline-OpenPrLogs4AF57F65-UpFmCDzo2b9E`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-OpenPrLogs4AF57F65-UpFmCDzo2b9E) | `step: pr` with the PR URL and labels, `EndToEndSeconds` |
| NOTIFY / ESCALATE Lambda | [`SelfHealingPipeline-NotifyLogsC0ABC89F-qVKu4VXhoO6g`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-NotifyLogsC0ABC89F-qVKu4VXhoO6g) | `notify->sns` (message id, subject, full text), `notify->slack` (`status: 200`), `step: escalate`, failure notices |
| GitHub webhook Lambda (the learning loop) | [`SelfHealingPipeline-GitHubWebhookLogs75FD6975-dwpLJNOiM5vz`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-GitHubWebhookLogs75FD6975-dwpLJNOiM5vz) | `github->ledger` with the verdict (from the next deploy; earlier runs show only START and REPORT) |
| The application's own log (what INGEST reads) | [`/aws/ecs/demo-app`](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Faws$252Fecs$252Fdemo-app) | the lines INGEST attaches: INFO, WARN, ERROR |

### Everything else

| What | Link |
|---|---|
| API Gateway (the webhook URL Sentry calls) | https://us-east-1.console.aws.amazon.com/apigateway/main/apis?region=us-east-1 |
| SNS topics (trigger topic, notification topic) | https://us-east-1.console.aws.amazon.com/sns/v3/home?region=us-east-1#/topics |
| SQS queues (`TriggerQueue…` and its dead-letter queue) | https://us-east-1.console.aws.amazon.com/sqs/v3/home?region=us-east-1#/queues |
| EventBridge pipe | https://us-east-1.console.aws.amazon.com/events/home?region=us-east-1#/pipes |
| Step Functions state machines (open a run for the graph) | https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/statemachines |
| ECS cluster (Fargate tasks: filter **Stopped**) | https://us-east-1.console.aws.amazon.com/ecs/v2/clusters?region=us-east-1 |
| S3 buckets (audit trail, run state) | https://us-east-1.console.aws.amazon.com/s3/buckets?region=us-east-1 |
| DynamoDB tables (limiter, PR cap, ledger, history) | https://us-east-1.console.aws.amazon.com/dynamodbv2/home?region=us-east-1#tables |
| Secrets Manager (webhook, github-webhook, slack-webhook secrets) | https://us-east-1.console.aws.amazon.com/secretsmanager/listsecrets?region=us-east-1 |
| Bedrock metrics (`AWS/Bedrock`, `Invocations`) | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#metricsV2 |
| CloudWatch, all log groups | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups |
| Sentry: issues, alert rule, integration Request Log | https://<org>.sentry.io/ (Alerts; Settings, Developer Settings, Custom Integrations) |
| GitHub: pull requests, webhook deliveries | https://github.com/dharmendradevops11/healer-demo-app/pulls ; repo Settings, Webhooks, Recent Deliveries |

[viewing-logs.md](viewing-logs.md) explains how to read each console page and what a healthy one looks like.

---

## Test each flow yourself

`scripts/test_flows.py` drives every flow from your terminal. It writes test data, so use it on the sandbox only. Set
`AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-east-1`; for alerts also `export SENTRY_DSN=<the project's DSN>` (Sentry: Settings, Client Keys; it
is a public key, not a secret). Run `python scripts/test_flows.py --help` for the list.

| # | Flow | Command | You should see | Where to look |
|---|---|---|---|---|
| 1 | **A fix is proposed and tested** (the main path) | `reset-limits`, `seed-logs`, `alert happy`, `wait` | path ends `... Test -> OpenPr -> Notify -> PullRequestOpened`; composite 91 (with logs); a ready PR; a Slack message | the execution graph; the PR; Slack; log groups above |
| 2 | **Escalate: below 60, no fix** | `reset-limits`, `alert escalate`, `wait` | path `... Route -> Gate -> Escalate -> Escalated`; composite under 60; `investigation_only`; a PR that changes only `HEALER_REPORT.md`; a Slack message | same, plus the PR's *Files changed* |
| 3 | **A forged webhook is rejected** | `forged` | `HTTP 401 {"error": "invalid signature"}`; **no** new run | the webhook Lambda log (no `webhook->sns` line) |
| 4 | **A duplicate alert runs once** | `duplicate` | path `InputShape -> Ingest -> Accepted -> Dropped`; status `duplicate`; no PR | INGEST log: `outcome: duplicate` |
| 5 | **INGEST reads real CloudWatch lines** | `seed-logs`, then flow 1 within 10 minutes | `log lines attached: 20`; signal strength 1.0 | `pipeline-state/<run>/state.json`, key `log_lines` |
| 6 | **A human merges, the ledger learns** | merge or close a PR on GitHub (the repo webhook must exist) | ledger `pending` becomes `approved` (merge) or `rejected` (close) | DynamoDB ledger table; GitHub webhook Recent Deliveries (200) |
| 7 | **Slack and SNS notification** | any run that reaches Notify or Escalate | `notify->slack status: 200`; the message in the channel | Notify Lambda log; Slack |
| 8 | **The daily PR cap** | run flow 1 four times without `reset-limits` | the fourth ends `cap_reached`, no PR | the state file's `reason` |
| 9 | **Shadow mode** | deploy with `-c healer:phase=shadow`, then flow 1 | decision recorded under `shadow/` in the audit bucket; **no** branch, **no** PR | audit bucket; GitHub shows nothing new |
| 10 | **A stage crashes and a human is told** | (not reproducible on demand) | a `[WARNING] ... pipeline error in <stage>` message with the error type and **no** ARNs or account number | Slack; the stage's log has the full error |

Flows 8 and 9 are recorded in [aws-test-log.md](aws-test-log.md); the rest are recorded below with their logs.

Read a run's evidence in one command:

```bash
python scripts/trace.py exec-XXXXXXXX          # every hop as text
python scripts/export_run.py exec-XXXXXXXX > run.md   # every log, input and output saved as a file
python scripts/test_flows.py status            # the newest run in 6 lines
```

**Flow 1 depends on the bug being in the repository's `main`.** On 2026-10-09 PR #19 was merged, which put the fix on `main`. Running
flow 1 afterwards makes the model see that `src/auth.py` already handles a missing profile; it declines to write a patch and the run
escalates with a report-only PR (run `exec-522182e6`, PR #21: path `... Gate -> Fix -> RouteAfterFix -> FixOutcome -> FixEnded`,
composite 85). To repeat the happy path, reset the demo repository's `main` to its first commit.

---

## Real Sentry as the source (run `exec-18c81a71`, 2026-10-09 15:13 CDT)

Steps 1 to 5 above were recorded with a script that imitated a Sentry webhook. This section records the same entry point with **real
Sentry** in front of it. Setup: [sentry-setup.md](sentry-setup.md). Full logs of the run: [runs/exec-18c81a71.md](runs/exec-18c81a71.md).

### What happened, in order

| # | Who | What |
|---|---|---|
| 1 | a test script (standing in for an application) | sent one error event to the Sentry project `python` using the project's DSN. Normally the application's Sentry SDK does this |
| 2 | **Sentry** | recorded it as a new issue, **PYTHON-3**: https://<org>.sentry.io/issues/7784023933/ (first seen 15:13:31) |
| 3 | **Sentry** | the alert rule "Notify via self-healing-pipeline" (trigger: a new issue is created) fired |
| 4 | **Sentry** | called our webhook, signed with the integration's Client Secret. 26 seconds after step 1 |
| 5 | AWS | API Gateway, webhook Lambda, SNS, SQS, Pipe, Step Functions: one execution, `exec-18c81a71` |
| 6 | AWS | the run ended in **PR #15**: https://github.com/dharmendradevops11/healer-demo-app/pull/15 |

Only step 1 is simulated. Steps 2 to 4 are Sentry's and steps 5 and 6 are the pipeline's.

### How we know Sentry made the call and not the test script

- The request carried a signature made with the integration's Client Secret. That secret was stored in AWS Secrets Manager without
  ever being read back, so the test script could not have produced it. A request signed with anything else gets `401`.
- The body had the shape Sentry's alert-rule webhook uses: `installation`, `data.event` (with `issue_id`, `web_url`, `tags`,
  `exception`), `triggered_rule`, `actor`.
- It arrived 26 seconds after the error was sent, which is Sentry's processing time.

### The webhook Lambda's log for this request

Log group `SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo`:

```
15:13:54  START RequestId: c230efce-8d03-421e-8870-144f8dd735ea
15:13:57  {"hop": "webhook->received", "action": "triggered", "shape": {"action": "str", "installation": {"uuid": "str"},
            "data": {"event": {"event_id": "str", "project": "int", "platform": "str", "message": "str", "datetime": "str",
            "tags": "list", "culprit": "str", "exception": "dict", "level": "str", "title": "str", "url": "str",
            "web_url": "str", "issue_url": "str", "issue_id": "str", ...}, "triggered_rule": "str"},
            "actor": {"type": "str", "id": "str", "name": "str"}}}
15:13:57  {"hop": "webhook->sns", "execution_id": "exec-18c81a71", "sns_message_id": "d64d47fe-c2e5-5f35-aa7b-24bd8fa05b38",
            "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingPipeline-TriggerTopic92976BC4-IhEQqbgkRKaA",
            "service": "demo-app", "title": "AttributeError: 'NoneType' object has no attribute 'name' (test 151331)"}
15:13:57  REPORT RequestId: c230efce-8d03-421e-8870-144f8dd735ea
```

The first line logs only the **shape** of what Sentry sent (keys and types, never values), so incident text is not written to the log.

### What the pipeline derived from Sentry's payload (saved run state)

| Field | Value | Where it came from |
|---|---|---|
| `affectedService` | `demo-app` | the event's `service` tag (then `server_name`, then the project) |
| `sentryIssueId` | `7784023933` | `data.event.issue_id` |
| `sentryIssueUrl` | `https://sentry.io/organizations/<org>/issues/7784023933/events/0108acfa…/` | `data.event.web_url` |
| `triggeredAt` | `2026-10-09T20:13:31Z` | the event's own `datetime`, so the end-to-end time is real |
| Result | `pr_opened`, composite 82, `fix_pr_standard_review` | the normal pipeline |

### Problems found with real Sentry, and fixed

| Found | Fix |
|---|---|
| One error produced **two webhooks** and two runs: the integration's own "issue created" subscription plus the alert rule's action | the integration subscribes to **no events**; only the alert rule's action calls the webhook (it also carries the full stack trace) |
| The alert rule carried extra triggers (issue resolved, reappeared, regression), so resolving an issue would start an investigation | the rule fires on **new issues only** |
| The alert-rule payload gave the service as a number (the project id) | the service comes from the event's `service` tag, then `server_name` |
| The same error could be delivered twice (retries) | INGEST records the Sentry issue id for 24 hours; a repeat ends as `duplicate` with no second PR |
| An issue webhook also fires on resolve, assign and ignore | only `action: created` is a failure |

### Where to look

| What | Where |
|---|---|
| The issue Sentry created | https://<org>.sentry.io/issues/7784023933/ |
| Sentry's own record of each webhook it sent, with our response code | Sentry, Settings, Developer Settings, Custom Integrations, `self-healing-pipeline`, **Request Log** (not fetched by the API here; check it in the website) |
| The alert rule | Sentry, Alerts, "Notify via self-healing-pipeline" |
| Our webhook log | the log group above, newest stream |
| The run | Step Functions, the execution started 15:13:57 (`e02c9aa9-f3e6-50a7-a6a6-f9eabea591c0`) |

---

## Step 1: the alert arrives and is published to SNS

**Who sends it.** A real Sentry project would. In this walkthrough a script sends a request built to look exactly like a Sentry
webhook (same body, same HMAC signature header, same timestamp header), because no Sentry project is connected yet. The webhook
cannot tell the difference: it only checks the signature.

### The request

```
POST https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/webhook
Content-Type: application/json
sentry-hook-signature: 1fa7ce2a2971da2c...f34d2ac2      (HMAC-SHA256 of the body; the full value is sent)
sentry-hook-timestamp: 1791570209
```

```json
{
  "action": "created",
  "data": {
    "issue": {
      "title": "AttributeError: 'NoneType' object has no attribute 'name'",
      "culprit": "src.auth in get_display_name",
      "level": "error",
      "project": { "slug": "demo-app" },
      "permalink": "https://sentry.io/organizations/o/issues/4242/",
      "firstSeen": "2026-10-09T16:20:00Z",
      "lastSeen": "2026-10-09T16:20:00Z"
    },
    "event": {
      "exception": {
        "values": [
          {
            "stacktrace": {
              "frames": [
                { "filename": "src/auth.py", "lineno": 28, "function": "greet" },
                { "filename": "src/auth.py", "lineno": 24, "function": "get_display_name" }
              ]
            }
          }
        ]
      }
    }
  }
}
```

### The response

```
HTTP 202
{"executionId": "exec-73ff3286", "snsMessageId": "e5523a0d-3ab3-5c15-b075-594e09d23e50"}
```

202 means the signature and the timestamp (no older than 300 seconds) both passed, the payload was understood, and it was
published to SNS. A wrong signature gets `401 {"error": "invalid signature"}`.

### What the webhook Lambda logged

Log group `SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo`:

```
START RequestId: 712c5ce5-a70e-4ff9-9305-787e2b186c67 Version: $LATEST
{"hop": "webhook->sns", "execution_id": "exec-73ff3286",
 "sns_message_id": "e5523a0d-3ab3-5c15-b075-594e09d23e50",
 "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingPipeline-TriggerTopic92976BC4-IhEQqbgkRKaA",
 "service": "demo-app", "title": "AttributeError: 'NoneType' object has no attribute 'name'"}
END RequestId: 712c5ce5-a70e-4ff9-9305-787e2b186c67
REPORT RequestId: 712c5ce5-a70e-4ff9-9305-787e2b186c67  Duration: 311.23 ms  Billed Duration: 312 ms  Memory Size: 256 MB  Max Memory Used: 92 MB
```

(Console times are UTC. This request was handled at 18:23:29 UTC.)

### What the Lambda published to SNS

The body of the SNS message (not stored by SNS; it is built in `healer/handlers.py` and reaches the queue unchanged, because
the subscription uses raw delivery):

```json
{
  "executionId": "exec-73ff3286",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: ...\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "triggeredAt": "2026-10-09T16:20:00Z"
  }
}
```

### Where to look in the console

| What | Where |
|---|---|
| The log above | CloudWatch, log group `SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo`, newest stream |
| The function | Lambda, `SelfHealingPipeline-WebhookReceiver…`, Monitor tab |
| The topic | SNS, topic `SelfHealingPipeline-TriggerTopic92976BC4-IhEQqbgkRKaA`, Subscriptions tab (the queue is subscribed) |

### Checks that passed at this step

- The request was authenticated: an invalid signature is rejected before anything is published.
- Nothing downstream had run yet: the pipe was paused, so no Step Functions execution existed for `exec-73ff3286`.

---

## Step 2: SNS delivers to SQS, and the message waits in the queue

**What happens.** The SNS topic has one subscription: the SQS queue, with **raw message delivery** on. SNS copies the published
message into the queue as it is, with no SNS envelope around it. The pipe (paused here) is what reads it out next.

### The subscription

```json
{ "endpoint": "arn:aws:sqs:us-east-1:<account>:SelfHealingPipeline-TriggerQueue434C4AA5-uUkPt3JwJjya", "protocol": "sqs" }
{ "RawMessageDelivery": "true", "Protocol": "sqs", "ConfirmationWasAuthenticated": "true" }
```

### The queue

```json
{
  "retention": "345600",           // 4 days
  "visibilityTimeout": "300",      // a reader has 5 minutes before the message becomes visible again
  "redrive": { "deadLetterTargetArn": "...SelfHealingPipeline-TriggerDeadLetters88A2981F-...", "maxReceiveCount": 3 }
}
```

After 3 failed deliveries a message moves to the dead-letter queue (it holds 0 messages so far).

### Counts, checked before showing the message

```
ApproximateNumberOfMessages           : 1     <- waiting
ApproximateNumberOfMessagesNotVisible : 0     <- not being processed
newest Step Functions execution       : 13:23:29, i.e. the earlier run; nothing new has started
```

### The message, read with a peek (visibility timeout 0, so it stays in the queue)

```
MessageId               : 9f8f7c80-32d0-4b01-ab81-ca39fd0216f0
ApproximateReceiveCount : 1
SentTimestamp (epoch ms): 1791570548642
```

Body, exactly as stored:

```json
{
  "executionId": "exec-7b31d8bd",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T16:20:00Z",
    "sentryIssueUrl": "https://sentry.io/organizations/o/issues/4242/"
  }
}
```

This is the incident the webhook built from Sentry's payload: the title, a stack trace rendered as a traceback, the service name
(the Sentry project slug), and a log group for INGEST to read.

### Where to look in the console

| What | Where |
|---|---|
| The message | SQS, queue `SelfHealingPipeline-TriggerQueue…`, **Send and receive messages**, **Poll for messages**. Polling shows it without consuming it |
| The subscription | SNS, the topic, Subscriptions tab, "Raw message delivery: Enabled" |
| The dead-letter queue | SQS, queue `SelfHealingPipeline-TriggerDeadLetters…` (empty) |

---

## Step 3: the EventBridge Pipe reads the queue and starts Step Functions

**What happens.** The pipe polls the queue (batch size 1), wraps the message the way an SQS source does, and starts a Step Functions
execution with it. It does not wait for the workflow to finish (`FIRE_AND_FORGET`). The pipe was started again here (it takes
about 20 seconds to go from `STOPPED` to `RUNNING`).

### Before and after

```
before starting the pipe : 1 message waiting, 0 in flight, pipe STOPPED
pipe started             : STARTING -> RUNNING
13:34:33  a Step Functions execution starts: a42d7b76-25be-5286-9c55-18351047b6a6
after                    : 0 waiting, 0 in flight (the message was taken and deleted from the queue)
```

### What the pipe logged (log group `SelfHealingPipeline-PipeLogs8633E6FA-TZkhQ2nzKvyr`)

Four events for this message, in this order, within 100 ms:

```
ExecutionStarted      the pipe picked up the message (SQS message id 9f8f7c80-32d0-4b01-ab81-ca39fd0216f0,
                      the same id as in Step 2). The log holds the raw SQS record: messageId, receiptHandle,
                      and body = the incident JSON from Step 2
TargetStageEntered    calling the target (Step Functions StartExecution)
TargetStageSucceeded  Step Functions accepted it
ExecutionSucceeded    the pipe is done with this message; SQS deletes it
```

### What Step Functions received as its input

```json
[ { "executionId": "exec-7b31d8bd",
    "incident": { "source": "sentry", "severity": "high", "type": "crash",
                  "title": "AttributeError: 'NoneType' object has no attribute 'name'",
                  "stackTrace": "AttributeError: ...\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
                  "affectedService": "demo-app", "cloudwatchLogGroup": "/aws/ecs/demo-app",
                  "triggeredAt": "2026-10-09T16:20:00Z",
                  "sentryIssueUrl": "https://sentry.io/organizations/o/issues/4242/" } } ]
```

Note the outer `[` `]`. EventBridge Pipes hands a Step Functions target an **array** of one item. The state machine's first state
(`InputShape`) notices this and `UnwrapBatch` turns it back into a plain object. This was one of the bugs found only on real AWS.

### Where to look in the console

| What | Where |
|---|---|
| The pipe | EventBridge, Pipes, `TriggerPipe-…`: source SQS, target Step Functions, the log destination |
| The pipe's log | CloudWatch, log group `SelfHealingPipeline-PipeLogs8633E6FA-TZkhQ2nzKvyr` |
| The execution | Step Functions, state machine `StateMachine2E01A3A5-…`, the execution started at 13:34:33 (name `a42d7b76-…`) |

---

## Step 4: Ingest, Investigate, Route (execution `a42d7b76-25be-5286-9c55-18351047b6a6`, run `exec-7b31d8bd`)

Timeline from the Step Functions history (local time, CDT):

```
13:34:33  InputShape, UnwrapBatch   0.0s   the pipe's array becomes an object
13:34:33  Ingest            (Lambda)       4.0s
13:34:37  Accepted                   0.0s   a Choice: did INGEST accept it?
13:34:37  Investigate       (Fargate)     55.2s
13:35:32  Route             (Lambda)       4.2s
13:35:36  Gate                       0.0s   a Choice: may a fix be written?
```

### Ingest: rate limit, guardrail classifier, attach the log lines

Lambda log group `SelfHealingPipeline-IngestLogs7327CBDC-uNlWWsY2cDq7`:

```
{"execution_id": "exec-7b31d8bd", "step": "ingest", "confidence": null, "output": {"outcome": "accepted"}}
{"_aws": {...}, "StageSeconds": 1.766, "execution_id": "exec-7b31d8bd", "Stage": "ingest"}
REPORT  Duration: 3435.80 ms  Billed Duration: 3645 ms  Memory Size: 512 MB  Max Memory Used: 109 MB  Init Duration: 208.53 ms
```

State output adds `"ingest": {"executionId": "exec-7b31d8bd", "status": "running", "reason": ""}`. `running` means the alert passed the hourly
limit (3 per service) and the guardrail classifier. Anything else (`rate_limited`, `blocked`) would have ended the run at `Accepted`.

**An honest observation.** INGEST attaches the last 20 CloudWatch log lines for the service. The saved state shows **0 log
lines**, because the log group `/aws/ecs/demo-app` does not exist in this sandbox (there is no real application behind the alert).
That is why the signal strength is 0.7 and not higher.

### Investigate: the Fargate task

ECS task `708c5d679d7b41a2b8c47df02fa5c2ca`, family `SelfHealingPipelineInvestigateTaskE3CC0D7F`, 1 vCPU / 2 GB, exit code 0.

```
13:34:37  Step Functions starts the task
13:34:57  container started        (about 20 s to provision and pull the image)
13:35:04  the work itself: 6.5 s   (clone the repo, read src/auth.py, ask Claude, score, decide)
13:35:31  task stopped
```

So about 55 s of the step is Fargate startup and shutdown, and 6.5 s is the work. Log group
`SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`, stream `investigate/healer-investigate/708c5d679d7b41a2b8c47df02fa5c2ca`:

```
{"execution_id": "exec-7b31d8bd", "step": "investigate", "confidence": 82,
 "output": {"root_cause": "In src/auth.py line 24, the code attempts to access 'session.user.profile.name' without checking if 'profile' is None. ...",
            "model_certainty": 95, "signal": 0.7, "history": null, "composite": 82, "decision": {...}}}
{"_aws": {...}, "StageSeconds": 6.512, "execution_id": "exec-7b31d8bd", "Stage": "investigate"}
[investigate] execution exec-7b31d8bd: status=running
```

What it decided (from the saved run state in the state bucket):

| | |
|---|---|
| The model said | confidence **95**: null dereference at `src/auth.py` line 24 |
| Files it named | `src/auth.py` |
| Signal strength | 0.7 (stack trace and file read; no log lines, no history) |
| History for this failure category | none yet (the ledger has too few resolved outcomes) |
| **Composite confidence** | **82** (0.30 signal + 0.45 model + 0.25 history, with the missing-history rule) |
| Band | medium (60 to 84) |
| Blast radius | medium (the service is not in the registry, so the default tier applies) |
| Tier / page | warning, business hours only |
| Review flags | `unowned service`, `new failure pattern` |

The model's 95 became 82 once the system weighed how much evidence it had. That gap is Chapter 9's point.

### Route: apply the escalation matrix

Lambda log group `SelfHealingPipeline-RouteLogs174AF25A-hN541QyQ5Bpa`. State output adds
`"route": {"executionId": "exec-7b31d8bd", "status": "running", "fixAction": "fix_pr_standard_review"}`.
The matrix cell (medium confidence x medium blast radius) is `fix_pr_standard_review`, so the Gate sends the run on to **Fix**. A cell
of `investigation_only` would have sent it to Escalate instead (report-only PR, no fix).

### Where to look in the console

| What | Where |
|---|---|
| Every state's input and output | Step Functions, the execution, click a state in the graph, *Input* / *Output* tabs |
| The Fargate task | ECS, cluster, *Tasks*, *Stopped*, `708c5d67…`, the *Logs* tab |
| The run state and audit files | S3, `self-healing-pipeline-state-<account>/pipeline-state/exec-7b31d8bd/state.json` and `self-healing-pipeline-audit-logs-<account>/audit/exec-7b31d8bd/` |

### How to check Step 4 yourself

| Where | Do | Expect |
|---|---|---|
| Step Functions, the execution, *Graph view* | click **Ingest**, then *Output* | `"ingest": {"status": "running"}` |
| same | click **Investigate**, *Details* | about 55 s; *Resource* links to the ECS task |
| same | click **Route**, *Output* | `"route": {"fixAction": "fix_pr_standard_review"}` |
| CloudWatch, `SelfHealingPipeline-AgentLogs…`, stream `investigate/healer-investigate/708c5d67…` | read the three lines | `"composite": 82`, `StageSeconds` about 6.5, `status=running` |
| ECS, cluster, *Tasks*, filter **Stopped**, task `708c5d67…` | read the header | exit code 0, 1 vCPU / 2 GB |
| S3, state bucket, `pipeline-state/exec-7b31d8bd/state.json` | search for `composite` | 82, `history` null, two `review_flags` |

Raw logs for this and every other step: [runs/exec-7b31d8bd.md](runs/exec-7b31d8bd.md).

---

## Step 5: Fix and Test (run `exec-4fb06009`, execution `a47cc9eb-b3ef-5ad8-a92d-aaa88f72b005`)

**Why a different run.** Steps 1 to 4 were captured on `exec-7b31d8bd`. That run's unit test failed because the model was never shown
the test and picked `"Guest"` where the test required `"there"`. The pipeline was then changed to show the model the tests that
exercise the file it is about to change (read-only), and Step 5 is recorded on a run made after that change. Full logs for both
runs are in [runs/](runs/). Steps 1 to 4 behave identically in the two runs.

```
14:04:22  Gate             may a fix be written? yes
14:04:22  Fix        (Fargate)   51.7 s
14:05:14  RouteAfterFix           0.2 s   did Fix produce a branch?
14:05:14  FixOutcome              0.0 s   a Choice: branch made, so go on to Test
14:05:14  Test       (Fargate)   50.0 s
14:06:04  OpenPr     (Lambda)     6.5 s   (Step 6)
```

### Fix: ECS task `4fa9c167abf8492499ce81b90d3957c4`

1 vCPU / 2 GB, exit code 0, up 14:04:42, stopped 14:05:13. Stream `fix/healer-fix/4fa9c167abf8492499ce81b90d3957c4` in log group
`SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`:

```
14:04:48  {"execution_id": "exec-4fb06009", "step": "fix", "output": {"type": "code-fix", "files": ["src/auth.py"]}}
14:04:49  {"execution_id": "exec-4fb06009", "step": "remediate", "output": {"applied": true, "branch": "healer/2026-10-09-fix-src-auth-py-b06009"}}
14:04:49  StageSeconds 6.523
14:04:49  [fix] execution exec-4fb06009: status=running
```

What the stage did, in order (audit file `audit/exec-4fb06009/step_003_fix.json`):

1. **Read the file the diagnosis named** (`src/auth.py`) and **found the tests that mention it**:
   `"input": {"files": ["src/auth.py"], "tests_shown": ["tests/test_auth.py"]}`. The test file is given to the model as **read-only**
   reference; it must not be changed.
2. **Asked Claude for a unified diff.** The model's answer: `"type": "code-fix"`, touching only `src/auth.py`.
3. **Checked the diff against the allowlist before applying it** (`step_004_remediate.json`): every file the diff touches must be
   declared and must be under `src/ lib/ app/ packages/`. A diff touching a test, a workflow, a migration or a script would have been
   refused here.
4. **Applied it on a new `healer/` branch** (`"applied": true`), committed and pushed. Never to `main`.

The commits on the branch (GitHub):

```
7c2d0ad  chore(healer): add reviewer packet      19:06:07 UTC   (added by OpenPr, Step 6)
ad868dc  fix(healer): fix src/auth.py            19:04:48 UTC   author "AI Self-Healer"
1d693ba  Demo app with one deliberate bug        (main)
```

The change itself:

```diff
 def get_display_name(session: Session) -> str:
-    # First OAuth login: new users have no profile yet. This line crashes for them.
-    return session.user.profile.name.strip()  # type: ignore[union-attr]
+    # First OAuth login: new users have no profile yet.
+    if session.user.profile is None:
+        return "there"
+    return session.user.profile.name.strip()
```

The value `"there"` is what `tests/test_auth.py` requires
(`assert get_display_name(Session(User("2"))) == "there"`). The model could only know that because it was shown the test.

### Test: ECS task `42449f99faaf4ababaf528259818c6f7`

2 vCPU / 4 GB (twice the size: it runs the repository's own checks), exit code 0, up 14:05:36, stopped 14:06:03. Stream
`test/healer-test/42449f99faaf4ababaf528259818c6f7`:

```
14:05:38  {"execution_id": "exec-4fb06009", "step": "test", "output": {"checks": ["type-check: pass", "unit: pass", "lint: pass"], "passed": true}}
14:05:38  StageSeconds 1.937
14:05:39  [test] execution exec-4fb06009: status=running
```

What the stage did (`audit/exec-4fb06009/step_005_test.json`, input `{"branch": "healer/2026-10-09-fix-src-auth-py-b06009"}`):

1. Cloned the repository and **checked out the branch the Fix task pushed** (a separate container, so it proves the pushed code and not
   a leftover working copy).
2. Installed nothing and ran three checks against it: **type-check** (mypy), **unit tests** (pytest), **lint** (ruff).
3. Recorded each as pass or fail. `passed: true` means all three passed, which is what keeps the PR from being a draft.

The checks ran in about 2 seconds; the other 48 seconds of the state are Fargate starting and stopping the container.

### The passing tests, in the Test task's own log (run `exec-151acb9e`)

The Test stage originally logged only the word `pass`. It now writes each check's own output (last 1500 characters, scrubbed of
secrets) to its log and to the audit file. This is run `exec-151acb9e`, the same alert and the same fix path as `exec-4fb06009`;
Test task `833f765a0312491eaa4f556e72cdd12a`, exit code 0, stream `test/healer-test/833f765a0312491eaa4f556e72cdd12a`:

```
14:25:12.601  [test:type_check] pass
14:25:12.601  Success: no issues found in 2 source files
14:25:12.601  [test:unit] pass
14:25:12.601  ...                                                                      [100%]
14:25:12.601  3 passed in 0.01s
14:25:12.601  [test:lint] pass
14:25:12.601  All checks passed!
14:25:12.668  {"execution_id": "exec-151acb9e", "step": "test", "output": {"checks": ["type-check: pass", "unit: pass", "lint: pass"], "passed": true, "output": {...}}}
14:25:12.668  StageSeconds 1.525
14:25:12.708  [test] execution exec-151acb9e: status=running
```

CloudWatch: https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS/log-events/test$252Fhealer-test$252F833f765a0312491eaa4f556e72cdd12a

The three dots are the three unit tests (`test_returns_trimmed_profile_name`, `test_greets_returning_user`,
`test_first_time_user_without_profile_gets_a_default_name`). The same checks run by hand on the pushed branch, with test names:

```
tests/test_auth.py::test_returns_trimmed_profile_name PASSED
tests/test_auth.py::test_greets_returning_user PASSED
tests/test_auth.py::test_first_time_user_without_profile_gets_a_default_name PASSED
3 passed in 0.01s
```

For contrast, the same third test on `main` (before the fix):

```
>       return session.user.profile.name.strip()  # type: ignore[union-attr]
E       AttributeError: 'NoneType' object has no attribute 'name'
FAILED tests/test_auth.py::test_first_time_user_without_profile_gets_a_default_name
1 failed, 2 passed
```

### How to check Step 5 yourself

| Where | Do | Expect |
|---|---|---|
| Step Functions, the execution, *Graph view* | click **Fix**, then **Test** | green; about 50 s each; *Resource* links to the ECS task |
| ECS, cluster, *Tasks*, filter **Stopped** | open `4fa9c167…` and `42449f99…` | exit code 0; Test has 2 vCPU / 4 GB |
| CloudWatch, `SelfHealingPipeline-AgentLogs…` | open the two streams above | the lines shown above |
| S3, audit bucket, `audit/exec-4fb06009/` | open `step_003_fix.json`, `step_004_remediate.json`, `step_005_test.json` | `tests_shown: ["tests/test_auth.py"]`, `applied: true`, `passed: true` |
| GitHub, repo, *Branches* | open `healer/2026-10-09-fix-src-auth-py-b06009` | the two commits above; `src/auth.py` returns `"there"` |

An observation worth knowing: the second commit ("add reviewer packet") shows under **your** GitHub account, while the fix commit
shows "AI Self-Healer". The packet is added through the GitHub API with your token, so GitHub attributes it to the token's owner.
Chapter 17 recommends a machine user for the token, which would make both commits show the bot.

---

## Step 6: OpenPr and Notify (run `exec-62698225`, started by a real Sentry alert)

Recorded on a run that came in through real Sentry, after the Fix prompt included the tests and the Test stage logged its output. Full logs:
[runs/exec-62698225.md](runs/exec-62698225.md).

```
15:32:46  Test                (Fargate)   47.8 s   all three checks pass
15:33:34  OpenPr              (Lambda)     7.0 s   opens the pull request
15:33:41  Notify              (Lambda)     4.6 s   tells the owner, through SNS
15:33:45  PullRequestOpened                         the run's last state
```

### OpenPr: the pull request

Lambda `SelfHealingPipeline-OpenPr92F50AD2-i5GWz4JCrZVL`, log group `SelfHealingPipeline-OpenPrLogs4AF57F65-UpFmCDzo2b9E`:

```
15:33:34  START RequestId: 493cbdfe-3cd4-4e5d-aade-8be1267fba3a
15:33:40  {"execution_id": "exec-62698225", "step": "pr", "confidence": 82,
           "output": {"pr": "https://github.com/dharmendradevops11/healer-demo-app/pull/16",
                      "labels": ["healer", "healer: standard-review", "healer: blast-radius-medium", "healer: human-review"]}}
15:33:41  StageSeconds 4.742
15:33:41  EndToEndSeconds 221.0     <- alert time to PR: 3 min 41 s (real, because Sentry supplies the error's own time)
15:33:41  REPORT  Duration 6570.82 ms  Billed 6789 ms  Memory 512 MB
```

What OpenPr does, in order:
1. Reads the saved run state (diagnosis, decision, the fix, the test results).
2. Builds the **reviewer packet** (`HEALER_REPORT.md`): incident, diagnosis and confidence, proposed fix, test results, blast radius, rollback plan.
3. Commits that file to the `healer/` branch the Fix task pushed (through the GitHub API, so the Lambda needs no git binary).
4. Opens the pull request against `main` with the packet in the description and the triage labels.
5. Opens it as a **draft** only if a check failed. Here nothing failed, so it is a ready PR.
6. Writes the outcome to the trust ledger (`pending`) and the remediation history.

**The PR (checked on GitHub):** https://github.com/dharmendradevops11/healer-demo-app/pull/16

| | |
|---|---|
| State | open, **not a draft**, `healer/2026-10-09-fix-src-auth-py-698225` into `main` |
| Commits | `fix(healer): fix src/auth.py`, `chore(healer): add reviewer packet` |
| Files | `src/auth.py` (+4 −2), `HEALER_REPORT.md` (+22). Nothing else |
| Labels | `healer`, `healer: standard-review`, `healer: blast-radius-medium`, `healer: human-review` |
| Description | routing decision (82/100, medium, `fix_pr_standard_review`), two "Human review required" notes (unowned service, new failure pattern), the reviewer packet, test results: **type-check pass, unit pass, lint pass**, "All checks passed.", and the footer `Execution: exec-62698225` |

The footer line is how the learning loop later finds the ledger row when someone merges or closes the PR.

### Notify: the message

Lambda `SelfHealingPipeline-Notify29C25B1B-waClKV3bDfn2`, log group `SelfHealingPipeline-NotifyLogsC0ABC89F-qVKu4VXhoO6g`:

```
15:33:45  {"hop": "notify->sns", "sns_message_id": "1bfcceb8-c8e6-5d43-b635-adfb990fe29c",
           "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingState-NotificationTopicEB7A0DF1-ZxzTplsPy47u",
           "subject": "[WARNING] [Healer] demo-app: Fix ready (82/100)",
           "attributes": {"escalationTier": "warning", "page": "business_hours_only", "channel": "slack+ticket", "fixAction": "fix_pr_standard_review"},
           "message": ...}
```

The message text:

```
Self-Healer: Fix ready
Escalation: WARNING -> unassigned via slack+ticket (page: business_hours_only)
Routing: medium confidence x medium blast radius -> fix_pr_standard_review
Service: demo-app
Issue: AttributeError: 'NoneType' object has no attribute 'name' (test 153000)
Root cause: In src/auth.py line 24, the code attempts to access 'session.user.profile.name' without checking if 'profile' is None. ...
Confidence: 82/100
Human review required: unowned service: it has no named team or on-call rotation in the registry
Human review required: new failure pattern: the ledger has too little history for this category
PR: https://github.com/dharmendradevops11/healer-demo-app/pull/16
```

The four message attributes (tier, page, channel, fix action) let subscribers filter. Only a `critical` tier pages anyone, always.

### Who received it: nobody yet, and why

The notification topic has **one subscription, an email address, and its status is `PendingConfirmation`**. AWS sends a
"Subscription Confirmation" email when the stack is deployed with `healer:notification_email`, and sends nothing to that address
until its **Confirm subscription** link is clicked. So the message above was published to the topic (the log line proves it) and
delivered to no one. Slack is not connected either (`healer:slack_secret_arn` is unset), so there is no other channel.

To receive notifications: click the link in the AWS email, or connect Slack with a webhook URL stored as a secret.

### How to check Step 6 yourself

| Where | Do | Expect |
|---|---|---|
| Step Functions, the execution, **OpenPr** then **Notify** | click each, *Details* | about 7 s and 5 s, both green; *Logs* link on each row |
| CloudWatch, `…OpenPrLogs…` and `…NotifyLogs…`, newest stream | read the lines above | the PR URL; the `notify->sns` line with the message |
| GitHub, the PR link above | read the *Conversation* and *Files changed* tabs | the packet, the labels, 2 files |
| SNS console, topic `SelfHealingState-NotificationTopic…`, *Subscriptions* | read the *Status* column | `Pending confirmation` until the email link is clicked |
| Your email | search for "AWS Notification - Subscription Confirmation" | the confirm link (it expires after 3 days) |

---

*What comes after Step 6 in the architecture: the human reads the PR and merges or closes it; GitHub's webhook then updates the trust
ledger (the learning loop); and the escalate branch handles runs that may not write a fix. These are recorded as they are shown.*
## The CloudWatch Logs hop (run `exec-810f0a1b`)

Figure 2.1 has INGEST "pull last 20 lines" from **CloudWatch Logs**. In Steps 4 to 6 it read **0 lines**, because the log group
`/aws/ecs/demo-app` did not exist in the account (there is no real application behind the alerts). This run fixes that, and it also
found a bug. Full logs: [runs/exec-810f0a1b.md](runs/exec-810f0a1b.md).

### What was set up

A log group `/aws/ecs/demo-app` (the name INGEST derives from the service) with 29 lines written the way an application would
write them: 26 `INFO request N ok` lines, then `WARN profile lookup returned None for user=2041`, then two `ERROR` lines. Then a
real error was sent through Sentry for the same service.

### The bug this found: the book's printed filter matches nothing

The book's Chapter 4 listing filters with `[level=ERROR || level=FATAL]`. Tested on real CloudWatch against those 29 lines, it
returned **0 lines**, although two of them contain `ERROR`. In CloudWatch a space-delimited pattern with one field only matches
events that consist of exactly one word, so it can never match a real log line (`2026-10-09T20:46:38Z ERROR ...` has many words).
The same group read with no pattern returned all 29. Chapter 2's prose also says INGEST attaches "the last 20 log lines", all
levels, not only errors. So the pipeline now uses `last_log_lines` (the newest 20 lines of every level in a 10-minute window),
and the printed listing stays in the repository unchanged. This is recorded as an errata candidate for the book.

### What INGEST attached (from the saved run state, `pipeline-state/exec-810f0a1b/state.json`)

20 lines, oldest first, ending at the failure:

```
2026-10-09T20:45:31Z INFO request 69 ok user=1009        <- the first of the 20
...
2026-10-09T20:46:31Z INFO request 84 ok user=1024
2026-10-09T20:46:35Z INFO request 85 ok user=1025
2026-10-09T20:46:36Z WARN profile lookup returned None for user=2041
2026-10-09T20:46:38Z ERROR AttributeError in get_display_name: 'NoneType' object has no attribute 'name' user=2041
2026-10-09T20:46:39Z ERROR request failed for first-time user user=2041 status=500
```

The Ingest Lambda's own line is `{"step": "ingest", "output": {"outcome": "accepted"}}`; its audit file `step_001_ingest.json` records
`"log_lines": 20` in its input.

### What the logs changed downstream

| | Run without logs (`exec-62698225`) | Run with logs (`exec-810f0a1b`) |
|---|---|---|
| Log lines attached | 0 | **20** |
| Signal strength | 0.7 | **1.0** |
| Model certainty | 95 | 95 |
| **Composite confidence** | 82 (medium) | **91 (high)** |
| Routing | `fix_pr_standard_review` | **`auto_fix_pr`** |
| PR | #16 | #17 |

The model's evidence summary now cites the log: "The CloudWatch logs show 'profile lookup returned None for user=2041' immediately
before the AttributeError." More evidence raised the score without the model being any more sure of itself: the composite blends in
how much evidence the system had (Chapter 9), which is why the book does not take the model's self-score at face value.

### Where to look

| What | Where |
|---|---|
| The application's log | CloudWatch, log group `/aws/ecs/demo-app` (retention set to 1 day) |
| What INGEST attached | S3, state bucket, `pipeline-state/exec-810f0a1b/state.json`, key `log_lines` |
| The run | Step Functions, the execution for `exec-810f0a1b` |

---

## The Escalate branch (run `exec-4898e06c`): a run that may not write a fix

Figure 2.1 splits after INVESTIGATE: "Score at or above 60" goes to FIX, "Score below 60" goes to **Escalate / Slack**. Everything so
far took the first branch. This run takes the second. Full logs: [runs/exec-4898e06c.md](runs/exec-4898e06c.md).

### How it was triggered

A real error sent through Sentry with **no stack trace** and from a service nothing is known about (`mystery-service`, no log group):
`Error: something went wrong`. There is nothing for the system to point at.

### What happened

```
15:54:36  InputShape, UnwrapBatch
15:54:36  Ingest        (Lambda)    4.0 s   0 log lines: no log group for this service
15:54:40  Accepted
15:54:40  Investigate   (Fargate)  85.1 s   clone, ask Claude, score
15:56:05  Route         (Lambda)    4.2 s   fixAction = investigation_only
15:56:10  Gate                      0.0 s   the Choice: not authorised, so go to Escalate
15:56:10  Escalate      (Lambda)   10.4 s   report-only PR + message
15:56:20  Escalated                         the run's last state
```

**Fix, RouteAfterFix, FixOutcome, Test, OpenPr and Notify never ran.** Step Functions skips them. No code was written, no branch
of fixes was pushed, no tests ran, and Bedrock was not asked for a patch.

### The decision (saved run state)

| | |
|---|---|
| Stack trace | none (the title only); 0 log lines |
| **Model certainty** | **75**: it gave an explanation anyway, blaming "a deliberate bug introduced in commit 1d693ba", which it read in the repository's history |
| Files it named | none |
| Signal strength | **0.3** (no trace, no files, no logs) |
| History | none yet |
| **Composite confidence** | **58**, band **low** |
| Blast radius | medium (service not in the registry) |
| `fix_action` | **`investigation_only`**, tier warning, page: business hours only |
| Status | `escalated`: "the escalation matrix does not authorize a fix" |
| Review flags | unowned service; new failure pattern |

**This is the point of the composite score.** On its own the model said 75, which is above the 60 line and would have sent this run to
FIX. It had nothing to base that on, and made up a plausible cause from a commit message. The system weighed how little evidence it
had (signal 0.3) and brought the score to 58, below the line. A person decides what to do next, not a fix generator.

### What Escalate did (the Notify Lambda, mode `escalate`)

Log group `SelfHealingPipeline-NotifyLogsC0ABC89F-qVKu4VXhoO6g`:

```
15:56:10  START RequestId: ae624b9d-5e56-4921-8b57-89d33b06b68c
15:56:20  {"hop": "notify->sns", "sns_message_id": "b2343b48-8f40-573e-a995-580bd874f0a4",
           "subject": "[WARNING] [Healer] mystery-service: Needs a human, no fix attempted (58/100)",
           "attributes": {"escalationTier": "warning", "page": "business_hours_only", "channel": "slack+ticket", "fixAction": "investigation_only"},
           "message": "Self-Healer: Needs a human, no fix attempted ... Routing: low confidence x medium blast radius -> investigation_only ...
                       PR: https://github.com/dharmendradevops11/healer-demo-app/pull/18 ... (the reviewer packet follows)"}
15:56:20  {"step": "escalate", "confidence": 58, "output": {"notified": "unassigned", "pr": ".../pull/18"}}
15:56:20  EndToEndSeconds 121.5
```

Two things happen, in this order:
1. **A report-only pull request.** The Lambda creates a `healer/` branch through the GitHub API (it has no git binary), commits only
   `HEALER_REPORT.md`, and opens the PR. The book's prose says this (Chapters 1, 2, 18: below 60 the agent is "a detective, not a
   developer").
2. **The message**, which carries the PR link and the reviewer packet. This is Figure 2.1's "Escalate / Slack" box.

### The pull request (checked on GitHub): https://github.com/dharmendradevops11/healer-demo-app/pull/18

| | |
|---|---|
| Title | `[HEALER] investigation: Error: something went wrong (escalate test 155419)` |
| Commits | one: `chore(healer): investigation report` |
| Files | **`HEALER_REPORT.md` only (+22).** No source file is touched |
| Labels | `healer`, `healer: investigation-only`, `healer: low-confidence`, `healer: human-review`, `healer: blast-radius-medium` |
| Description | "Investigation only. No source code was changed", the routing decision (58/100, low, `investigation_only`), the reviewer packet with `files_changed: []`, `tests_run: ["not run"]` and `rollback_plan: "No code change to roll back."` |
| Draft | no |

### Escalate reaching Slack (run `exec-633686c4`)

The first escalate run above was made before Slack was connected. The same kind of alert (no stack trace, unknown service) was sent
again once Slack was in place and the failure-message redaction was deployed. Full logs: [runs/exec-633686c4.md](runs/exec-633686c4.md).

```
path   : InputShape -> UnwrapBatch -> Ingest -> Accepted -> Investigate -> Route -> Gate -> Escalate -> Escalated
decision: composite 53 (low), investigation_only, status escalated
PR     : https://github.com/dharmendradevops11/healer-demo-app/pull/20   (HEALER_REPORT.md only)
Notify : {"hop": "notify->sns",   "sns_message_id": "17c83db9-d98e-55e2-8587-5efa844ca8ce",
          "subject": "[WARNING] [Healer] mystery-service: Needs a human, no fix attempted (53/100)"}
         {"hop": "notify->slack", "status": 200, "subject": "[WARNING] [Healer] mystery-service: Needs a human, no fix attempted (53/100)"}
```

In Slack this is the message `[WARNING] [Healer] mystery-service: Needs a human, no fix attempted (53/100)` with the routing line
(`low confidence x medium blast radius -> investigation_only`), the root cause, the human-review notes and the PR link.

**A message that leaked internal ids, and the fix.** The failed run of the Slack setup posted this to the channel: the full Lambda error,
with the AWS account number, the role ARN and the secret's ARN. Failure messages now carry only the error type and message
(`ClientError: An error occurred (AccessDeniedException) ...`), with ARNs shown as `[arn]` and account numbers as `[account]`; the stack
is dropped. The full error stays in the stage's CloudWatch log and the audit file.

### What this branch shows against Figure 2.1

| Figure 2.1 | What runs here |
|---|---|
| Score below 60 goes to Escalate / Slack | Gate sends it to the Escalate state |
| "Slack" | the message goes to **SNS and Slack** (this first escalate run was made before Slack was connected; a second run, below, reached Slack) |
| (the book's prose, not drawn in the figure) a report-only PR | created, as above |

### The audit trail for this run

`step_001_ingest.json`, `step_002_investigate.json`, `step_003_escalate.json`. No fix, remediate, test or pr step exists, because those
stages never ran.

### How to check it yourself

| Where | Do | Expect |
|---|---|---|
| Step Functions, the execution, *Graph view* | look at the path | green: Ingest, Investigate, Route, Gate, **Escalate**, Escalated. **Fix, Test, OpenPr are not green** (never entered) |
| same, click **Route**, *Output* | read it | `"fixAction": "investigation_only"` |
| S3, state bucket, `pipeline-state/exec-4898e06c/state.json` | search `composite`, `fix_action` | 58, `investigation_only` |
| GitHub, the PR above | *Files changed* | `HEALER_REPORT.md` only |

---

## Slack (run `exec-ec2eb471`)

Figure 2.1 sends NOTIFY to a **Slack channel**. Until this run, notifications reached only SNS. Full logs: [runs/exec-ec2eb471.md](runs/exec-ec2eb471.md).

### Setup

1. In Slack: an app with **Incoming Webhooks** on, one webhook added to a channel.
2. The webhook URL is stored as the AWS secret `self-healing-pipeline/slack-webhook`. It is read **only when a message is sent**, and
   only by the Notify Lambda.
3. The stack is deployed with `-c healer:slack_secret_arn=<the secret's ARN>`.

A direct test post to the webhook before storing it returned HTTP 200 `ok`.

### A bug this found: the Slack secret was read by every stage

The first run after connecting Slack **failed in INGEST**:

```
AccessDeniedException ... Healer-Ingest-Role ... is not authorized to perform: secretsmanager:GetSecretValue
on resource: ...secret:self-healing-pipeline/slack-webhook-...
```

The services were built by reading the Slack secret up front, so every Lambda and task that builds them (INGEST, INVESTIGATE, FIX, TEST,
OpenPr) needed permission for a secret only NOTIFY uses. That breaks least privilege and the book's rule that secrets are fetched at the
moment of use (Chapter 11). Fixed: `SlackNotifier` now takes a function and reads the secret when it sends the first message; only the
Notify role can read it. A Slack failure is logged and never stops the pipeline.

### The Notify Lambda's log for the run that worked

Log group `SelfHealingPipeline-NotifyLogsC0ABC89F-qVKu4VXhoO6g`, 16:13:48 (Notify took 4.4 s):

```
{"hop": "notify->sns",   "sns_message_id": "3c3cbd25-0ced-54b2-aa03-de6657a1f7bf", "subject": "[INFO] [Healer] demo-app: Fix ready (91/100)",
 "attributes": {"escalationTier": "informational", "page": "False", "channel": "slack", "fixAction": "auto_fix_pr"}}
{"hop": "notify->slack", "status": 200, "subject": "[INFO] [Healer] demo-app: Fix ready (91/100)"}
```

`status: 200` is Slack's own answer: it accepted the message. The webhook URL is never written to any log.

### What the Slack message contains

The same text as the SNS message: a bold subject line (`[INFO] [Healer] demo-app: Fix ready (91/100)`), the escalation line, the
routing line (`high confidence x medium blast radius -> auto_fix_pr`), service, issue, root cause, confidence, any "Human review
required" notes, and the PR link (here PR #19). The tier decides how loud it is: only a `critical` tier pages anyone.

### How to check it yourself

| Where | Do | Expect |
|---|---|---|
| Your Slack channel | look for two messages | the connection test ("Slack is wired up") and the `[INFO] [Healer] demo-app: Fix ready (91/100)` message with the PR link |
| CloudWatch, `SelfHealingPipeline-NotifyLogs…` | find the `notify->slack` line | `"status": 200` |
| Secrets Manager | secret `self-healing-pipeline/slack-webhook` | exists. Read access is only on the Notify role |

**The webhook URL was pasted into the chat while setting this up, so it should be revoked and replaced**: Slack app, Incoming Webhooks,
remove it, add a new one, then `aws secretsmanager put-secret-value` the new URL.

---

## Human merges the PR, and the pipeline learns (PR #19, run `exec-ec2eb471`)

The last box in your image before production: **Human Merges PR**. Nothing in the pipeline merges anything; a person does. What the
pipeline adds is that it hears about the decision and records it (Chapter 2, Stage 4; Chapter 9, "The Ledger").

### Setup

A **GitHub webhook** on the repository: payload URL `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/github`, content type
JSON, **Pull requests** events only, signed with a secret stored in AWS (`self-healing-pipeline/github-webhook`). It goes to the
`GitHubWebhook` Lambda, which is allowed to touch only the ledger and history tables and read its one secret.

### Before

```
ledger  exec-ec2eb471: human_verdict = pending   confidence 91   category crash:AttributeError
history exec-ec2eb471: human_decision = None     files_changed ['src/auth.py']
```

### The human step (16:29:16 local)

PR #19 (`healer/2026-10-09-fix-src-auth-py-2eb471`): ready, not a draft, 2 commits, mergeable. A person merged it on GitHub at 16:29:18.
The pipeline did nothing to it.

### What happened next

| Time (UTC) | Evidence |
|---|---|
| 21:29:19 | GitHub sent a `ping` to the new webhook: **HTTP 200** (GitHub's own Recent Deliveries list) |
| 21:29:20 | GitHub sent `pull_request`, `action: closed`: **HTTP 200** |
| 21:29:20 | the `GitHubWebhook` Lambda ran (2.6 s cold, 0.6 s warm) in log group `SelfHealingPipeline-GitHubWebhookLogs75FD6975-dwpLJNOiM5vz` |

The Lambda checked the request's signature, saw a `healer/` branch, found `Execution: exec-ec2eb471` in the PR description, saw
`merged: true` with the baseline of 2 commits, and decided **approved**.

### After

```
ledger  exec-ec2eb471: human_verdict = approved  confidence 91   category crash:AttributeError
history exec-ec2eb471: human_decision = merged   files_changed ['src/auth.py']
```

| Reviewer does | Ledger | History |
|---|---|---|
| merges as it was | `approved` | `merged` |
| merges after adding commits | `modified` | `edited_then_merged` |
| closes without merging | `rejected` (with the reason ticked in the PR template) | `rejected` |
| closes an investigation-only PR | unchanged: a report says nothing about whether the diagnosis was right | unchanged |

### What this changes for the next run

The category `crash:AttributeError` now has **one** resolved outcome. The composite score uses the history input only once a category
has at least **five** resolved outcomes, so nothing changes yet. After five, the 25% history weight stops being a neutral prior and
starts reflecting how often reviewers actually accepted fixes for this kind of failure. That is how the pipeline's confidence becomes
calibrated to your team.

### A gap found and fixed afterwards

The `GitHubWebhook` Lambda wrote **no log line** about what it recorded, so the only evidence was the two tables. It now logs
`{"hop": "github->ledger", "execution_id": ..., "verdict": "approved", "reason": null}`. That line appears from the next deploy.

### How to check it yourself

| Where | Do | Expect |
|---|---|---|
| GitHub, repository *Settings, Webhooks*, the webhook, **Recent Deliveries** | open the `pull_request` delivery | **200**, the request and response bodies |
| CloudWatch, `SelfHealingPipeline-GitHubWebhookLogs…` | newest stream | one invocation at 21:29:20 UTC |
| DynamoDB, table `…TrustLedger…`, *Explore items*, `exec-ec2eb471` | read `human_verdict` | `approved` |
| DynamoDB, table `…RemediationHistory…` | read `human_decision` | `merged` |

---

## Other flows: duplicate alert, forged webhook, failed stage

### A forged webhook is rejected

```
$ python scripts/test_flows.py forged
HTTP 401 {"error": "invalid signature"}
```

The request had a signature of 64 zeros. The webhook Lambda recomputes the HMAC-SHA256 of the body with the stored secret, compares in
constant time, and refuses. Nothing is published to SNS and no Step Functions run starts. Before any of that, it also refuses a payload
over 5 MB and a timestamp more than 300 seconds old (replay protection).

### A duplicate alert runs once

Sentry can deliver one error twice (retries; an alert rule and an integration both firing). INGEST records the Sentry issue id with a
conditional write that expires after 24 hours, so a second delivery cannot take it.

```
$ python scripts/test_flows.py duplicate
issue dup-37d1a112 was already marked as taken; started run exec-307c9e03 for it.
run exec-307c9e03: SUCCEEDED
path: InputShape -> Ingest -> Accepted -> Dropped
decision: ... status duplicate (Sentry issue dup-37d1a112 is already being handled)
PR: None
```

The run ended in about 5 seconds at `Dropped`, with no Fargate task and no Bedrock call. The marker is a row in the rate-limit table with
key `sentry-issue#<id>` and an `expires_at` attribute. Full logs: [runs/exec-307c9e03.md](runs/exec-307c9e03.md).

### A stage crashes and a human is told

When any stage fails, Step Functions catches it, calls the Notify Lambda in `failure` mode, and ends the run as failed. If the stage
crashed before it saved anything, the Notify Lambda starts the record from the incident itself. This was seen for real when the Slack secret
was first connected: INGEST was denied access and the channel received

```
[WARNING] [Healer] demo-app: pipeline error in ingest
The self-healing pipeline hit an error in the ingest stage and stopped.
Service: demo-app   Issue: AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)
Error: ... AccessDeniedException ... (the full Lambda error, including the AWS account number and role ARNs)
Execution: exec-ddec46ad
```

That message exposed internal identifiers, so failure messages now carry only the error type and message, with ARNs shown as `[arn]` and
account numbers as `[account]`, and no stack. The full error stays in the stage's CloudWatch log and the audit file. A failure
cannot be reproduced on demand without breaking something, so it is covered by tests rather than a script.

---

