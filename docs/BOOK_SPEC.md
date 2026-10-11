# Book specification: what *The Self-Healing Pipeline* promises

This file is the contract between the published book and this repository. Every design decision in the
code is checked against it. If the code and this file disagree, one of them is wrong, and we fix it on purpose.

**Sources, in order of authority**

1. The book's printed code listings (`chapters/`, `companion_code/`). Reproduced as printed.
2. The book's prose, tables and figures (Figure 2.1, Appendices D, E and F, Chapter 17).
3. This repository's additions, always labelled "beyond the book" in [book-to-code.md](book-to-code.md).

Read from the published interior PDF (`publishing/The_Self-Healing_Pipeline_Interior.pdf`, 19 chapters, 9 appendices).

**Status key:** ✅ aligned · 🟡 aligned with a documented difference · ❌ not yet aligned (a work item) · ⏳ not built yet

---

## 1. The system in one paragraph

A Sentry error reaches a webhook. It flows through SNS and SQS into one Step Functions execution. An INGEST Lambda
attaches the last 20 CloudWatch log lines. INVESTIGATE (Fargate) clones the repository, reads the files named in the
stack trace, correlates recent commits, and asks Claude on Bedrock for a root-cause hypothesis and a 0–100 confidence.
That raw number is converted to a composite confidence, paired with a blast-radius tier, and looked up in an escalation
matrix that decides what the system may do. If a fix is authorised, FIX (Fargate) writes a diff on a `healer/` branch,
TEST (Fargate) runs type-check, unit tests and lint, and a PR Lambda opens a pull request with the evidence. Slack is
notified. **A human merges or rejects. Nothing merges itself, at any score.** (Ch. 1, 2, 18)

## 2. Architecture (Figure 2.1, Ch. 1, 2, 8, 14, 18)

### 2.1 Flow

```
Sentry webhook (HMAC-SHA256, constant-time, replay-protected)
  -> SNS (fan-out) -> SQS -> EventBridge Pipe -> Step Functions
       1 INGEST       Lambda   rate limit (3/service/hour, atomic DynamoDB), last 20 CloudWatch lines
       2 INVESTIGATE  Fargate  clone repo, read implicated files, commits, Bedrock, confidence
         gate         composite confidence (60 / 85 bands) x blast radius -> escalation matrix
       3 FIX          Fargate  diff on healer/ branch, allowlist enforced before git apply
       4 TEST         Fargate  type-check, unit tests, lint on the changed files
       5 PR           Lambda   PR with root cause, confidence, files read, fix strategy, test results
       6 NOTIFY       Slack (+ SNS)
       "Escalate / Slack" branch when the matrix does not authorise a fix
```

"Seven stages" (Ch. 18): ingest, investigate, route, fix, test, PR, notify. Our Step Functions names these
`Ingest, Investigate, Route/Gate, Fix, Test, OpenPr, Notify`.

### 2.2 Structural rules stated in the book

| Rule | Where | Status |
|---|---|---|
| Stateless Fargate tasks that treat **S3 as the state bus**; `ecs runTask.sync` returns exit codes without stdout, so results go to S3 | Ch. 8 "Orchestration layer", Ch. 18 | ✅ `healer/state.py` |
| Step Functions orchestrates; no in-process daemon | Ch. 8 | ✅ `infra/pipeline_stack.py` |
| Rate limit before anything else: 3 investigations per service per hour, atomic `ConditionExpression` | Ch. 2, 5 | ✅ `healer/ingest/rate_limiter.py` |
| Coordination signal lives in DynamoDB (`ConsistentRead=True`), not S3 polling | Ch. 14 | 🟡 nothing polls: Step Functions runs tasks to completion. Documented in `DECISIONS.md` |
| Everything the fix stage does is on a `healer/` branch, never `main` | Ch. 2, 7 | ✅ |
| Allowlist is checked **before** any diff reaches `git apply` | Ch. 2, 7, 17 | ✅ |
| Model is a replaceable component (system prompt + user prompt in, structured JSON out); model ID is a **configuration parameter** | Ch. 18, App. E | ✅ `BEDROCK_MODEL_ID`, CDK context `healer:bedrock_model_id` |
| JSON extraction tolerates fenced and bare JSON | Ch. 18 | ✅ `healer/llm`, `diagnose.py` |
| Every Bedrock prompt and response logged to S3 with execution ID and timestamp ("Nothing happens without a record") | Ch. 18 | ✅ audit logger (see the Ch. 8 vs 18 contradiction on raw prompts, §9) |
| One trace/execution ID follows a failure through every stage | Ch. 14 | ✅ `execution_id` |
| PR is the audit trail: root cause, confidence, every file read, strategy, test results | Ch. 2, 18 | ✅ `healer/pr/packet.py` |
| No auto-merge, ever, by design (documented in Contributing guide) | Ch. 18 | ✅ no merge code exists. ✅ `CONTRIBUTING.md` |

