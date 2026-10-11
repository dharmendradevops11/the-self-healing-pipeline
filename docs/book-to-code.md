# Book to code

Where each chapter's code lives, what was added beyond the printed listing, and how to try it.
The book is the specification. Where this repository goes further than a listing, it says so here.

| Chapter | Section | Code | Tests |
|---|---|---|---|
| 2 | Stage 1, Detect | `healer/ingest/rate_limiter.py` | `tests/unit/test_chapter02.py` |
| 2 | Stage 2, Diagnose | `healer/investigate/diagnose.py`, `healer/llm/` | `tests/unit/test_chapter02.py` |
| 2 | Stage 3, Remediate | `healer/guardrails/allowlist.py`, `healer/fix/` | `tests/unit/test_chapter02.py` |
| 2 | Stage 4, Learn | `healer/ledger/remediation_history.py` | `tests/unit/test_chapter02.py` |
| 3 | Prompt injection (baseline filter) | `healer/guardrails/sanitizer.py` | `tests/unit/test_chapter02.py` |
| 3 | Isolation forest, correlation, lift | `healer/library/anomaly.py`, `healer/library/correlation.py` | `tests/unit/test_chapter03.py` |
| 3 | When the model lies | `healer/guardrails/validator.py` | `tests/unit/test_chapter03.py` |
| 3 | Sparse data, build failures, alert suppression | `healer/library/heuristics.py`, `build_failure.py`, `alerting.py` | `tests/unit/test_chapter03.py` |
| 4 | Fetching the logs that matter | `healer/ingest/logs.py` | `tests/unit/test_chapter04.py` |
| 4 | Structured logs, health score, deploy correlation | `healer/library/observability.py` | `tests/unit/test_chapter04.py` |
| 5 | Z-score, MAD, EMA | `healer/library/statistics.py` | `tests/unit/test_chapter05.py` |
| 5 | Multivariate isolation forest, DevOps Guru filter | `healer/library/pipeline_anomaly.py`, `devops_guru.py` | `tests/unit/test_chapter05.py` |
| 5 | Alert flood limiter, false-positive feedback | `healer/ingest/alert_limiter.py`, `healer/ledger/alert_feedback.py` | `tests/unit/test_chapter05.py` |
| 6 | Reactive vs predictive, ARIMA and Prophet forecasts | `healer/library/forecasting.py` | `tests/unit/test_chapter06.py` |
| 6 | Flaky tests, deployment risk | `healer/library/flakiness.py`, `healer/library/deploy_risk.py` | `tests/unit/test_chapter06.py` |
| 7 | Allowlist (Chapter 7 version), remediation rate limit | `healer/guardrails/allowlist.py`, `remediation_limiter.py` | `tests/unit/test_chapter07.py` |
| 7 | Runbook handler, selection, retry, circuit breakers | `healer/library/remediation/` (`runbook`, `selection`, `retry`, `circuit_breaker`) | `tests/unit/test_chapter07.py` |
| 7 | Confirm-before-execute, remediation patterns, policies | `healer/library/remediation/` (`confirm`, `patterns`, `policy`) | `tests/unit/test_chapter07.py` |
| 8 | The INVESTIGATE flow: cheap signals first, optional tools | `healer/investigate/investigate.py`, `tools.py` | `tests/unit/test_chapter08.py` |
| 8 | Orchestration layer and tool model | `healer/investigate/agent.py`, `tools.py` | `tests/unit/test_chapter08.py` |
| 8 | Memory investigation, steps 1 and 2 | `healer/library/memory_investigation.py` | `tests/unit/test_chapter08.py` |
| 10 | Hypotheses from history, model-proposed scenarios, novelty library, blast radius before injection, FIS template | `healer/library/chaos.py`, `infra/policies/fis-ecs-stop-task.json` | `tests/unit/test_chapter10.py` |
| 11 | Layer 1 delimiters, hardened sanitizer, red-team suite | `healer/guardrails/delimiters.py`, `sanitizer.py` | `tests/unit/test_chapter11.py` |
| 11 | Layer 2 classifier (a filter, never a gate) | `healer/guardrails/classifier.py` | `tests/unit/test_chapter11.py` |
| 11 | Webhook validation, replay protection, rotation overlap | `healer/ingest/webhook.py` | `tests/unit/test_chapter11.py` |
| 11 | Secrets, three-step rotation, log scrubber | `healer/guardrails/secrets.py`, `scrubber.py` | `tests/unit/test_chapter11.py` |
| 11 | Audit and compliance records | `healer/ledger/compliance.py` | `tests/unit/test_chapter11.py` |
| 11 | IAM policy documents | `infra/policies/` | `tests/unit/test_chapter11.py` |
| 12 | DORA metrics, SLO burn rate, threshold retrospective | `healer/library/slo.py` | `tests/unit/test_chapter12.py` |
| 13 | Autonomous response policy, decision trail, accountability | `healer/library/agents.py` | `tests/unit/test_chapter13.py` |
| 14 | Redis distributed rate limiter, cross-account trust policy | `healer/library/scale.py`, `infra/policies/cross-account-trust.json` | `tests/unit/test_chapter14.py` |
| 14 | Humans always see the exceptions (critical, new pattern, recurrence) | `healer/gate/human_review.py` | `tests/unit/test_book_alignment.py` |
| 17 | The allowlist as YAML with patch limits | `healer/guardrails/patch_policy.py` | `tests/unit/test_chapter17.py` |
| 17 | Earning trust in phases: shadow, supervised, autonomous | `healer/guardrails/phases.py` | `tests/unit/test_chapter17.py` |
| 17 | Daily PR cap in DynamoDB, merge-rate health signal | `healer/guardrails/phases.py` | `tests/unit/test_chapter17.py` |
| 17 | GitHub webhook signature | `healer/ingest/webhook.py` (`validate_signature`) | `tests/unit/test_chapter17.py` |
| 2 | The whole pipeline, wired (Figure 2.1) | `healer/pipeline.py`, `healer/demo.py` | `tests/unit/test_pipeline.py` |
| 17 | Build, push, deploy, teardown; LocalStack; Dockerfiles | `scripts/`, `docker/`, `docker-compose.yml`, `healer/demo.py --localstack` | `tests/integration/test_localstack.py` |
| 17 | Stack as code | `infra/` | `tests/unit/test_infra.py` |
| 2, 9 | Fix generation, test runner, PR host, reviewer packet, notifiers | `healer/fix/generate.py`, `healer/test/`, `healer/pr/`, `healer/notify/` | `tests/unit/test_pipeline.py` |
| 9 | Composite confidence | `healer/gate/confidence.py` | `tests/unit/test_gate.py` |
| 9 | Blast radius | `healer/gate/blast_radius.py` | `tests/unit/test_gate.py` |
| 9 | Escalation matrix | `healer/gate/escalation.py`, `healer/gate/decision.py` | `tests/unit/test_gate.py` |
| 9 | Audit log, rollbacks, trust ledger | `healer/ledger/` | `tests/unit/test_ledger.py` |

