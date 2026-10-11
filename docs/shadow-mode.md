# Earning trust in phases (Chapter 17)

"Trust has to be rolled out in phases." Set with `healer:phase` (or `HEALER_PHASE`).

| Phase | What happens | How long | Code |
|---|---|---|---|
| **shadow** | Read-only. Analyses every failure, writes "if I'd been allowed to act, here is what I would have done" to the audit bucket. No branch, no PR, no message. | 2 to 4 weeks | `record_shadow` |
| **supervised** | Generates patches and opens PRs. Nothing merges without review. One low-traffic service, business hours. **3 PRs a day**, counted in DynamoDB so a cold start cannot reset it. | until it is boring | `PRThrottle` |
| **autonomous** | Still PR-only. Hard limits: fewer than 5 files, diff under 1,000 lines, tests pass, service stable for the last hour. Loosen slowly. | not in the first month | `AutonomyLimits` |

Nothing merges itself in any phase.

## What to look at

- **Shadow records**: `shadow/…` keys in the audit bucket. Review them in postmortems. Look for where it is confidently,
  spectacularly wrong.
- **Merge rate** (`merge_rate` in `healer/guardrails/phases.py`): below 30% means something is broken, either bad patches,
  an untrusted process, or PRs rotting because nobody owns approval. Record why each PR was rejected ("wrong approach",
  "breaks compliance", "doesn't address root cause").
- **Confidence calibration**: a model that reports 80 may succeed closer to 72% of the time. The trust ledger
  (`agent-trust-ledger`) is how the composite score learns that gap.

## Rolling out

One team first (technical enough to give sharp feedback, not so critical that a bad merge is a postmortem). Two weeks.
Then a second team with a genuinely different stack. Then one or two services every few days.
