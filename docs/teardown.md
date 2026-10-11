# Teardown (Chapter 17)

```bash
AWS_PROFILE=... AWS_REGION=us-east-1 ./scripts/teardown.sh
```

It follows the book's order:

1. `cdk destroy --all -f` removes Lambdas, ECS, Step Functions, queues and security groups.
2. Empties and deletes the ECR repository `self-healing-pipeline/healer-agent`. (`batch-delete-image` fails on an empty
   repository, so the script tolerates that.)
3. Empties and deletes the **state** bucket. It is disposable.
4. **Checks the audit bucket before touching it.** With Object Lock, objects inside their retention window cannot be
   deleted, and the bucket cannot be removed while they exist. GOVERNANCE mode lets a principal with
   `s3:BypassGovernanceRetention` override that. The fact that you can is not a reason to. Verify the mode and the dates,
   wait for expiry, export the records first if you need them.
   ```bash
   aws s3api get-object-lock-configuration --bucket self-healing-pipeline-audit-logs-ACCOUNT
   aws s3api get-bucket-versioning        --bucket self-healing-pipeline-audit-logs-ACCOUNT
   ```
5. Secrets are yours to delete, because the stack never created them:
   `aws secretsmanager delete-secret --secret-id self-healing-pipeline/github-token --recovery-window-in-days 7`.
   Revoke the GitHub token as well.

By default (`healer:audit_object_lock=false`) everything, including the audit bucket, is destroyed cleanly. That default is
for experiments. Turn Object Lock on for anything real.

## What the stack does not remove (found by checking an account after a real teardown, 2026-10-09)

- **Two log groups** named `/aws/lambda/SelfHealingState-CustomS3AutoDelete…`. CDK's bucket-emptying helper functions create them at run time, so
  the stack does not own them. `scripts/teardown.sh` now deletes them.
- **Anything you created by hand for testing:** a log group such as `/aws/ecs/<service>` from `test_flows.py seed-logs`, the webhook secrets, and the
  repository webhook in GitHub.

- **The CDK bootstrap** (`CDKToolkit`: an assets bucket and an image repository). It is shared by every CDK app in the account
  and costs about a cent a month, so it stays so the next deploy is quick. To remove it:
  `aws cloudformation delete-stack --stack-name CDKToolkit`, after emptying its bucket and repository.
- **Secrets you created**, and **the repository webhook** you added in GitHub (Settings, Webhooks).
- **Pull requests the pipeline opened.** They live in your repository.

This was run for real: after `scripts/teardown.sh` the account held no stacks, tables, clusters, functions, state machines,
log groups or pipeline buckets.
