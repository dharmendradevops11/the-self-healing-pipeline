# AWS re-check of the final code (2026-10-11)

The hardening pass (one path policy, binary-file skip, no `.pyc` from checks, fork-PR filter, new teardown checks) changed code after
the first real AWS run. This is the second real run, from a fresh clone of the release, on a sandbox account.

| What | Result |
|---|---|
| Deploy (`scripts/deploy.sh`, both stacks, image build and push) | succeeded, about 3 minutes |
| Forged webhook | `401 invalid signature`, no run started |
| Signed alert, fixable bug | `exec-d0e8a14f`: `Ingest -> Investigate -> Route -> Gate -> Fix -> Test -> OpenPr -> Notify`, composite 82, type-check, unit and lint all pass, PR opened ([run log](runs/exec-d0e8a14f.md)) |
| Signed alert, vague and unknown service | `exec-9677880a`: composite 53, `investigation_only`, report-only PR ([run log](runs/exec-9677880a.md)) |
| Duplicate alert | `Ingest -> Accepted -> Dropped`, status `duplicate`, no PR |
| Fork PR event (signed, built by hand) | `200 {"ignored": "pull request from a fork"}`, ledger untouched |
| Real GitHub `pull_request` closed event (webhook delivery 200) | ledger `pending` became `rejected`, history `rejected`: the fork filter reads GitHub's real payload correctly |
| `scripts/teardown.sh` | printed the account, destroyed both stacks, removed the ECR repository and the orphan log group, final inventory `stacks: none`, `ecr: none`, exit 0 |

Not covered this time: real Sentry and Slack (proven in the first run), and the `merged: true` branch of the GitHub event (covered by unit tests; the
run closed the pull request instead, so the demo app's `main` keeps its bug).

The alerts were sent as signed webhooks, built the way Sentry signs them, so Sentry itself was not involved.
