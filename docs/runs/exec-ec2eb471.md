# Run `exec-ec2eb471`

Exported 2026-10-09 16:14 local time from region `us-east-1`. Account shown as `<account>`.

| | |
|---|---|
| Step Functions execution | `1212ae5e-d0c1-5a34-a3aa-cd1d8a4ddf6f` |
| Status | **SUCCEEDED** |
| Started | 16:10:52 |
| Stopped | 16:13:48 |
| Console | https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/v2/executions/details/arn:aws:states:us-east-1:<account>:execution:StateMachine2E01A3A5-J16ZhWEQEldV:1212ae5e-d0c1-5a34-a3aa-cd1d8a4ddf6f |

## 1. Webhook Lambda (the front door)

Log group `SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo`

```
16:10:52.540  {"hop": "webhook->sns", "execution_id": "exec-ec2eb471", "sns_message_id": "0c6ee09c-a1bb-52be-a1f5-83dffb2752fa", "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingPipeline-TriggerTopic92976BC4-IhEQqbgkRKaA", "service": "demo-app", "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)"}
```

## 2. EventBridge Pipe (queue to Step Functions)

Log group `SelfHealingPipeline-PipeLogs8633E6FA-TZkhQ2nzKvyr`. The first event holds the raw SQS record the pipe read.

```
16:10:52.577  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580252577,"executionId":"df6fdd85-8552-404a-904c-4cc66b768756","messageType":"ExecutionStarted","logLevel":"INFO","payload":"{\"Records\":[{\"messageId\":\"22b6c027-c317-415b-9854-f09be8647a31\",\"receiptHandle\":\"AQEBJlU8aL9m88K2k+f1Rnsi55KbYmdORP2f/AE3W6yN5zZVJvhiU/LRMp/HlmcJmmP4q8ZZPV7b7PgxX4u+ymEuQwEyHqG8fYktDbTD5eKdyVHgEkOGgxpVs+GfUvawWJ4LupDMm6HbNMEF+w1Wk+9WUdCrpc5WgZVdJss1hmmCTaZbEAGo2XtjM98f1e0lThTcKTmZZ0/fV52ShE0+HYDpCL4+cG+U7Sm0puK3SX6BktWJ6lrxZK+a2ptovkrNv/8HdntSg4Ub3tNmmPswELRJk5LCqAApVgwwrvBn3XEEphSdB942a6HwxD8PanXBGzeovu1HLP0cX1WsMFg6om9C6CXhPV8IKrNeB6n9z+TnO4XE88ick0CDlGCiHgpgFbD1+fI2k7abMVgHUneeeN1HLo+whhTraBgVH1ENJ59CawDvx/54WL97RUc6+EvKPsP6\",\"body\":\"{\\\"executionId\\\": \\\"exec-ec2eb471\\\", \\\"incident\\\": {\\\"source\\\": \\\"sentry\\\", \\\"severity\\\": \\\"high\\\", \\\"type\\\": \\\"crash\\\", \\\"title\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\\\", \\\"stackTrace\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\\\\nTraceback (most recent call last)\\\\n  File \\\\\\\"src/auth.py\\\\\\\", line 28, in greet\\\\n  File \\\\\\\"src/auth.py\\\\\\\", line 24, in get_display_name\\\", \\\"affectedService\\\": \\\"demo-app\\\", \\\"cloudwatchLogGroup\\\": \\\"/aws/ecs/demo-app\\\", \\\"triggeredAt\\\": \\\"2026-10-09T21:10:29.000000Z\\\", \\\"sentryIssueUrl\\\": \\\"https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/\\\", \\\"sentryIssueId\\\": \\\"7784106874\\\"}}\",\"attributes\":{\"ApproximateReceiveCount\":\"1\",\"AWSTraceHeader\":\"Root=1-6ac95859-4be1f56c42edcbd91678dd10;Parent=130362359310abda;Sampled=0;Lineage=1:a6e3e63c:0\",\"SentTimestamp\":\"1791580252559\",\"SenderId\":\"AROA3TYMO3BGGTBI3MZUH:AWS-CLOUDCAST\",\"ApproximateFirstReceiveTimestamp\":\"1791580252563\"},\"messageAttributes\":{},\"md5OfBody\":\"d23b236da5d2e0a6a7d1f0dc541f4475\",\"eventSource\":\"aws:sqs\",\"eventSourceARN\":\"arn:aws:sqs:us-east-1:<account>:SelfHealingPipeline-TriggerQueue434C4AA5-uUkPt3JwJjya\",\"awsRegion\":\"us-east-1\"}]}"}
16:10:52.590  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580252590,"executionId":"df6fdd85-8552-404a-904c-4cc66b768756","messageType":"TargetStageEntered","logLevel":"INFO"}
16:10:52.672  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580252672,"executionId":"df6fdd85-8552-404a-904c-4cc66b768756","messageType":"ExecutionSucceeded","logLevel":"INFO"}
16:10:52.672  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791580252672,"executionId":"df6fdd85-8552-404a-904c-4cc66b768756","messageType":"TargetStageSucceeded","logLevel":"INFO","payload":""}
```

