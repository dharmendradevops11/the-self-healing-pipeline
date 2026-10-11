# Appendix F: IAM-control summary

The book's roles, and what the CDK stack (`infra/pipeline_stack.py`), the authoritative source for the exact values,
creates. Run `cdk synth` and read the policies before you deploy.

| Book role | Trust | Here | Notes |
|---|---|---|---|
| `Healer-Ingest-Role` | lambda | `Healer-Ingest-Role` | `logs:FilterLogEvents` on the ECS log groups; rate-limit table; model access for the guardrail classifier |
| `Healer-Investigate-Role` | ecs-tasks | `Healer-Investigate-Role` | `bedrock:InvokeModel` on `anthropic.*` only, state/audit buckets, ledger, GitHub secret |
| `Healer-Remediate-Role` | ecs-tasks | ⏳ not built | The book's role restarts services (`ssm:SendCommand`, `ecs:UpdateService`) on resources tagged `healer-eligible=true`, a **different** tag from `chaos-eligible`. This pipeline's remediation is a pull request, so no such role exists yet. `Healer-Fix-Role` and `Healer-Test-Role` are the stack's own additions |
| `Healer-Audit-Logger-Role` | lambda | each stage role | The stack has no separate audit Lambda; every role is **denied** `s3:DeleteObject` and `s3:DeleteObjectVersion` on the audit bucket |

Not in the table, but required (the book says so): exact S3 prefixes, Bedrock model ARNs, KMS keys for secrets, scoped log-group
ARNs, `iam:PassRole` for task execution roles, and any cross-account `sts:AssumeRole` path. The three standalone policy documents
from Chapter 11 are in [../infra/policies](../infra/policies/README.md); the cross-account trust policy from Chapter 14 is
`cross-account-trust.json`.