## 3. Technology stack (Appendix E, Ch. 17)

| Component | Book | Repo |
|---|---|---|
| Python | 3.11.x | ✅ 3.11 (venv, Lambda runtime, Docker image) |
| Node.js | 20.x LTS (CDK CLI, webhook validator) | 🟡 CDK CLI only. Webhook validator is Python (Ch. 11, 17 listings are Python) |
| boto3 | 1.34.x | ✅ |
| AWS CDK | 2.138.0+ | ✅ `aws-cdk-lib>=2.138` |
| Bedrock | runtime API, `bedrock-2023-05-31` | ✅ `healer/llm/bedrock.py` |
| Claude model | `anthropic.claude-sonnet-4-20250514-v1:0` tested, now legacy; keep ID in config | ✅ default empty, set by config |
| LocalStack | 3.4.0+ | ✅ `localstack/localstack:3.4.0` |
| Docker | 24.0.7+ | ✅ |
| statsmodels / scikit-learn / Prophet | 0.14.1 / 1.4.x / 1.1.5 | ✅ pinned; Prophet optional |
| Region | us-east-1 in all commands | ✅ default |

Ch. 17 prerequisites also name a primary, a complex-case fallback and a quick-analysis model. ✅ Three settings: `healer:bedrock_model_id`, `bedrock_fallback_model_id`, `bedrock_quick_model_id` (`healer/llm/router.py`).

## 4. Decision model (Ch. 2, 9) — the part readers will test hardest

| Item | Book | Status |
|---|---|---|
| Composite = 0.30 signal + 0.45 model + 0.25 history; sparse history uses 0.5 prior and half its weight moves to model | Ch. 9 | ✅ `healer/gate/confidence.py` |
| Bands: low <60, medium 60–84, high ≥85 | Ch. 2, 9 | ✅ |
| 60 authorises fix generation and a PR. ≥85 plus a small blast radius is "confident enough to act". Nothing merges at any score | Ch. 2 | ✅ |
| Blast radius tiers: critical (PII/payment or >500k users), high (>50k), medium (>5k), else low | Ch. 9 | ✅ `healer/gate/blast_radius.py` |
| 12-cell matrix → `auto_fix_pr`, `fix_pr_standard_review`, `fix_pr_expedited_review`, `investigation_only`; tiers informational/warning/critical; page false/business_hours_only/always | Ch. 9 | ✅ `healer/gate/escalation.py` |
| No response from secondary on-call in 15 min → automated escalation. No action ever merged or executed on timeout | Ch. 9 | 🟡 timeout rule documented; no on-call integration (`get_current_oncall` is a parameter) |
| Reviewer packet `HEALER_REPORT.md` (YAML: incident, diagnosis, proposed_fix, blast_radius, rollback_plan) | Ch. 9 | ✅ `healer/pr/packet.py` |
| Step-level audit log `audit/{execution}/step_NNN_{type}.json`; trust ledger (`agent-trust-ledger`, GSI `category-timestamp-index`); rollbacks | Ch. 9 | ✅ `healer/ledger/` |
| **Below 60 ("investigation_only") = an investigation-only PR containing `HEALER_REPORT.md` and no source change** | Ch. 1 (policy block), Ch. 2 Level 4, Ch. 9, 12, 14, 16, 18 | ✅ `stages.escalate` pushes a `healer/` branch holding only `HEALER_REPORT.md`, opens a PR labelled `healer: investigation-only`, and notifies Slack (D1) |
| 40 was too low, 60 is the deliberate threshold, it is a CloudFormation parameter, start at 70 to be conservative | Ch. 16, 18 | ✅ 60 default; `healer:confidence_threshold` CDK context / `HEALER_CONFIDENCE_THRESHOLD` |
| Never decide **whether a human sees it** by confidence. Always route critical services, never-before-seen patterns and "successful but recurring" fixes to a human | Ch. 14 | ✅ `healer/gate/human_review.py`: critical service, new pattern, recurrence after a merged fix → `healer: human-review` label and a line in the message |