## 3. Step Functions: every state, its time, input and output

| State | Started | Seconds |
|---|---|---|
| InputShape | 16:10:52 | 0.0 |
| UnwrapBatch | 16:10:52 | 0.0 |
| Ingest | 16:10:52 | 4.4 |
| Accepted | 16:10:57 | 0.0 |
| Investigate | 16:10:57 | 51.3 |
| Route | 16:11:48 | 4.0 |
| Gate | 16:11:52 | 0.0 |
| Fix | 16:11:52 | 56.3 |
| RouteAfterFix | 16:12:48 | 0.3 |
| FixOutcome | 16:12:48 | 0.0 |
| Test | 16:12:48 | 48.7 |
| OpenPr | 16:13:37 | 6.8 |
| Notify | 16:13:44 | 4.4 |
| PullRequestOpened | 16:13:48 | 0.0 |

### Ingest

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  }
}
```

### Investigate

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  }
}
```

### Route

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### Fix

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### RouteAfterFix

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### Test

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### OpenPr

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### Notify

Input:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874"
  },
  "ingest": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-ec2eb471",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

## 4. Lambda logs (full)

### Ingest: function `SelfHealingPipeline-Ingest4069586C-96sTMKxkqcHq`, log group `SelfHealingPipeline-IngestLogs7327CBDC-uNlWWsY2cDq7`

```
16:10:53.118  START RequestId: f624e6c2-f635-4fb3-8210-83fb64cc0e13 Version: $LATEST
16:10:56.953  {"execution_id": "exec-ec2eb471", "step": "ingest", "confidence": null, "output": {"outcome": "accepted"}}
16:10:56.953  {"_aws": {"Timestamp": 1791580256953, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 2.195, "execution_id": "exec-ec2eb471", "Stage": "ingest"}
16:10:57.037  END RequestId: f624e6c2-f635-4fb3-8210-83fb64cc0e13
16:10:57.037  REPORT RequestId: f624e6c2-f635-4fb3-8210-83fb64cc0e13	Duration: 3918.33 ms	Billed Duration: 4131 ms	Memory Size: 512 MB	Max Memory Used: 109 MB	Init Duration: 211.76 ms
```

### Route: function `SelfHealingPipeline-RouteA67450D2-mzwTqL6g4d5J`, log group `SelfHealingPipeline-RouteLogs174AF25A-hN541QyQ5Bpa`

```
16:11:48.761  START RequestId: a9f7ed85-e580-40e6-9989-ce993bdbc19c Version: $LATEST
16:11:52.326  END RequestId: a9f7ed85-e580-40e6-9989-ce993bdbc19c
16:11:52.326  REPORT RequestId: a9f7ed85-e580-40e6-9989-ce993bdbc19c	Duration: 3564.03 ms	Billed Duration: 3780 ms	Memory Size: 256 MB	Max Memory Used: 106 MB	Init Duration: 215.09 ms
```

### RouteAfterFix: function `SelfHealingPipeline-RouteA67450D2-mzwTqL6g4d5J`, log group `SelfHealingPipeline-RouteLogs174AF25A-hN541QyQ5Bpa`

```
16:12:48.821  START RequestId: 325471c7-6c72-432e-ae06-e5445d596200 Version: $LATEST
16:12:48.944  END RequestId: 325471c7-6c72-432e-ae06-e5445d596200
16:12:48.945  REPORT RequestId: 325471c7-6c72-432e-ae06-e5445d596200	Duration: 122.02 ms	Billed Duration: 123 ms	Memory Size: 256 MB	Max Memory Used: 106 MB
```