## Where the code goes beyond the printed listing

- **The listings call helpers the book never shows** (`checkout_branch`, `apply_patch`, `push_branch`,
  `rollback_branch`, `delete_branch`, `get_current_oncall`). They are implemented here: `healer/fix/git_ops.py` runs real
  `git`, and `get_current_oncall` is a parameter.
- **`apply_remediation` also checks the files the diff actually touches,** not only the list the model declared. A model
  that declares a safe file while the diff edits a CI workflow is refused.
- **`apply_remediation` commits before it pushes.** The printed listing pushes without committing.
- **Patches are applied with `--recount`,** because language models often miscount hunk line numbers.
- **A service missing from the blast-radius registry gets a default tier,** instead of being scored as zero risk.
- **Signal strength has a concrete formula.** The book names the input but not how to compute it.
- **The audit logger can resume its step numbering,** because the pipeline runs each stage in a separate process.
- **The Chapter 5 alert limiter uses a different condition than the printed one.** The printed
  `ConditionExpression` does arithmetic and calls `if_not_exists`, which DynamoDB rejects in a condition. The version here
  says the same thing in a form DynamoDB accepts.
- **The Chapter 5 z-score listing does not print what the book says.** It flags nothing, because with 9 points no value
  can exceed a z-score of 3.0. The test documents the real behavior. Use a lower threshold or more data.
- **The Chapter 4 health score reproduces the printed formula,** including its quirks: the weights sum to 0.9 and the
  latency term is uncapped.
- **The Chapter 6 Prophet listing is completed.** The book's version stops after `model.fit(df)`. The forecast and threshold
  check were added in the same return shape as the ARIMA function. Prophet is optional (`requirements-analytics.txt`), so
  its test is skipped unless it is installed.
- **The Chapter 7 patterns take their collaborators as named arguments.** The book's listings call helpers it never shows
  (`get_disk_usage`, `kubectl_exec`, `ssm`, `wait_for_interaction`, ...). Each is a parameter here, so a pattern runs against
  your platform or a test double. Dry-run is the default wherever the book offers it.
- **The Chapter 7 circuit breaker is reproduced as printed,** including a quirk: its cooldown is longer than its window, so
  it reopens after the window. Tests show both the printed behavior and a cooldown that is honored.
- **The Chapter 8 investigation feeds the Chapter 9 gate.** `investigate_failure` returns the evidence (log lines, trace, files
  read, commit context) that `compute_signal_strength` turns into the signal input of the composite score. If an optional
  tool fails the investigation says so, and a diagnosis made on less evidence gets a lower signal.
