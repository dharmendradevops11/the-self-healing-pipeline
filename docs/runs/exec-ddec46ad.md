# Run `exec-ddec46ad`

Exported 2026-10-09 17:02 local time from region `us-east-1`. Account shown as `<account>`.

| | |
|---|---|
| Step Functions execution | `c0a278a1-a9fd-57ed-90c1-1be2f0130ef0` |
| Status | **FAILED** |
| Started | 16:07:59 |
| Stopped | 16:08:05 |
| Console | https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/v2/executions/details/arn:aws:states:us-east-1:<account>:execution:StateMachine2E01A3A5-J16ZhWEQEldV:c0a278a1-a9fd-57ed-90c1-1be2f0130ef0 |

## 1. Webhook Lambda (the front door)

Log group `SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo`

```
16:07:59.060  {"hop": "webhook->sns", "execution_id": "exec-ddec46ad", "sns_message_id": "30dd132e-9561-5353-819f-706dcc8e9819", "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingPipeline-TriggerTopic92976BC4-IhEQqbgkRKaA", "service": "demo-app", "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)"}
```

## 2. EventBridge Pipe (queue to Step Functions)

Log group `SelfHealingPipeline-PipeLogs8633E6FA-TZkhQ2nzKvyr`. The first event holds the raw SQS record the pipe read.

```
16:07:59.105  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580079105,"executionId":"623bd38a-43ea-45f8-b75a-138f078e50fa","messageType":"ExecutionStarted","logLevel":"INFO","payload":"{\"Records\":[{\"messageId\":\"81d1e484-f35a-4c27-bf9c-5548716b6989\",\"receiptHandle\":\"AQEBEqEC/l81PjdzXGrPwmCedHAjUaMPKf/XekzR5PYR/ykVZ60K1K+z9esrxQcKAJIwh61ScELseXAkd1xAjyrG0On4R2AfzrQ5d3Ge4+UmGdpCFRA8Zfl/CSARD7asAtNI60WZoDJqI79FNmWrOhbe5j38B0dAusay3jlsMk7G0BUx/jI93Y62Y64WjKAoXaKakONaRen4Gefs4u2WrQkLvcM+TKk4nfL0savFB1K/2cmMrvdTwgNrBlJOIBT9XZAay+BG+gYoQwV2XuFNyDcSTZ6Ydbr7N1syau4RkrzadhxNhwzT9ikr6ytWZfbce+5XRPsugqn6ZTZ3Aor9y2LZvPvFvnIR8tGxQVq3U3+d0fv9dIc5w8GZMD1AEsFR82slFOhDkjiIxsY/EWRATHu0GoIcix3OT/k4LZM8shmo9iumbddFwIQoGibRC1aEnVt/\",\"body\":\"{\\\"executionId\\\": \\\"exec-ddec46ad\\\", \\\"incident\\\": {\\\"source\\\": \\\"sentry\\\", \\\"severity\\\": \\\"high\\\", \\\"type\\\": \\\"crash\\\", \\\"title\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)\\\", \\\"stackTrace\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)\\\\nTraceback (most recent call last)\\\\n  File \\\\\\\"src/auth.py\\\\\\\", line 28, in greet\\\\n  File \\\\\\\"src/auth.py\\\\\\\", line 24, in get_display_name\\\", \\\"affectedService\\\": \\\"demo-app\\\", \\\"cloudwatchLogGroup\\\": \\\"/aws/ecs/demo-app\\\", \\\"triggeredAt\\\": \\\"2026-10-09T21:07:40.000000Z\\\", \\\"sentryIssueUrl\\\": \\\"https://sentry.io/organizations/<org>/issues/7784103133/events/ef428867f4614b26b9b8aadbd17cfbcd/\\\", \\\"sentryIssueId\\\": \\\"7784103133\\\"}}\",\"attributes\":{\"ApproximateReceiveCount\":\"1\",\"AWSTraceHeader\":\"Root=1-6ac957ab-212ec8a00c662d201ea3b5ac;Parent=31d541e563218fe4;Sampled=0;Lineage=1:a6e3e63c:0\",\"SentTimestamp\":\"1791580079082\",\"SenderId\":\"AROA3TYMO3BGGTBI3MZUH:AWS-CLOUDCAST\",\"ApproximateFirstReceiveTimestamp\":\"1791580079092\"},\"messageAttributes\":{},\"md5OfBody\":\"7676b1c3377647f41c1c5adfd2b82cea\",\"eventSource\":\"aws:sqs\",\"eventSourceARN\":\"arn:aws:sqs:us-east-1:<account>:SelfHealingPipeline-TriggerQueue434C4AA5-uUkPt3JwJjya\",\"awsRegion\":\"us-east-1\"}]}"}
16:07:59.115  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580079115,"executionId":"623bd38a-43ea-45f8-b75a-138f078e50fa","messageType":"TargetStageEntered","logLevel":"INFO"}
16:07:59.197  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580079197,"executionId":"623bd38a-43ea-45f8-b75a-138f078e50fa","messageType":"TargetStageSucceeded","logLevel":"INFO","payload":""}
16:07:59.197  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580079197,"executionId":"623bd38a-43ea-45f8-b75a-138f078e50fa","messageType":"ExecutionSucceeded","logLevel":"INFO"}
```