## 5. Guardrails and security (Ch. 7, 11, 17, App. C, F)

| Control | Status |
|---|---|
| Path allowlist: `SAFE_PATH_PREFIXES` = `src/ lib/ app/ packages/`; anchored forbidden patterns (`^infrastructure/`, `^\.github/`, `(^|/)migrations/`, `(^|/)Dockerfile$`, `\.ya?ml$`, `\.sh$`) | ✅ `healer/guardrails/allowlist.py` |
| `config/allowlist.yaml`: allowed globs, denied globs (deny wins), `max_files_per_patch: 5`, `max_lines_per_file: 500`, `require_tests: true` | ✅ `config/allowlist.yaml` (the Ch. 17 file) + `PatchPolicy.from_file` |
| Four-layer injection defense: hardened sanitizer, `<untrusted_telemetry>` delimiters with breakout protection, classifier as filter-not-gate failing closed, sandbox/IAM | ✅ |
| Webhook: HMAC-SHA256 on the **raw** body, constant-time, base64 handling, 5 MB cap, replay window 300 s, previous secret valid 24 h | ✅ `healer/ingest/webhook.py` |
| Secrets in Secrets Manager, fetched at use, never env vars, never logged; fail-closed scrubber; three-step rotation | ✅ |
| Secret names `self-healing-pipeline/github-token` (JSON `{"token": …}`), `self-healing-pipeline/sentry-dsn` | ✅ JSON read; CDK takes ARNs; `docs/deploy.md` uses these names |
| KMS trap: grant `kms:Decrypt` + `kms:DescribeKey` next to `GetSecretValue` | 🟡 stack uses the AWS-managed key; the trap is explained in `docs/troubleshooting.md` |
| IAM roles per Appendix F: `Healer-Ingest-Role` (logs:FilterLogEvents, sns:Publish, scoped log groups), `Healer-Investigate-Role` (bedrock:InvokeModel, s3:GetObject), `Healer-Remediate-Role` (ssm:SendCommand, ecs:UpdateService, only `healer-eligible=true` tag), `Healer-Audit-Logger-Role` (s3:PutObject only, **denies s3:DeleteObject**) | ✅ `Healer-Ingest-Role`, `Healer-Investigate-Role`, `Healer-Remediate-Role` (acts only on `healer-eligible=true`; code in `healer/remediate/`), plus `Healer-Fix-Role` and `Healer-Test-Role`. Every role is denied `s3:DeleteObject` on the audit bucket and the Ch. 11 hard limits. The audit-logger duty is done by each stage |
| Audit bucket: versioned, private, TLS only, Object Lock **GOVERNANCE**, never bypass on teardown | ✅ optional Object Lock in `state_stack.py` |
| Fine-grained GitHub PAT (Contents RW, Pull requests RW, Metadata R), 90-day expiry, machine user | ✅ [infra/policies](../infra/policies) and `docs/deploy.md` |
| Compliance record: `approved_by` is never the agent | ✅ `healer/ledger/compliance.py` |

