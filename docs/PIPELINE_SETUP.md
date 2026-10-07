# 🔧 AWS AI Self-Healing Pipeline

> **Note:** The NOTIFY stage publishes to an SNS topic (AWS Chatbot / email / any subscriber). The `SlackWebhookUrl` CloudFormation parameter is still required by the template but is not used by the current code, so any placeholder value works.

> Autonomous AI-powered backend repair. Detects issues → investigates root cause → generates a fix → runs tests → opens a GitHub PR. **Your team only reviews the PR.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE-PIPELINE-MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)](https://www.typescriptlang.org/)
[![AWS Bedrock](https://img.shields.io/badge/Powered%20by-AWS%20Bedrock-orange)](https://aws.amazon.com/bedrock/)

---

## What It Does

When Sentry detects a crash or your monitoring digest flags an anomaly, this pipeline:

1. **Enriches** — pulls CloudWatch logs and Sentry occurrence count for context
2. **Investigates** — clones your repo, reads the implicated files, asks Claude (via AWS Bedrock) for root cause analysis with a confidence score (0–100)
3. **Fixes** — if confidence ≥ 60, generates a unified diff, applies it, pushes a `healer/` branch
4. **Tests** — runs type-check + unit tests + linting on the changed files
5. **PRs** — opens a GitHub PR with the full investigation report, confidence score, and test results
6. **Notifies** — posts to Slack with the PR link

**Human role: review and merge the PR.** Everything else is automated.

---

## Architecture

```
Sentry webhook ──┐
                 ├──► SNS Topic ──► SQS Queue ──► EventBridge Pipe ──► Step Functions
Monitoring digest┘
                                                            │
                           ┌────────────────────────────────┘
                           ▼
                    ┌─────────────┐
                    │   INGEST    │  Lambda — rate limit, enrich with CW logs
                    └──────┬──────┘
                           │ S3 state bus
                    ┌──────▼──────┐
                    │ INVESTIGATE │  Fargate — clone repo, read files, Bedrock analysis
                    └──────┬──────┘
                           │ confidence score + root cause
                    ┌──────▼──────┐
                    │     FIX     │  Fargate — Bedrock diff generation, git apply, push branch
                    └──────┬──────┘
                           │ healer/ branch
                    ┌──────▼──────┐
                    │    TEST     │  Fargate — type-check, unit tests, lint
                    └──────┬──────┘
                           │ test results
                    ┌──────▼──────┐
                    │     PR      │  Lambda — GitHub PR with full report + healer label
                    └──────┬──────┘
                    ┌──────▼──────┐
                    │   NOTIFY    │  Lambda — Slack notification with PR link
                    └─────────────┘
```

All stages share state via **S3** (`pipeline-state/{executionId}/state.json`). Any stage failure routes to PR + Notify with whatever context was gathered — nothing fails silently.

---

## Key Design Decisions

| Decision | Why |
|----------|-----|
| **S3 as inter-stage bus** | ECS `runTask.sync` doesn't capture stdout — S3 is the only reliable way to pass data between Fargate stages |
| **SNS → SQS → Pipe** | EventBridge Pipes doesn't support SNS as a source; SQS bridges it |
| **AWS Bedrock (not OpenAI)** | No external API keys — Claude runs inside your AWS account |
| **Atomic DynamoDB rate limit** | `UpdateCommand` with `ConditionExpression` prevents concurrent flood events from bypassing the 3/hour limit (no TOCTOU race) |
| **5 scoped IAM roles** | Lambda, TaskRole, TaskExecutionRole, StateMachineRole, PipeRole — `ecs:RunTask` limited to `healer-*` task families only |
| **Secrets at runtime** | GitHub token and Sentry secret fetched from Secrets Manager at invocation — never stored in plaintext Lambda env vars |

---

## Prerequisites

- AWS account with **Bedrock enabled** in your region
- GitHub **Personal Access Token** (fine-grained: `Contents: write` + `Pull requests: write`)
- Sentry account *(optional — can trigger manually via Step Functions)*
- Slack incoming webhook or AWS Chatbot
- Docker, AWS CLI, Node.js 20+

---

## Quick Start

### 1. Install dependencies

```bash
cd infrastructure/healer
npm install
```

### 2. Run tests

```bash
npm test           # 12 tests across 4 suites
npm run type-check # zero TypeScript errors
```

### 3. Build

```bash
npm run build        # Lambda bundles → dist/lambdas/
npm run build:tasks  # Fargate task bundles → dist/tasks/
```

### 4. Create ECR repository

```bash
aws ecr create-repository \
  --repository-name YOUR_PROJECT/healer \
  --region YOUR_REGION
```

### 5. Build & push Docker image

```bash
ECR=YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/YOUR_PROJECT/healer

aws ecr get-login-password --region YOUR_REGION | \
  docker login --username AWS --password-stdin $ECR

docker build -t $ECR:latest infrastructure/healer/
docker push $ECR:latest
```

### 6. Package Lambda zips & upload to S3

```bash
cd infrastructure/healer/dist/lambdas

for f in ingest stage-ingest stage-pr stage-notify; do
  python3 -c "
import zipfile
with zipfile.ZipFile('$f.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    z.write('$f/index.js', 'index.js')
"
  aws s3 cp $f.zip s3://YOUR_BUCKET/healer/lambdas/$f.zip
done
```

### 7. Store secrets in AWS Secrets Manager

```bash
# GitHub Personal Access Token
aws secretsmanager create-secret \
  --name "/YOUR_PROJECT/healer/github-token" \
  --secret-string "ghp_YOUR_TOKEN"

# Sentry HMAC webhook secret (from Sentry → Settings → Integrations → Webhooks)
aws secretsmanager create-secret \
  --name "/YOUR_PROJECT/healer/sentry-webhook-secret" \
  --secret-string "YOUR_SENTRY_HMAC_SECRET"
```

### 8. Deploy the CloudFormation stack

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation/self-healing-pipeline.yaml \
  --stack-name YOUR_PROJECT-self-healing-pipeline \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=YOUR_PROJECT \
    Environment=dev \
    EcsClusterArn="arn:aws:ecs:REGION:ACCOUNT_ID:cluster/YOUR_CLUSTER" \
    SubnetId="subnet-XXXXXXXX" \
    SecurityGroupId="sg-XXXXXXXX" \
    GithubTokenSecretArn="arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:/YOUR_PROJECT/healer/github-token" \
    SentryWebhookSecretArn="arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:/YOUR_PROJECT/healer/sentry-webhook-secret" \
    GithubRepoOwner="YOUR_GITHUB_ORG" \
    GithubRepoName="YOUR_REPO" \
    GithubBaseBranch="main" \
    SlackWebhookUrl="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK" \
    HealerImageUri="ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/YOUR_PROJECT/healer:latest" \
    BedrockModelId="us.anthropic.claude-sonnet-4-6"
```

### 9. Wire Sentry (optional)

```bash
# Get the webhook URL from stack outputs
aws cloudformation describe-stacks \
  --stack-name YOUR_PROJECT-self-healing-pipeline \
  --query 'Stacks[0].Outputs[?OutputKey==`SentryWebhookUrl`].OutputValue' \
  --output text
```

Add this URL in Sentry: **Settings → Integrations → Webhooks → Add webhook**

### 10. Smoke test

```bash
SM_ARN=$(aws cloudformation describe-stacks \
  --stack-name YOUR_PROJECT-self-healing-pipeline \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

aws stepfunctions start-execution \
  --state-machine-arn "$SM_ARN" \
  --name "smoke-test-$(date +%s)" \
  --input '{
    "executionId": "smoke-test-001",
    "event": {
      "source": "manual",
      "severity": "medium",
      "type": "crash",
      "title": "TypeError: Cannot read properties of null",
      "stackTrace": "at processRequest (src/handlers/auth.ts:52:5)",
      "affectedService": "your-api",
      "cloudwatchLogGroup": "/ecs/your-api",
      "triggeredAt": "2026-01-01T00:00:00Z"
    }
  }'
```

Expected: GitHub PR created in ~15–20 minutes with the `healer` label, Slack notification received.

---

## Configuration

### Customise the file path allowlist

Edit `infrastructure/healer/tasks/fix/run.ts` to match your project structure:

```typescript
const SAFE_PATH_PREFIXES = [
  "src/",
  "lib/",
  "packages/",
  // Add your source directories
];

const FORBIDDEN_PATH_PATTERNS = [
  /^infrastructure\//,
  /^\.github\//,
  /migrations\//,
  /^Dockerfile/,
  /\.ya?ml$/,
  /\.sh$/,
  // Add any other paths you never want auto-patched
];
```

### Customise the test runner

Edit `infrastructure/healer/tasks/test/run.ts` to match your test commands:

```typescript
const typeCheck = runCheck("npm", ["run", "type-check"], repoPath);
const unitTests = runCheck("npm", ["test", "--", "--testPathPattern", testPattern], repoPath);
const lint = runCheck("npx", ["eslint", "--max-warnings=0", ...tsxFiles], repoPath);
```

### Rate limiting

Default: 3 executions/hour/service (configurable in `lambdas/shared/dynamodb-client.ts`):

```typescript
const MAX_PER_HOUR = 3;
```

---

## How the Bedrock Prompts Work

**INVESTIGATE stage** — asks Claude to:
- Read the stack trace and implicated source files
- Identify the root cause with a confidence score (0–100)
- List affected files and suggest a fix strategy
- Return structured JSON for the FIX stage to act on

**FIX stage** — asks Claude to:
- Generate a minimal unified diff
- Limit changes to the identified files only
- Return `"investigation-only"` if confidence < 60 or no safe fix exists

Both prompts include **prompt injection defenses** — user-controlled data (Sentry titles, stack traces, CloudWatch logs) is sanitized before being embedded.

---

## Cost Estimate

| Component | Per execution | Monthly (10 incidents) |
|-----------|--------------|----------------------|
| Bedrock Claude Sonnet (2 calls) | ~$0.50–2.00 | ~$5–20 |
| Fargate (3 tasks × ~20 min) | ~$0.15 | ~$1.50 |
| Step Functions | < $0.01 | < $0.10 |
| Lambda, S3, DynamoDB | < $0.01 | < $0.10 |
| **Total** | **~$0.70–2.20** | **~$7–22** |

The rate limit (3/hour/service) prevents runaway Bedrock spend on noisy alerts.

---

## Security

| Control | Implementation |
|---------|---------------|
| Sentry webhook validation | HMAC-SHA256 via `crypto.timingSafeEqual` — rejects if secret not configured |
| Prompt injection defense | `sanitizeForPrompt()` strips injection phrases from all Sentry/CW data |
| File path allowlist | Server-side validation blocks diffs to `infrastructure/`, `.github/`, migrations, YAML, shell scripts |
| Secrets at runtime | GitHub PAT and Sentry secret fetched from Secrets Manager at invocation — not in Lambda env vars |
| Scoped IAM | 5 roles with least-privilege; `ecs:RunTask` limited to `healer-*` task definitions only |
| Rate limiting | Atomic `UpdateCommand` with `ConditionExpression` — no TOCTOU race on concurrent alerts |

---

## Extending the Pipeline

### Add a new trigger source

1. Publish to the `{ProjectName}-{Environment}-healer-trigger` SNS topic with this payload:

```json
{
  "executionId": "unique-id",
  "event": {
    "source": "your-source",
    "severity": "high",
    "type": "crash",
    "title": "Error description",
    "stackTrace": "at func (src/file.ts:10:5)",
    "affectedService": "your-service",
    "cloudwatchLogGroup": "/ecs/your-service",
    "triggeredAt": "ISO8601 timestamp"
  }
}
```

### Add a new notification channel

Edit `lambdas/stage-notify/index.ts` — it publishes to SNS, which routes to AWS Chatbot/Slack. You can add any SNS subscriber (email, PagerDuty, Teams, etc.).

### Change the AI model

Update `BedrockModelId` parameter in the CloudFormation deploy. Any Claude model available in your region works. Available cross-region inference profiles:

```bash
aws bedrock list-inference-profiles --region us-east-2 \
  --query 'inferenceProfileSummaries[?contains(inferenceProfileId,`claude`)].inferenceProfileId' \
  --output text
```

---

## Troubleshooting

**Pipeline times out on Investigate/Fix/Test stages**  
→ These are Fargate tasks that install pnpm + clone your repo. First run takes 10–15 min. Check your subnet has a NAT gateway for internet access.

**"corrupt patch at line N"**  
→ Bedrock generated a diff that doesn't apply cleanly. The pipeline falls back to an investigation-only PR with the root cause analysis — still useful.

**No Slack notification**  
→ Check `stage-notify` Lambda CloudWatch logs (`/aws/lambda/{ProjectName}-{Environment}-healer-stage-notify`). The SNS → Chatbot requires `MessageStructure: "json"` with the custom card format — see `lambdas/stage-notify/index.ts`.

**"Reference already exists" on PR creation**  
→ A healer branch with the same name exists. The branch name includes a 6-char suffix from `executionId` — if you re-run with the same ID, increment it.

---

## Contributing

PRs welcome! Key areas:

- **Better patch quality** — multi-file diffs, context-aware patching
- **More languages** — currently optimised for TypeScript/Node.js; Python, Go support welcome
- **More triggers** — Datadog, PagerDuty, CloudWatch Alarms integrations
- **GitLab support** — alongside GitHub

---

## License

MIT — see [LICENSE-PIPELINE-MIT](../LICENSE-PIPELINE-MIT)