## 3. Step Functions: every state, its time, input and output

| State | Started | Seconds |
|---|---|---|
| InputShape | 16:07:59 | 0.0 |
| UnwrapBatch | 16:07:59 | 0.0 |
| Ingest | 16:07:59 | 1.8 |
| NotifyFailureIngest | 16:08:00 | 4.9 |
| FailedIngest | 16:08:05 | - |

### Ingest

Input:

```json
{
  "executionId": "exec-ddec46ad",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:07:40.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784103133/events/ef428867f4614b26b9b8aadbd17cfbcd/",
    "sentryIssueId": "7784103133"
  }
}
```

Output:

```json
{
  "executionId": "exec-ddec46ad",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:07:40.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784103133/events/ef428867f4614b26b9b8aadbd17cfbcd/",
    "sentryIssueId": "7784103133"
  },
  "error": {
    "Error": "ClientError",
    "Cause": "{\"errorMessage\": \"An error occurred (AccessDeniedException) when calling the GetSecretValue operation: User: arn:aws:sts::<account>:assumed-role/Healer-Ingest-Role/SelfHealingPipeline-Ingest4069586C-96sTMKxkqcHq is not authorized to perform: secretsmanager:GetSecretValue on resource: arn:aws:secretsmanager:us-east-1:<account>:secret:self-healing-pipeline/slack-webhook-SyE2kJ because no identity-based policy allows the secretsmanager:GetSecretValue action\", \"errorType\": \"ClientError\", \"requestId\": \"ef409db4-cfbc-4814-b120-9771b844a697\", \"stackTrace\": [\"  File \\\"/var/task/healer/handlers.py\\\", line 170, in ingest_handler\\n    s = services or _services()\\n\", \"  File \\\"/var/task/healer/handlers.py\\\", line 33, in _services\\n    return build_services(_settings())\\n\", \"  File \\\"/var/task/healer/config.py\\\", line 200, in build_services\\n    notifiers.append(SlackNotifier(get_secret(secrets, settings.slack_secret_arn)))\\n\", \"  File \\\"/var/task/healer/guardrails/secrets.py\\\", line 19, in get_secret\\n    value = secrets_client.get_secret_value(SecretId=secret_id)[\\\"SecretString\\\"]\\n\", \"  File \\\"/var/lang/lib/python3.11/site-packages/botocore/client.py\\\", line 606, in _api_call\\n    return self._make_api_call(operation_name, kwargs)\\n\", \"  File \\\"/var/lang/lib/python3.11/site-packages/botocore/context.py\\\", line 123, in wrapper\\n    return func(*args, **kwargs)\\n\", \"  File \\\"/var/lang/lib/python3.11/site-packages/botocore/client.py\\\", line 1094, in _make_api_call\\n    raise error_class(parsed_response, operation_name)\\n\"]}"
  }
}
```

## 4. Lambda logs (full)

### Ingest: function `SelfHealingPipeline-Ingest4069586C-96sTMKxkqcHq`, log group `SelfHealingPipeline-IngestLogs7327CBDC-uNlWWsY2cDq7`