## 6. Data stores and names

| Resource | Book name | Repo | Status |
|---|---|---|---|
| Rate limit table | `investigation_rate_limits` (key `service`, `hour`) | same | ✅ |
| Remediation history | `remediation_history` | same | ✅ |
| Trust ledger | `agent-trust-ledger`, GSI `category-timestamp-index` | same | ✅ |
| PR throttle | DynamoDB item `pr-count#{date}` | `pr-throttle` | ✅ |
| Audit bucket | `self-healing-pipeline-audit-logs` (Object Lock) | `self-healing-pipeline-audit-logs-<account>` | ✅ |
| State bucket | `self-healing-pipeline-state` (non-audit, tears down normally) | `self-healing-pipeline-state-<account>` (disposable) | ✅ (D2) |
| ECR repository | `self-healing-pipeline/healer-agent` (Ch. 17 teardown) | same | ✅ |
| Container image | `self-healing-pipeline/webhook-receiver:latest` (Ch. 17 build) | Dockerfile provided; deployed as a zip Lambda | 🟡 documented difference |
| Branch names | `healer/YYYY-MM-DD-<slug>-<suffix>`, e.g. `healer/2024-03-15-typeerror-cannot-read-prop-a1b2c3` | same shape | ✅ |
| Agent state key | `{state_key}/context.json`, `{state_key}/result.json` | `pipeline-state/{id}/state.json` | 🟡 one file per execution |

## 7. Operations (Ch. 17)

| Promise | Status |
|---|---|
| `docker-compose up` boots LocalStack (`SERVICES=s3,dynamodb,secretsmanager`, `DEBUG=1`, `PERSISTENCE=1`, `./localstack-data`), then run the pipeline end to end offline | ✅ compose file, `--localstack`, `make local-test` |
| Three core functions locally: failure detector, AI analyzer, patch applier | ✅ mapped in `docs/start-local.md` |
| `build.sh` builds Lambda deps with `--platform manylinux2014_x86_64`, strips `__pycache__` | 🟡 CDK bundles the asset; explained in `docs/deploy.md` |
| `docker build --platform linux/amd64 …` then ECR login/tag/push; use commit SHAs in production, not `latest` | ✅ `scripts/build-and-push.sh` (accepts a tag) |
| Test with Lambda Runtime Interface Emulator (`docker run -p 9000:8080`, curl `/2015-03-31/functions/function/invocations`) | ✅ `docs/start-local.md` |
| Phases: **shadow** (2–4 weeks, read-only) → **supervised** (one low-traffic service, business hours, **3 PRs/day**, DynamoDB-backed) → **autonomous with limits** (<5 files, <1000 diff lines, tests pass, stable 1 h) | ✅ `healer/guardrails/phases.py` |
| Merge rate is the health signal; below 30% means something is broken; rejection reasons captured | ✅ `merge_rate`; ✅ `docs/templates/pull_request_template.md` |
| Webhook troubleshooting (API Gateway base64 proxy body), cost spike triage (Bedrock token metrics), healthy run costs $0.70–$2.20 | ✅ code and `docs/troubleshooting.md` |
| Teardown: `cdk destroy --all -f`; ECR guarded `batch-delete-image`; check Object Lock before touching the audit bucket; `aws s3 rm` the state bucket; `delete-secret` | ✅ `scripts/teardown.sh` (state bucket step follows D2) |
| Release tag `v1.0.0`, `requirements.txt`, tested with Python 3.11 / LocalStack 3.4.0 / CDK 2.138.0 | ⏳ tag at publish |
| Handoff docs: `ARCHITECTURE.md`, `RUNBOOK.md` (Bedrock throttling, IAM errors, SQS backlog, ECS OOM, cross-account assume-role), `ONBOARDING.md`, `DECISIONS.md` | ✅ `docs/ARCHITECTURE.md`, `RUNBOOK.md`, `ONBOARDING.md`, `DECISIONS.md` |
| Billing alarm recommended | ✅ `healer:billing_alarm_usd` |

