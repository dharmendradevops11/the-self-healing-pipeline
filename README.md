# The Self-Healing Pipeline

Companion repository for **The Self-Healing Pipeline: How I Taught My CI/CD Pipeline to Fix Itself at 2 AM** by Dharmendra Ahuja.

It has two parts: a **deployable pipeline** you can run in your own AWS account, and **every code example from the book**, organized by chapter.

## 1. Run the pipeline

Sentry alert → SNS → SQS → EventBridge Pipe → Step Functions → ingest, investigate, fix, test, open a GitHub PR, notify. A human reviews the PR.

- Code: [`infrastructure/healer/`](infrastructure/healer/) (TypeScript Lambdas and Fargate tasks) and [`infrastructure/cloudformation/self-healing-pipeline.yaml`](infrastructure/cloudformation/self-healing-pipeline.yaml)
- Step-by-step setup, prerequisites and troubleshooting: [docs/PIPELINE_SETUP.md](docs/PIPELINE_SETUP.md)

```bash
cd infrastructure/healer
npm install
npm run type-check && npm test   # 12 tests, 4 suites
npm run build && npm run build:tasks
```

### What you change to make it yours

All setup is configuration. Nothing in the code needs editing for a standard deployment.

| Setting | Where | Notes |
|---|---|---|
| `GithubRepoOwner`, `GithubRepoName`, `GithubBaseBranch` | CloudFormation parameters | The repository you want healed |
| `GithubTokenSecretArn`, `SentryAuthTokenSecretArn`, `SentryWebhookSecretArn` | CloudFormation parameters | Secrets Manager ARNs. Secrets are fetched at runtime, never stored in the template |
| `EcsClusterArn`, `SubnetId`, `SecurityGroupId`, `HealerImageUri` | CloudFormation parameters | Your network and the ECR image you push |
| `BedrockModelId`, `BedrockRegion` | CloudFormation parameters | Check that the model is enabled in your account and not retired |
| `SlackWebhookUrl` | CloudFormation parameter | Required by the template, unused by current code (see setup doc) |
| Git author email | `infrastructure/healer/tasks/shared/git-client.ts` | Placeholder `healer@your-domain.com` |

Test the pipeline in a non-production AWS account first. It can push branches and open pull requests against the repository you point it at.

## 2. Book examples

- [`chapters/`](chapters/) mirrors the book: one folder per chapter, every code listing in reading order, and a README mapping each file to its section. Most are excerpts that illustrate one idea.
- [`companion_code/`](companion_code/) holds the standalone Python reference implementations indexed in Appendix D (anomaly detection, rate limiting, decision tree, signature validation, failure observer, secret scrubbing).
- [`.manuscript_changelog.md`](.manuscript_changelog.md) tracks revisions.

The Python examples are conceptual companions to the pipeline stages. They are not imported by the TypeScript pipeline.

All account IDs, ARNs, tokens and endpoints in this repository are placeholders.

## Licenses

- Book examples (`chapters/`, `companion_code/`): Apache License 2.0, see [LICENSE](LICENSE).
- Pipeline code (`infrastructure/`): MIT, Copyright (c) 2026 Abhishek Sahu, see [LICENSE-PIPELINE-MIT](LICENSE-PIPELINE-MIT).

Everything is provided for illustrative and reference purposes, without warranty. Review and test in a secure staging environment before production use. Corrections and issues: use this repository's issue tracker.