### OpenPr: function `SelfHealingPipeline-OpenPr92F50AD2-i5GWz4JCrZVL`, log group `SelfHealingPipeline-OpenPrLogs4AF57F65-UpFmCDzo2b9E`

```
16:13:38.135  START RequestId: fff13c5b-3273-43ec-9718-67ae157ded2a Version: $LATEST
16:13:44.348  {"execution_id": "exec-ec2eb471", "step": "pr", "confidence": 91, "output": {"pr": "https://github.com/dharmendradevops11/healer-demo-app/pull/19", "labels": ["healer", "healer: auto-fix-pr", "healer: blast-radius-medium", "healer: human-review"]}}
16:13:44.403  {"_aws": {"Timestamp": 1791580424403, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 4.557, "execution_id": "exec-ec2eb471", "Stage": "pr"}
16:13:44.403  {"_aws": {"Timestamp": 1791580424403, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Outcome"]], "Metrics": [{"Name": "EndToEndSeconds", "Unit": "Seconds"}]}]}, "EndToEndSeconds": 195.4, "execution_id": "exec-ec2eb471", "Outcome": "pr_opened"}
16:13:44.447  END RequestId: fff13c5b-3273-43ec-9718-67ae157ded2a
16:13:44.447  REPORT RequestId: fff13c5b-3273-43ec-9718-67ae157ded2a	Duration: 6310.77 ms	Billed Duration: 6480 ms	Memory Size: 512 MB	Max Memory Used: 109 MB	Init Duration: 168.51 ms
```

### Notify: function `SelfHealingPipeline-Notify29C25B1B-waClKV3bDfn2`, log group `SelfHealingPipeline-NotifyLogsC0ABC89F-qVKu4VXhoO6g`

```
16:13:44.975  START RequestId: c4947dae-ce11-4c6a-a00f-d86d24d5e2c3 Version: $LATEST
16:13:48.552  {"hop": "notify->sns", "sns_message_id": "3c3cbd25-0ced-54b2-aa03-de6657a1f7bf", "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingState-NotificationTopicEB7A0DF1-ZxzTplsPy47u", "subject": "[INFO] [Healer] demo-app: Fix ready (91/100)", "attributes": {"escalationTier": "informational", "page": "False", "channel": "slack", "fixAction": "auto_fix_pr"}, "message": "Self-Healer: Fix ready\nEscalation: INFO -> unassigned via slack (page: no)\nRouting: high confidence x medium blast radius -> auto_fix_pr\nService: demo-app\nIssue: AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nRoot cause: In src/auth.py line 24, the get_display_name() function attempts to access session.user.profile.name without checking if profile is None. When first-time OAuth users log in, they have no profile yet (profile=None), causing an AttributeError when trying to access the 'name' attribute on NoneType.\nConfidence: 91/100\nHuman review required: unowned service: it has no named team or on-call rotation in the registry\nHuman review required: new failure pattern: the ledger has too little history for this category\nPR: https://github.com/dharmendradevops11/healer-demo-app/pull/19"}
16:13:48.820  {"hop": "notify->slack", "status": 200, "subject": "[INFO] [Healer] demo-app: Fix ready (91/100)"}
16:13:48.820  {"_aws": {"Timestamp": 1791580428820, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 0.378, "execution_id": "exec-ec2eb471", "Stage": "notify"}
16:13:48.879  END RequestId: c4947dae-ce11-4c6a-a00f-d86d24d5e2c3
16:13:48.880  REPORT RequestId: c4947dae-ce11-4c6a-a00f-d86d24d5e2c3	Duration: 3903.61 ms	Billed Duration: 4094 ms	Memory Size: 256 MB	Max Memory Used: 108 MB	Init Duration: 190.02 ms
```

## 5. Fargate task logs (full) and task details

### Investigate: task `293361b257144ba4adc2f490fa0e2251`, stream `investigate/healer-investigate/293361b257144ba4adc2f490fa0e2251`