## 8. Chapter inventory: every listing the book prints

| Ch | Topic | Listings in `chapters/` | Code | Status |
|---|---|---|---|---|
| 1 | Cost of failures; policy block | `sample_03.txt` (allowlist/threshold YAML) | `healer/gate`, `patch_policy` | ✅ |
| 2 | Four stages | 4 | `ingest`, `investigate`, `fix`, `ledger` | ✅ |
| 3 | ML in triage | isolation forest, correlation, validator, heuristics | `healer/library/*`, `guardrails` | ✅ |
| 4 | Dashboards | logs, health score, deploy correlation | `ingest/logs.py`, `library/observability.py` | ✅ |
| 5 | Alert noise | z-score, MAD, EMA, isolation forest, DevOps Guru, limiter | `library/*`, `ingest/alert_limiter.py` | ✅ |
| 6 | Slow outages | ARIMA, Prophet, flakiness, deploy risk | `library/*` | ✅ |
| 7 | Remediation | allowlist, runbooks, retries, breakers, confirm, patterns | `library/remediation/` | ✅ |
| 8 | AI write access | investigate flow, agent executor, memory leak | `investigate/`, `library/memory_investigation.py` | ✅ |
| 9 | Trust | confidence, blast radius, matrix, ledger | `gate/`, `ledger/` | ✅ |
| 10 | Chaos | 3 Python + FIS JSON | `healer/library/chaos.py`, `infra/policies/fis-ecs-stop-task.json` | ✅ |
| 11 | Security | delimiters, sanitizer, classifier, webhook, secrets, scrubber, IAM JSON | `guardrails/`, `ingest/webhook.py`, `infra/policies` | ✅ |
| 12 | SLOs / DORA | DORA, SLO tracker, retrospective | `healer/library/slo.py` | ✅ |
| 13 | Autonomous policy, decision trail | 4 Python + 3 text | `healer/library/agents.py` | ✅ (the example_04 analysis is an inline script; its numbers are the book's, not code to run) |
| 14 | Scale | Redis limiter, cross-account IAM JSON | `healer/library/scale.py`, `infra/policies/cross-account-trust.json` | ✅ |
| 15 | ROI | none | — | n/a |
| 16 | Four incidents | none (narrative) | scenarios are our own | n/a |
| 17 | Start local | compose, Docker, YAML, PR throttle, signature, teardown | `phases.py`, `webhook.py`, `scripts/`, `docker/` | ✅ / 🟡 |
| 18 | Limits | none | — | n/a |
| App. D | `companion_code/` | 6 modules named | `companion_code/` | ✅ untouched |

## 9. Places where the book disagrees with itself (decisions needed or taken)

| # | Conflict | Decision |
|---|---|---|
| D1 | Below 60: Ch. 1, Ch. 2 Level 4, Ch. 12, 14, 16, 18 say an **investigation-only PR with `HEALER_REPORT.md`**. Figure 2.1 shows **"Escalate / Slack"** with no FIX/TEST/PR. | **Decided (author, 2026-10-09): follow the book, and where the figure says Slack, wire Slack, small and configurable.** `investigation_only` opens the report-only PR and sends the Slack/SNS message with the PR link. Implemented. |
| D2 | Ch. 17 names two buckets (audit, state); Ch. 8 and 18 put inter-stage state and the audit trail in S3 without separating them. | Two buckets, as Ch. 17 names them (account id appended, S3 names are global). Implemented. |
| D3 | INGEST fetches the last **20** log lines (Ch. 1, 2, 10, 14) vs **30** (Ch. 16, 18). | Default 20, configurable (`HEALER_LOG_LINES` / `healer:log_lines`). Implemented. |
| D4 | Ch. 17 builds a `webhook-receiver` image but tears down a `healer-agent` ECR repo. | Keep `healer-agent` as the repository the stack creates. The webhook Dockerfile is provided for the container route; the stack deploys a zip Lambda. |
| D5 | Ch. 8 stores raw prompts in the audit trail; Ch. 18 / 11 say sanitise and scrub. | Store the **sanitised** prompt and scrubbed response; secrets never reach the audit bucket. |
| D6 | Ch. 18 says the pipeline targets TypeScript/Node.js (`github-client.ts`, `extractFilesFromStackTrace`); Ch. 17's allowlist and every listing are Python. | The repo is the Python rebuild the stack table requires. The demo app is Python; stack-trace parsing accepts Python and Node frames. |
| D7 | Figure 2.1 and Ch. 18 describe the original TypeScript/CloudFormation system; Appendix E and Ch. 17 require Python + CDK. | Python + CDK. Behaviour matches the prose; implementation language follows Appendix E. |
| D8 | "Ten engineers" (Ch. 13/15) vs the Preface. | Out of scope for the repo. Tracked in the private errata list. |

## 10. Work queue derived from this file (in order)

1. ~~D1~~, ~~D2~~, ~~log lines / threshold / allowlist.yaml~~, ~~Appendix F role names~~, ~~Ch. 14 human-review flags~~ done.
6. ~~DynamoDB coordination record~~ documented decision (DECISIONS.md). ~~Docs~~ done: `start-local`, `deploy`, `shadow-mode`, `troubleshooting`, `teardown`, `ARCHITECTURE`, `RUNBOOK`, `ONBOARDING`, `DECISIONS`, `CONTRIBUTING`.
7. ~~Libraries for Ch. 10, 12, 13, 14~~ and ~~appendices A–I~~ done.
8. Update `docs/book-to-code.md`, README status, and re-verify this file against a clean checkout.
9. ~~Real AWS test and teardown~~ done, see `docs/aws-test-log.md`.
10. Publish decisions (fresh repo vs history rewrite, tag `v1.0.0`, URL in the Amazon description).


## 11. Audit findings and what was done (2026-10-09, prose read against the code)

| Book says | Gap found | Now |
|---|---|---|
| Ch. 2 prompt has slots for recent deployment, dependency changes, metric history | never filled | ✅ filled from the clone and CloudWatch |
| Ch. 3 gate 2: do the suggested files exist? | not checked | ✅ `check_constraints`, flagged to a human |
| Ch. 3 answer carries `fixStrategy`, `reasoning` | ignored | ✅ kept for the reviewer |
| Ch. 2/9 Stage 4: record whether the human accepted or rejected | ledger rows stayed `pending` forever | ✅ GitHub `pull_request` webhook → ledger and history |
| Ch. 9/16: quarterly confidence-distribution report | no way to build it | ✅ `bucket_stats_from_ledger` → `review_threshold_adjustment` |
| Ch. 11: explicit Deny statements; nothing may delete tables, touch IAM/billing or assume roles | none | ✅ on every role we create |
| Ch. 11: tag PCI-scoped services, require human approval before the agent touches them | not enforced | ✅ `pci_scoped` forces `investigation_only` |
| Ch. 14: boto3 pool 50 + adaptive retries; multi-region round-robin; throttle vs hard failure | not built | ✅ |
| Ch. 14: per-stage time, end-to-end time, one trace id | not built | ✅ EMF on stdout |
| Ch. 16: every alert has a named team and on-call | unowned services looked routine | ✅ flagged `unowned service` |
| App. F: `Healer-Remediate-Role`, `healer-eligible` tag distinct from `chaos-eligible` | not built | ✅ |
| Ch. 17: primary / fallback / quick models | one model | ✅ |

Judged and left as documented differences: rate-limited alerts are dropped as Ch. 2 prints (Ch. 16/18 say "queued"); the Ch. 8
memory-leak agent that "runs every fifteen minutes via EventBridge" is a case study built as a library, because the pipeline is
reactive by design (Ch. 2); sandbox egress is not disabled (Appendix C).
