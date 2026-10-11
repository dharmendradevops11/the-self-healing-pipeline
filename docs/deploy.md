# Deploy to AWS (Chapter 17)

Only after you have run it locally until you are bored. Deploying bills you. [teardown.md](teardown.md) takes it to zero.

## Prerequisites (the book's "real list")

- An AWS account with **Bedrock model access** granted (a separate enablement; it can take a day or two). Check
  your quotas for invocations and tokens per minute.
- A **fine-grained** GitHub token, not a classic one: *Contents: Read and write*, *Pull requests: Read and write*,
  *Metadata: Read-only*, nothing at account level, 90-day expiry. Use a machine user.
- Docker, the AWS CLI, Python 3.11, Node 20 (for the CDK CLI). Run `aws sts get-caller-identity` before anything.
- A billing alarm.

## Secrets: store them before anything else

Read them into variables so they never reach your shell history. The names and the JSON shape are the book's.

```bash
read -sp "GitHub token: " GITHUB_TOKEN; echo ""
aws secretsmanager create-secret --name self-healing-pipeline/github-token \
  --secret-string "{\"token\":\"$GITHUB_TOKEN\"}" --region us-east-1
read -sp "Webhook signing secret: " WH; echo ""
aws secretsmanager create-secret --name self-healing-pipeline/webhook \
  --secret-string "$WH" --region us-east-1
```

Store JSON, not a bare string: you will want to add metadata later. The stack takes the **ARNs** (it never sees values).
The Lambdas and tasks read a secret at the moment they use it, never from an environment variable.

## Deploy

```bash
./scripts/deploy.sh \
  -c healer:github_repo_url=https://github.com/YOU/YOUR-REPO \
  -c healer:github_secret_arn=arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:self-healing-pipeline/github-token-XXXX \
  -c healer:webhook_secret_arn=arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:self-healing-pipeline/webhook-XXXX \
  -c healer:phase=shadow \
  -c healer:bedrock_model_id=YOUR-SUPPORTED-MODEL-ID
```

It deploys the state stack (buckets, tables, ECR, topic), builds and pushes the image, then deploys the pipeline
(VPC, Fargate tasks, Lambdas, queue, pipe, state machine, API). Use a commit SHA for `healer:image_tag` in production,
not `latest`.

| Context key | Default | Book |
|---|---|---|
| `healer:phase` | `supervised` | shadow, supervised, autonomous (Ch. 17) |
| `healer:confidence_threshold` | 60 | "a CloudFormation parameter" (Ch. 16, 18) |
| `healer:log_lines` | 20 | last 20 CloudWatch lines (Ch. 2) |
| `healer:max_daily_prs` | 3 | "three PRs a day at first" (Ch. 17) |
| `healer:bedrock_model_id` | a current Sonnet | keep the ID in configuration (App. E) |
| `healer:audit_object_lock` | false | Object Lock GOVERNANCE on the audit bucket (Ch. 8, 11) |
| `healer:audit_retention_days` | 90 | audit retention, then lifecycle pruning (App. H) |
| `healer:service_registry` | `{}` | blast-radius registry (Ch. 9) |
| `healer:billing_alarm_usd` | 0 (off) | "set a billing alarm" (Ch. 17); needs billing alerts enabled, us-east-1 |
| `healer:bedrock_regions` | current region | comma separated; requests round-robin across them (Ch. 14) |
| `healer:bedrock_fallback_model_id` | none | the model asked when the primary cannot answer (Ch. 17) |
| `healer:bedrock_quick_model_id` | none | a small model for the injection classifier (Ch. 17 "quick analysis") |
| `healer:github_webhook_secret_arn` | none | signs GitHub `pull_request` events so reviewer decisions reach the ledger |
| `healer:slack_secret_arn`, `healer:notification_email` | none | where results and escalations go |

Point your Sentry project's webhook at the `WebhookUrl` output. Start in **shadow** mode: the pipeline analyses every
failure and writes what it *would* have done. See [shadow-mode.md](shadow-mode.md).

## Differences from the printed chapter

- The book builds a `webhook-receiver` container. The stack deploys the webhook as a zip Lambda that CDK bundles
  (no 50 MB problem: the handler needs only boto3 and PyYAML). The Dockerfile is there if you prefer the image route.
- The book's `build.sh` builds Lambda dependencies with `--platform manylinux2014_x86_64`. CDK bundling does the
  equivalent for this stack.

## Close the learning loop: the GitHub webhook

Without it every ledger row stays `pending`, the history input to the confidence score never activates, and the pipeline
never learns what your reviewers think (Chapter 2, Stage 4; Chapter 9, "The Ledger").

1. Create a secret holding a random string and pass its ARN as `healer:github_webhook_secret_arn`.
2. In the repository's *Settings, Webhooks*, add the `GitHubWebhookUrl` output, content type `application/json`, the same
   secret, and the *Pull requests* event only.
3. When a `healer/` pull request closes, the ledger records `approved` (merged), `modified` (merged after extra commits) or
   `rejected` (closed). A rejection keeps the reason ticked in [the PR template](templates/pull_request_template.md).

Investigation-only pull requests are ignored: closing a report says nothing about whether the diagnosis was right.
