# Runbook: the five failures that actually happen (Chapter 14)

Copy-paste commands, not theory. Region `us-east-1`; add `--profile` as needed.

## 1. Bedrock throttling
Symptom: Investigate/Fix tasks fail with `ThrottlingException`; Step Functions executions end in `NotifyFailure`.
```bash
aws service-quotas list-service-quotas --service-code bedrock --region us-east-1 | head -40
aws cloudwatch get-metric-statistics --namespace AWS/Bedrock --metric-name InvocationThrottles \
  --start-time $(date -u -v-1H +%FT%TZ) --end-time $(date -u +%FT%TZ) --period 300 --statistics Sum
```
Lower `healer:max_daily_prs`/the hourly limit, request a quota increase, or switch `healer:bedrock_model_id`. The rate limiter
exists so a flood does not become a throttle storm.

## 2. IAM errors
Symptom: `AccessDeniedException` in a stage's log group. Find which role: Lambda functions are `Healer-Ingest-Role` and the
generated roles; tasks are `Healer-Investigate-Role`, `Healer-Fix-Role`, `Healer-Test-Role`.
```bash
aws logs filter-log-events --log-group-name /aws/lambda/<function> --filter-pattern AccessDenied --max-items 20
```
For `GetSecretValue`, suspect KMS first ([troubleshooting.md](troubleshooting.md)). Never fix by widening to `*`.

## 3. SQS backlog
```bash
aws sqs get-queue-attributes --queue-url <queue-url> --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
aws sqs get-queue-attributes --queue-url <dlq-url>   --attribute-names ApproximateNumberOfMessages
```
Messages in the DLQ failed three deliveries: read one, fix the cause, redrive (`aws sqs start-message-move-task`).

## 4. ECS task out of memory
Symptom: Fix or Test task exits 137. The Test task runs your repository's own checks and is the usual culprit.
```bash
aws ecs list-tasks --cluster <cluster> --desired-status STOPPED
aws ecs describe-tasks --cluster <cluster> --tasks <arn> --query 'tasks[].containers[].{reason:reason,exit:exitCode}'
```
Raise the memory in `infra/pipeline_stack.py` (`agent("Test", "test", 2048, 4096, …)`) and redeploy.

## 5. Cross-account assume-role failures
Only if you run the pipeline across accounts (Chapter 14). The target account's trust policy must name the source role and the
source role must be allowed `sts:AssumeRole`; both halves, with an external ID.
```bash
aws sts assume-role --role-arn <target-role> --role-session-name test --external-id <id>
```
Test the handshake by hand before wiring it in.