```
16:07:59.657  START RequestId: ef409db4-cfbc-4814-b120-9771b844a697 Version: $LATEST
16:08:00.946  [ERROR] ClientError: An error occurred (AccessDeniedException) when calling the GetSecretValue operation: User: arn:aws:sts::<account>:assumed-role/Healer-Ingest-Role/SelfHealingPipeline-Ingest4069586C-96sTMKxkqcHq is not authorized to perform: secretsmanager:GetSecretValue on resource: arn:aws:secretsmanager:us-east-1:<account>:secret:self-healing-pipeline/slack-webhook-SyE2kJ because no identity-based policy allows the secretsmanager:GetSecretValue action
Traceback (most recent call last):
  File "/var/task/healer/handlers.py", line 170, in ingest_handler
    s = services or _services()
  File "/var/task/healer/handlers.py", line 33, in _services
    return build_services(_settings())
  File "/var/task/healer/config.py", line 200, in build_services
    notifiers.append(SlackNotifier(get_secret(secrets, settings.slack_secret_arn)))
  File "/var/task/healer/guardrails/secrets.py", line 19, in get_secret
    value = secrets_client.get_secret_value(SecretId=secret_id)["SecretString"]
  File "/var/lang/lib/python3.11/site-packages/botocore/client.py", line 606, in _api_call
    return self._make_api_call(operation_name, kwargs)
  File "/var/lang/lib/python3.11/site-packages/botocore/context.py", line 123, in wrapper
    return func(*args, **kwargs)
  File "/var/lang/lib/python3.11/site-packages/botocore/client.py", line 1094, in _make_api_call
    raise error_class(parsed_response, operation_name)
16:08:00.949  END RequestId: ef409db4-cfbc-4814-b120-9771b844a697
16:08:00.949  REPORT RequestId: ef409db4-cfbc-4814-b120-9771b844a697	Duration: 1290.90 ms	Billed Duration: 1499 ms	Memory Size: 512 MB	Max Memory Used: 92 MB	Init Duration: 208.00 ms
```

## 5. Fargate task logs (full) and task details

## 6. Audit trail (S3) and the final state

### `audit/exec-ddec46ad/step_001_failure.json`

```json
{
  "execution_id": "exec-ddec46ad",
  "step_number": 1,
  "timestamp": "2026-10-09T21:08:05.698543+00:00",
  "step_type": "failure",
  "input": {
    "stage": "ingest"
  },
  "output": {
    "error": "{\"errorMessage\": \"An error occurred (AccessDeniedException) when calling the GetSecretValue operation: User: arn:aws:sts::<account>:assumed-role/Healer-Ingest-Role/SelfHealingPipeline-Ingest4069586C-96sTMKxkqcHq is not authorized to perform: secretsmanager:GetSecretValue on resource: arn:aws:secretsmanager:us-east-1:<account>:secret:self-healing-pipeline/slack-webhook-SyE2kJ because no identity-based policy allows the secretsmanager:GetSecretValue action\", \"errorType\": \"ClientError\", \"requ"
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### Final state `pipeline-state/exec-ddec46ad/state.json`

```json
{
  "execution_id": "exec-ddec46ad",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 160740)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:07:40.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784103133/events/ef428867f4614b26b9b8aadbd17cfbcd/",
    "sentryIssueId": "7784103133"
  },
  "status": "escalated",
  "reason": "error in ingest: {\"errorMessage\": \"An error occurred (AccessDeniedException) when calling the GetSecretValue operation: User: arn:aws:sts::<account>:assumed-role/Healer-Ingest-Role/SelfHealingPipeline-Ingest4069586",
  "log_lines": [],
  "diagnosis": null,
  "evidence": null,
  "degraded": [],
  "category": "",
  "history": null,
  "signal": null,
  "composite": null,
  "decision": null,
  "proposal": null,
  "plan_action": "",
  "branch": null,
  "fix_commit": null,
  "tests": null,
  "pr": null,
  "notified": true,
  "review_flags": [],
  "constraint_problems": [],
  "end_to_end_reported": true,
  "audit_keys": [
    "audit/exec-ddec46ad/step_001_failure.json"
  ]
}
```