CPU 1024 / memory 2048 MB, exit code **0**, started 16:11:16, stopped 16:11:47, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-sjN1cxd3l54G/tasks/293361b257144ba4adc2f490fa0e2251/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`, stream above.

```
16:11:23.607  {"execution_id": "exec-ec2eb471", "step": "investigate", "confidence": 91, "output": {"root_cause": "In src/auth.py line 24, the get_display_name() function attempts to access session.user.profile.name without checking if profile is None. When first-time OAuth users log in, they have no profile yet (... [296 chars]", "model_certainty": 95, "signal": 1.0, "history": null, "composite": 91, "decision": {"composite_confidence": 91, "band": "high", "blast_radius": {"affected_services": 0, "estimated_users": 0, "sensitive_data_at_risk": false, "tier": "medium"}, "tier": "informational", "fix_action": "auto_fix_pr", "recipient": "unassigned", "page": false, "channel": "slack", "owner": "unassigned"}}}
16:11:23.607  {"_aws": {"Timestamp": 1791580283607, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 6.596, "execution_id": "exec-ec2eb471", "Stage": "investigate"}
16:11:23.695  [investigate] execution exec-ec2eb471: status=running
```

### Fix: task `b5c2211b894243cf93e683befc828182`, stream `fix/healer-fix/b5c2211b894243cf93e683befc828182`

CPU 1024 / memory 2048 MB, exit code **0**, started 16:12:15, stopped 16:12:47, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-sjN1cxd3l54G/tasks/b5c2211b894243cf93e683befc828182/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`, stream above.

```
16:12:21.417  {"execution_id": "exec-ec2eb471", "step": "fix", "confidence": null, "output": {"type": "code-fix", "files": ["src/auth.py"]}}
16:12:22.443  {"execution_id": "exec-ec2eb471", "step": "remediate", "confidence": null, "output": {"applied": true, "branch": "healer/2026-10-09-fix-src-auth-py-2eb471"}}
16:12:22.446  {"_aws": {"Timestamp": 1791580342445, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 6.429, "execution_id": "exec-ec2eb471", "Stage": "fix"}
16:12:22.529  [fix] execution exec-ec2eb471: status=running
```

### Test: task `b0952d7600af4acabf7a4894be6a2a96`, stream `test/healer-test/b0952d7600af4acabf7a4894be6a2a96`

CPU 2048 / memory 4096 MB, exit code **0**, started 16:13:09, stopped 16:13:36, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-sjN1cxd3l54G/tasks/b0952d7600af4acabf7a4894be6a2a96/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`, stream above.

```
16:13:11.233  [test:type_check] pass
16:13:11.234  Success: no issues found in 2 source files
16:13:11.234  [test:unit] pass
16:13:11.234  ...                                                                      [100%]
16:13:11.234  3 passed in 0.01s
16:13:11.234  [test:lint] pass
16:13:11.234  All checks passed!
16:13:11.276  {"execution_id": "exec-ec2eb471", "step": "test", "confidence": null, "output": {"checks": ["type-check: pass", "unit: pass", "lint: pass"], "passed": true, "output": {"type_check": "Success: no issues found in 2 source files", "unit": "...                                                                      [100%]\n3 passed in 0.01s", "lint": "All checks passed!"}}}
16:13:11.276  {"_aws": {"Timestamp": 1791580391276, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 1.434, "execution_id": "exec-ec2eb471", "Stage": "test"}
16:13:11.334  [test] execution exec-ec2eb471: status=running
```

## 6. Audit trail (S3) and the final state

### `audit/exec-ec2eb471/step_001_ingest.json`

```json
{
  "execution_id": "exec-ec2eb471",
  "step_number": 1,
  "timestamp": "2026-10-09T21:10:56.888210+00:00",
  "step_type": "ingest",
  "input": {
    "service": "demo-app",
    "log_lines": 20
  },
  "output": {
    "outcome": "accepted"
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### `audit/exec-ec2eb471/step_002_investigate.json`

```json
{
  "execution_id": "exec-ec2eb471",
  "step_number": 2,
  "timestamp": "2026-10-09T21:11:23.537263+00:00",
  "step_type": "investigate",
  "input": {
    "files": [
      "src/auth.py"
    ],
    "degraded": []
  },
  "output": {
    "root_cause": "In src/auth.py line 24, the get_display_name() function attempts to access session.user.profile.name without checking if profile is None. When first-time OAuth users log in, they have no profile yet (profile=None), causing an AttributeError when trying to access the 'name' attribute on NoneType.",
    "model_certainty": 95,
    "signal": 1.0,
    "history": null,
    "composite": 91,
    "decision": {
      "composite_confidence": 91,
      "band": "high",
      "blast_radius": {
        "affected_services": 0,
        "estimated_users": 0,
        "sensitive_data_at_risk": false,
        "tier": "medium"
      },
      "tier": "informational",
      "fix_action": "auto_fix_pr",
      "recipient": "unassigned",
      "page": false,
      "channel": "slack",
      "owner": "unassigned"
    }
  },
  "tool_calls": [],
  "confidence_score": 91
}
```

### `audit/exec-ec2eb471/step_003_fix.json`

```json
{
  "execution_id": "exec-ec2eb471",
  "step_number": 3,
  "timestamp": "2026-10-09T21:12:21.356703+00:00",
  "step_type": "fix",
  "input": {
    "files": [
      "src/auth.py"
    ],
    "tests_shown": [
      "tests/test_auth.py"
    ]
  },
  "output": {
    "type": "code-fix",
    "files": [
      "src/auth.py"
    ]
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### `audit/exec-ec2eb471/step_004_remediate.json`

```json
{
  "execution_id": "exec-ec2eb471",
  "step_number": 4,
  "timestamp": "2026-10-09T21:12:22.408573+00:00",
  "step_type": "remediate",
  "input": {
    "files": [
      "src/auth.py"
    ]
  },
  "output": {
    "applied": true,
    "branch": "healer/2026-10-09-fix-src-auth-py-2eb471"
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### `audit/exec-ec2eb471/step_005_test.json`

```json
{
  "execution_id": "exec-ec2eb471",
  "step_number": 5,
  "timestamp": "2026-10-09T21:13:11.233812+00:00",
  "step_type": "test",
  "input": {
    "branch": "healer/2026-10-09-fix-src-auth-py-2eb471"
  },
  "output": {
    "checks": [
      "type-check: pass",
      "unit: pass",
      "lint: pass"
    ],
    "passed": true,
    "output": {
      "type_check": "Success: no issues found in 2 source files",
      "unit": "...                                                                      [100%]\n3 passed in 0.01s",
      "lint": "All checks passed!"
    }
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### `audit/exec-ec2eb471/step_006_pr.json`

```json
{
  "execution_id": "exec-ec2eb471",
  "step_number": 6,
  "timestamp": "2026-10-09T21:13:44.300175+00:00",
  "step_type": "pr",
  "input": {
    "branch": "healer/2026-10-09-fix-src-auth-py-2eb471"
  },
  "output": {
    "pr": "https://github.com/dharmendradevops11/healer-demo-app/pull/19",
    "labels": [
      "healer",
      "healer: auto-fix-pr",
      "healer: blast-radius-medium",
      "healer: human-review"
    ]
  },
  "tool_calls": [],
  "confidence_score": 91
}
```

### Final state `pipeline-state/exec-ec2eb471/state.json`

```json
{
  "execution_id": "exec-ec2eb471",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (slack test 161029)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T21:10:29.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784106874/events/6bcb106ab41047bd991bad453eacfa24/",
    "sentryIssueId": "7784106874",
    "logs": "2026-10-09T21:09:11Z INFO request 129 ok user=1009\n2026-10-09T21:09:15Z INFO request 130 ok user=1010\n2026-10-09T21:09:19Z INFO request 131 ok user=1011\n2026-10-09T21:09:23Z INFO request 132 ok user=1012\n2026-10-09T21:09:27Z INFO request 133 ok user=1013\n2026-10-09T21:09:31Z INFO request 134 ok user=1014\n2026-10-09T21:09:35Z INFO request 135 ok user=1015\n2026-10-09T21:09:39Z INFO request 136 ok user=1016\n2026-10-09T21:09:43Z INFO request 137 ok user=1017\n2026-10-09T21:09:47Z INFO request 138 ok user=1018\n2026-10-09T21:09:51Z INFO request 139 ok user=1019\n2026-10-09T21:09:55Z INFO request 140 ok user=1020\n2026-10-09T21:09:59Z INFO request 141 ok user=1021\n2026-10-09T21:10:03Z INFO request 142 ok user=1022\n2026-10-09T21:10:07Z INFO request 143 ok user=1023\n2026-10-09T21:10:11Z INFO request 144 ok user=1024\n2026-10-09T21:10:15Z INFO request 145 ok user=1025\n2026-10-09T21:10:16Z WARN profile lookup returned None for user=2041\n2026-10-09T21:10:18Z ERROR AttributeError in get_display_name: 'NoneType' object has no attribute 'name' user=2041\n2026-10-09T21:10:19Z ERROR request failed for first-time user user=2041 status=500"
  },
  "status": "pr_opened",
  "reason": "open_pr: supervised: a human reviews every pull request",
  "log_lines": [
    "2026-10-09T21:09:11Z INFO request 129 ok user=1009",
    "2026-10-09T21:09:15Z INFO request 130 ok user=1010",
    "2026-10-09T21:09:19Z INFO request 131 ok user=1011",
    "2026-10-09T21:09:23Z INFO request 132 ok user=1012",
    "2026-10-09T21:09:27Z INFO request 133 ok user=1013",
    "2026-10-09T21:09:31Z INFO request 134 ok user=1014",
    "2026-10-09T21:09:35Z INFO request 135 ok user=1015",
    "2026-10-09T21:09:39Z INFO request 136 ok user=1016",
    "2026-10-09T21:09:43Z INFO request 137 ok user=1017",
    "2026-10-09T21:09:47Z INFO request 138 ok user=1018",
    "2026-10-09T21:09:51Z INFO request 139 ok user=1019",
    "2026-10-09T21:09:55Z INFO request 140 ok user=1020",
    "2026-10-09T21:09:59Z INFO request 141 ok user=1021",
    "2026-10-09T21:10:03Z INFO request 142 ok user=1022",
    "2026-10-09T21:10:07Z INFO request 143 ok user=1023",
    "2026-10-09T21:10:11Z INFO request 144 ok user=1024",
    "2026-10-09T21:10:15Z INFO request 145 ok user=1025",
    "2026-10-09T21:10:16Z WARN profile lookup returned None for user=2041",
    "2026-10-09T21:10:18Z ERROR AttributeError in get_display_name: 'NoneType' object has no attribute 'name' user=2041",
    "2026-10-09T21:10:19Z ERROR request failed for first-time user user=2041 status=500"
  ],
  "diagnosis": {
    "root_cause_hypothesis": "In src/auth.py line 24, the get_display_name() function attempts to access session.user.profile.name without checking if profile is None. When first-time OAuth users log in, they have no profile yet (profile=None), causing an AttributeError when trying to access the 'name' attribute on NoneType.",
    "confidence_score": 95,
    "evidence_summary": "The CloudWatch logs show 'profile lookup returned None for user=2041' followed immediately by the AttributeError for the same user. The error message 'request failed for first-time user' confirms this affects new users. The code comment explicitly states 'First OAuth login: new users have no profile yet. This line crashes for them.' The User dataclass shows profile is Optional[Profile], but get_display_name() doesn't handle the None case before accessing .name. The recent commit message mentions 'one deliberate bug', consistent with this unhandled None case.",
    "affected_files": [
      "src/auth.py"
    ],
    "raw_response": "```json\n{\n  \"rootCauseHypothesis\": \"In src/auth.py line 24, the get_display_name() function attempts to access session.user.profile.name without checking if profile is None. When first-time OAuth users log in, they have no profile yet (profile=None), causing an AttributeError when trying to access the 'name' attribute on NoneType.\",\n  \"confidenceScore\": 95,\n  \"evidenceSummary\": \"The CloudWatch logs show 'profile lookup returned None for user=2041' followed immediately by the AttributeError for the same user. The error message 'request failed for first-time user' confirms this affects new users. The code comment explicitly states 'First OAuth login: new users have no profile yet. This line crashes for them.' The User dataclass shows profile is Optional[Profile], but get_display_name() doesn't handle the None case before accessing .name. The recent commit message mentions 'one deliberate bug', consistent with this unhandled None case.\",\n  \"affectedFiles\": [\n    \"src/auth.py\"\n  ]\n}\n```",
    "fix_strategy": "",
    "reasoning": ""
  },
  "evidence": {
    "log_lines": 20,
    "has_stack_trace": true,
    "files_implied": 1,
    "files_read": 1,
    "has_commit_context": true
  },
  "degraded": [],
  "category": "crash:AttributeError",
  "history": null,
  "signal": 0.9999999999999999,
  "composite": 91,
  "decision": {
    "composite_confidence": 91,
    "band": "high",
    "blast_radius": {
      "affected_services": 0,
      "estimated_users": 0,
      "sensitive_data_at_risk": false,
      "tier": "medium"
    },
    "tier": "informational",
    "fix_action": "auto_fix_pr",
    "recipient": "unassigned",
    "page": false,
    "channel": "slack",
    "owner": "unassigned"
  },
  "proposal": {
    "type": "code-fix",
    "diff": "diff --git a/src/auth.py b/src/auth.py\n--- a/src/auth.py\n+++ b/src/auth.py\n@@ -18,7 +18,10 @@ class Session:\n \n \n def get_display_name(session: Session) -> str:\n-    # First OAuth login: new users have no profile yet. This line crashes for them.\n-    return session.user.profile.name.strip()  # type: ignore[union-attr]\n+    # First OAuth login: new users have no profile yet.\n+    if session.user.profile is None:\n+        return \"there\"\n+    return session.user.profile.name.strip()\n \n \n def greet(session: Session) -> str:",
    "affected_files": [
      "src/auth.py"
    ],
    "explanation": "The fix adds a None check for session.user.profile before accessing its name attribute. When profile is None (first-time OAuth users), it returns the default value \"there\" as specified by the test. Otherwise, it returns the trimmed profile name as before. This prevents the AttributeError that occurs when trying to access .name on a NoneType object.",
    "raw_response": "```json\n{\n  \"type\": \"code-fix\",\n  \"diff\": \"diff --git a/src/auth.py b/src/auth.py\\n--- a/src/auth.py\\n+++ b/src/auth.py\\n@@ -18,7 +18,10 @@ class Session:\\n \\n \\n def get_display_name(session: Session) -> str:\\n-    # First OAuth login: new users have no profile yet. This line crashes for them.\\n-    return session.user.profile.name.strip()  # type: ignore[union-attr]\\n+    # First OAuth login: new users have no profile yet.\\n+    if session.user.profile is None:\\n+        return \\\"there\\\"\\n+    return session.user.profile.name.strip()\\n \\n \\n def greet(session: Session) -> str:\",\n  \"affectedFiles\": [\"src/auth.py\"],\n  \"explanation\": \"The fix adds a None check for session.user.profile before accessing its name attribute. When profile is None (first-time OAuth users), it returns the default value \\\"there\\\" as specified by the test. Otherwise, it returns the trimmed profile name as before. This prevents the AttributeError that occurs when trying to access .name on a NoneType object.\"\n}\n```"
  },
  "plan_action": "open_pr: supervised: a human reviews every pull request",
  "branch": "healer/2026-10-09-fix-src-auth-py-2eb471",
  "fix_commit": "19ab6bc",
  "tests": {
    "checks": [
      {
        "name": "type_check",
        "status": "pass",
        "output": "Success: no issues found in 2 source files\n"
      },
      {
        "name": "unit",
        "status": "pass",
        "output": "...                                                                      [100%]\n3 passed in 0.01s\n"
      },
      {
        "name": "lint",
        "status": "pass",
        "output": "All checks passed!\n"
      }
    ]
  },
  "pr": {
    "number": 19,
    "url": "https://github.com/dharmendradevops11/healer-demo-app/pull/19",
    "title": "[HEALER] fix: AttributeError: 'NoneType' object has no attribute 'name' (slack test ",
    "branch": "healer/2026-10-09-fix-src-auth-py-2eb471",
    "labels": [
      "healer",
      "healer: auto-fix-pr",
      "healer: blast-radius-medium",
      "healer: human-review"
    ]
  },
  "notified": true,
  "review_flags": [
    "unowned service: it has no named team or on-call rotation in the registry",
    "new failure pattern: the ledger has too little history for this category"
  ],
  "constraint_problems": [],
  "end_to_end_reported": true,
  "audit_keys": [
    "audit/exec-ec2eb471/step_001_ingest.json",
    "audit/exec-ec2eb471/step_002_investigate.json",
    "audit/exec-ec2eb471/step_003_fix.json",
    "audit/exec-ec2eb471/step_004_remediate.json",
    "audit/exec-ec2eb471/step_005_test.json",
    "audit/exec-ec2eb471/step_006_pr.json"
  ]
}
```