- **Stack-trace paths are checked for traversal before they are read.**
- **The memory anomaly check guards against an empty series and a zero starting value,** which would crash the printed listing.
- **The listings that read from Prometheus, CloudWatch, DevOps Guru or your own history store take that client as an
  argument,** so every one of them runs against your own numbers, or a test double, with no live system.
- **There are two sanitizers on purpose.** `sanitize_basic` is the Chapter 3 listing. `sanitize_for_prompt` is the Chapter 11
  version the pipeline uses: it also strips code fences and role markers. The book's own red-team suite fails against the
  Chapter 3 version, and a test shows both. Regular expressions stay a fragile layer: delimiters, the classifier, a sandbox
  and hard IAM limits are what the design relies on.
- **The webhook check goes beyond the printed listing.** It also rejects replays, accepts the previous secret for 24 hours
  after a rotation, caps the body at 5 MB, handles base64 bodies, and only parses JSON after the signature is verified.
- **The secret-rotation listing is corrected.** `testSecret` and `finishSecret` read the pending token from the `AWSPENDING`
  stage, where Secrets Manager keeps it.
- **The Chapter 11 log scrubber fails closed,** unlike the copy in `companion_code`, which fails open.
- **The investigation prompt is now fenced.** Every untrusted field is sanitized and the data sits inside an
  `<untrusted_telemetry>` block that the payload cannot close.
- **The phases are code, not just advice.** `PhaseController` turns the gate's decision into what may actually happen:
  shadow records only, supervised opens a capped pull request, and autonomous also needs fewer than five files, a diff under
  1,000 lines, passing tests and an hour of stability. Break any limit and it falls back to a reviewed pull request.
- **Three chapters print three different allowlists** (Chapter 2: four prefixes; Chapter 7: six prefixes plus `.husky/`;
  Chapter 17: YAML globs with patch limits). All three are implemented, so you can pick the one that matches your setup.
- **The Chapter 17 webhook listing checks the size on the decoded bytes,** not on the length of the base64 text.
- **Branch names carry a unique suffix,** as in the book's own example (`healer/2024-03-15-typeerror-cannot-read-prop-a1b2c3`),
  so two incidents touching the same file on the same day cannot collide.
- **The pipeline never merges.** The pull request is the end of what it may do. A fix whose tests fail opens as a draft.
- **The sanitizer is the Chapter 3 version.** It is a first-line filter and has known gaps. Chapter 11 adds the stronger layers.
- **The Chapter 10 scenario proposer takes the pipeline's model provider,** not a hard-wired Anthropic client, so it runs offline.
- **The Chapter 12 DORA script is a set of functions,** not a script that calls GitHub and PagerDuty on import. The HTTP `get` is a
  parameter.
- **The Chapter 13 listings are completed:** `Incident`, `parse_memory_gib` and `scrub_sensitive_data` are defined, and
  `map_accountability` (a docstring in the book) enforces its own rule: a human owns every change and the agent never approves.
- **Below the fix threshold** the pipeline pushes a branch holding only `HEALER_REPORT.md` and opens an investigation-only PR, and
  also sends the Figure 2.1 Slack message ([DECISIONS.md](DECISIONS.md)).
- **Chapter 2's prompt slots are filled.** Recent deployment (the head commit, labelled as a proxy), dependency changes
  (recent edits to manifests and lock files) and CloudWatch metric history come from the clone and from CloudWatch.
- **Chapter 3's constraint gate is real:** a model that names a file that does not exist is flagged to a human.
- **Chapter 9's verdicts arrive:** `healer/ledger/feedback.py` and the `/github` webhook turn a closed pull request into a
  ledger verdict and a remediation-history decision.
- **Chapter 11's hard limits are Deny statements on every role we create,** and a PCI-scoped service is never fixed.
- **Chapter 14:** `healer/llm/router.py` (round-robin regions, throttle versus hard failure), a bigger Bedrock connection
  pool with adaptive retries, and `healer/telemetry.py` (stage and end-to-end time, one trace id).
- **Chapter 17's model trio:** primary, fallback and a small model for the classifier are three settings.
- **Appendix F's `Healer-Remediate-Role`:** `healer/remediate/` restarts an ECS service only if it is tagged
  `healer-eligible=true`, never `chaos-eligible`.
- **Chapter 4's log filter never matches a real log line.** `get_relevant_logs` uses the pattern `[level=ERROR || level=FATAL]`.
  Tested on real CloudWatch it returned 0 of 29 ordinary lines, because a one-field space-delimited pattern only matches
  one-word events. The listing is kept as printed. INGEST uses `last_log_lines` instead: the newest 20 lines of every level, which is
  also what Chapter 2 says ("the last 20 CloudWatch log lines").
