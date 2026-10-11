# Tested on real AWS (2026-10-09)

Sandbox account, us-east-1, Claude Sonnet 4.5 through Bedrock, a private demo repository with one deliberate bug. Deployed with
`cdk deploy`, exercised, then torn down with `scripts/teardown.sh`. Cost: well under $1.

## What ran

| Scenario | Result |
|---|---|
| Signed Sentry webhook, forged and genuine | forged request rejected (401), genuine accepted (202) |
| Webhook to queue to pipe to state machine | all seven stages ran |
| Fix path | INGEST, INVESTIGATE, ROUTE, FIX, TEST, PR, NOTIFY; a draft or ready PR with the reviewer packet |
| Reviewer closes a PR | ledger and history record `rejected` |
| Reviewer merges a PR | ledger and history record `approved` |
| Payments-style service (critical blast radius) | `investigation_only`, a report-only PR holding just `HEALER_REPORT.md`, critical tier |
| Vague alert | composite 58, `investigation_only`, report-only PR, hallucinated file flagged |
| Shadow mode | decision recorded in the audit bucket, no branch, no PR |
| Daily PR cap | the fourth PR of the day was refused |
| Teardown | stacks, tables, buckets, image repository, functions and log groups gone |

## What only real AWS could find

Each of these passed every local test, and each is now fixed and covered by a test.

1. The state machine passed the literal string `"$"` to the first Lambda instead of the execution input.
2. A crash before any state was saved made the failure notice crash too.
3. INVESTIGATE could not query the incident history table.
4. FIX could not publish to the notification topic.
5. Claude answered with diffs that had bare `---` / `+++` headers, so `git apply` failed. A diff without a
   `diff --git` line could also slip past the allowlist cross-check.
6. The Lambda runtime has no `requests` package.
7. EventBridge Pipes hands Step Functions a one-item array, not an object.
8. The report-only PR tried to clone with git inside a Lambda, which has none.
9. Shadow mode wrote to the default ledger table name instead of the deployed one.

Also learned: `cdk.json` runs `python app.py`, so the virtual environment must be on `PATH`; and `-c` flags must reach
`cdk` as separate arguments (a shell that does not split a variable silently deploys the defaults).
