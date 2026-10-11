# Appendix A: Glossary

Terms as the book uses them. Where a term has a home in the code, it is named.

- **AIOps**: machine learning, pattern matching and data science applied to operational tasks and monitoring.
- **Alert fatigue**: the exhaustion of engineers bombarded by alerts. A system design failure, not an operations team failure.
  (`healer/ingest/rate_limiter.py`, `alert_limiter.py`)
- **Blast radius**: the potential impact if an automated remediation fails or is applied wrongly. Constraining it with
  allowlists, PR caps and scoped credentials is the central safety discipline. (`healer/gate/blast_radius.py`)
- **Canary deployment**: rolling a change to a small fraction of traffic first.
- **Chaos engineering**: injecting failures on purpose to verify resilience works. (`healer/library/chaos.py`)
- **Circuit breaker**: stops calls to a failing dependency after repeated errors. (`healer/library/remediation/circuit_breaker.py`)
- **Confidence threshold**: the score (0 to 100) that decides between proposing a fix and an investigation-only report. 60 is
  the boundary. (`healer/gate/escalation.py`, `healer:confidence_threshold`)
- **Context switching**: stopping one task to handle an alert. Roughly 23 minutes to regain deep focus (Gloria Mark, UC Irvine).
- **Deterministic validation**: non-AI checks (pytest, linters, schema validation) that guard a proposed change. (`healer/test/`)
- **DORA metrics**: deployment frequency, lead time for changes, change failure rate, time to restore. (`healer/library/slo.py`)
- **Flaky test**: passes and fails under identical conditions. (`healer/library/flakiness.py`)
- **Heuristic confidence**: a calibrated score from historical backtesting, distinct from the model's self-report.
  (`healer/gate/confidence.py`, the trust ledger)
- **Human-in-the-loop (HITL)**: the AI suggests, a human approves. Review of every healer PR is permanent. 
- **LocalStack**: a local AWS emulator. (`docker-compose.yml`)
- **Median absolute deviation (MAD)**: a robust measure of variability. (`healer/library/statistics.py`)
- **MTTR**: mean time to recovery. The book reports 4.2 hours to 22 minutes in its deployment.
- **Prompt injection**: untrusted input that tries to override the model's instructions. (`healer/guardrails/`)
- **Runbook**: a step-by-step procedure for an operational situation. The investigation report is a drafted runbook entry.
- **Self-healing**: detect, diagnose, remediate and verify, with human approval for any change across the review boundary. It
  does not mean "no humans"; humans are spared the diagnosis and the drafting, and reserved for the judgment.
