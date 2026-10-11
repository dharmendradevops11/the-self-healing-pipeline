# Architecture

Figure 2.1 of the book, as code. The *why* behind each choice is in [DECISIONS.md](DECISIONS.md). What the book promises,
item by item, is in [BOOK_SPEC.md](BOOK_SPEC.md).

```
Sentry webhook ──► API Gateway ──► WebhookReceiver Lambda   HMAC-SHA256, replay window, size cap
                                        │ publish
                                        ▼
                                   SNS trigger topic ──► SQS (+ DLQ) ──► EventBridge Pipe
                                                                              │
                                                                              ▼
                                                                  Step Functions state machine
   Ingest (Lambda)      rate limit 3/service/hour · classifier · last 20 log lines
   Investigate (Fargate) clone · read implicated files · commits · Bedrock · composite confidence · blast radius
   Route (Lambda)       escalation matrix: auto_fix_pr | fix_pr_standard_review | fix_pr_expedited_review | investigation_only
   Fix (Fargate)        diff on a healer/ branch · allowlist before git apply          (skipped for investigation_only)
   Test (Fargate)       type-check · unit tests · lint on the branch                   (skipped for investigation_only)
   OpenPr (Lambda)      PR with the reviewer packet (HEALER_REPORT.md)
   Notify (Lambda)      Slack and/or SNS, by escalation tier
   Escalate (Lambda)    investigation-only PR (HEALER_REPORT.md only) + message
```

A human reads the pull request and merges or rejects it. There is no merge code anywhere in this repository.

## The state bus

Fargate tasks are stateless. `ecs runTask.sync` returns an exit code and no output, so each stage loads
`pipeline-state/{execution_id}/state.json` from S3, does its work, and saves it back (`healer/state.py`). Step Functions
passes only the execution ID. Because Step Functions waits for each task to exit before the next state starts, no stage polls
for another's output.

## Two buckets

| Bucket | Holds | Lifetime |
|---|---|---|
| `self-healing-pipeline-audit-logs-<account>` | `audit/{execution}/step_NNN_{type}.json`, shadow records | Object Lock GOVERNANCE when enabled; nothing may delete |
| `self-healing-pipeline-state-<account>` | `pipeline-state/…` | disposable; lifecycle-expired after 30 days |

## Tables

| Table | Key | Purpose |
|---|---|---|
| `investigation_rate_limits` | service, hour | atomic limiter, 3/hour |
| `pr-throttle` | `pr-count#{date}` | daily PR cap |
| `agent-trust-ledger` | execution_id; GSI `category-timestamp-index` | model accuracy by failure category |
| `remediation_history` | incident_id; GSI `service-created-index` | what was done, what the human decided |

## The decision

1. Model certainty (0–100) → **composite** = 0.30 signal + 0.45 model + 0.25 history (`healer/gate/confidence.py`).
2. Band: low <60, medium 60–84, high ≥85. The fix threshold (60) is a deployment parameter.
3. **Blast radius** from the service registry: critical (PII/payments or >500k users), high (>50k), medium (>5k), low.
4. The 12-cell matrix gives the escalation tier, the page rule and what the pipeline may do (`healer/gate/escalation.py`).
5. Flags that always put a human in front of it (`healer/gate/human_review.py`).

## Guardrails, outermost first

webhook HMAC + replay window → rate limiter → classifier (a filter, never a gate; fails closed) → sanitiser + `<untrusted_telemetry>`
delimiters → model → path allowlist and patch limits **before** `git apply` → `healer/` branch only → tests → PR → human.
Credentials are fetched at the moment of use and are never in environment variables, the audit log, or a URL.

## Code map

`healer/ingest` · `investigate` · `gate` · `fix` · `test` · `pr` · `notify` · `guardrails` · `ledger` · `llm` · `library/` (the
chapter listings that are not on the main path) · `stages.py` (one function per box above) · `pipeline.py` (in-process runner) ·
`handlers.py` (Lambda) · `tasks.py` (Fargate) · `infra/` (CDK).
