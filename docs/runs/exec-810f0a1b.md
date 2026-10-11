# Run `exec-810f0a1b`

Exported 2026-10-09 15:50 local time from region `us-east-1`. Account shown as `<account>`.

| | |
|---|---|
| Step Functions execution | `303423cd-6034-5efd-a1aa-408e3532b61f` |
| Status | **SUCCEEDED** |
| Started | 15:47:12 |
| Stopped | 15:50:04 |
| Console | https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/v2/executions/details/arn:aws:states:us-east-1:<account>:execution:StateMachine2E01A3A5-J16ZhWEQEldV:303423cd-6034-5efd-a1aa-408e3532b61f |

## 1. Webhook Lambda (the front door)

Log group `SelfHealingPipeline-WebhookReceiverLogsA2D32536-APGgLsEunhQo`

```
15:47:12.174  {"hop": "webhook->sns", "execution_id": "exec-810f0a1b", "sns_message_id": "4eaa5d1d-d2c4-58c9-a657-3e5e87d45070", "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingPipeline-TriggerTopic92976BC4-IhEQqbgkRKaA", "service": "demo-app", "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)"}
```

## 2. EventBridge Pipe (queue to Step Functions)

Log group `SelfHealingPipeline-PipeLogs8633E6FA-TZkhQ2nzKvyr`. The first event holds the raw SQS record the pipe read.

```
15:47:12.257  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791578832257,"executionId":"ddbf4713-18f6-4224-b7fe-013dbd969e6a","messageType":"ExecutionStarted","logLevel":"INFO","payload":"{\"Records\":[{\"messageId\":\"4b7f60d5-b85c-4b14-bea2-c4c383888cfd\",\"receiptHandle\":\"AQEB1RoGtKamp7AHSqEjj96Zm1/6sE6m3cQ7uMU22uAuq+CWX10fJ6whqGbS7Jg4A54/RoIly9jcKxQxfNeuIY/jzeUwJN+c9zIx3heKuyZTdGBeI8nHZeXSTYUU5MWpKeHSvIPWmp/rUS1ctpYD72qOe4gY8Ah3Rk0zMlrbmz9lGkFQwJ0ICdnuNGDTiYuPFfmKHy2WTYOjD7j+DVJ0hm4QI3D4+SPpwajrO4uIwgVMeoMkoSUlHmvi7pLuuaPJvghekxYVETCx/a2TrtV+XE8Q4QEq4pgtqad4BLjjaznbLHwYzdDD6f1YP5AnMw7vtjEva67o99XC47iuUjdWdpQe3fE0dUP0Tsok8Kck8OFg+yxuMImQBLm480AM4bj6m37CmzJzBgNe/kVyhsJf8n3TV6zQjBYNsPenNvGSi44ELhxgf58u9dUqYYdxhzKU3Pc8\",\"body\":\"{\\\"executionId\\\": \\\"exec-810f0a1b\\\", \\\"incident\\\": {\\\"source\\\": \\\"sentry\\\", \\\"severity\\\": \\\"high\\\", \\\"type\\\": \\\"crash\\\", \\\"title\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\\\", \\\"stackTrace\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\\\\nTraceback (most recent call last)\\\\n  File \\\\\\\"src/auth.py\\\\\\\", line 28, in greet\\\\n  File \\\\\\\"src/auth.py\\\\\\\", line 24, in get_display_name\\\", \\\"affectedService\\\": \\\"demo-app\\\", \\\"cloudwatchLogGroup\\\": \\\"/aws/ecs/demo-app\\\", \\\"triggeredAt\\\": \\\"2026-10-09T20:46:49.000000Z\\\", \\\"sentryIssueUrl\\\": \\\"https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/\\\", \\\"sentryIssueId\\\": \\\"7784073374\\\"}}\",\"attributes\":{\"ApproximateReceiveCount\":\"1\",\"AWSTraceHeader\":\"Root=1-6ac952cc-197592104c94b80866e24e52;Parent=32f4cc0ee4e63358;Sampled=0;Lineage=1:a6e3e63c:0\",\"SentTimestamp\":\"1791578832236\",\"SenderId\":\"AROA3TYMO3BGGTBI3MZUH:AWS-CLOUDCAST\",\"ApproximateFirstReceiveTimestamp\":\"1791578832245\"},\"messageAttributes\":{},\"md5OfBody\":\"0415cdd9d340cc4251c49d7bd5eb068f\",\"eventSource\":\"aws:sqs\",\"eventSourceARN\":\"arn:aws:sqs:us-east-1:<account>:SelfHealingPipeline-TriggerQueue434C4AA5-uUkPt3JwJjya\",\"awsRegion\":\"us-east-1\"}]}"}
15:47:12.268  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791578832268,"executionId":"ddbf4713-18f6-4224-b7fe-013dbd969e6a","messageType":"TargetStageEntered","logLevel":"INFO"}
15:47:12.376  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791578832376,"executionId":"ddbf4713-18f6-4224-b7fe-013dbd969e6a","messageType":"ExecutionSucceeded","logLevel":"INFO"}
15:47:12.376  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-oc57KtkSRiQ3","timestamp":1791578832376,"executionId":"ddbf4713-18f6-4224-b7fe-013dbd969e6a","messageType":"TargetStageSucceeded","logLevel":"INFO","payload":""}
```

## 3. Step Functions: every state, its time, input and output

| State | Started | Seconds |
|---|---|---|
| InputShape | 15:47:12 | 0.0 |
| UnwrapBatch | 15:47:12 | 0.0 |
| Ingest | 15:47:12 | 4.6 |
| Accepted | 15:47:16 | 0.0 |
| Investigate | 15:47:16 | 50.3 |
| Route | 15:48:07 | 4.1 |
| Gate | 15:48:11 | 0.0 |
| Fix | 15:48:11 | 52.7 |
| RouteAfterFix | 15:49:04 | 0.2 |
| FixOutcome | 15:49:04 | 0.0 |
| Test | 15:49:04 | 49.3 |
| OpenPr | 15:49:53 | 6.3 |
| Notify | 15:49:59 | 4.3 |
| PullRequestOpened | 15:50:04 | 0.0 |

### Ingest

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  }
}
```

### Investigate

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  }
}
```

### Route

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### Fix

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### RouteAfterFix

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### Test

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### OpenPr

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

### Notify

Input:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

Output:

```json
{
  "executionId": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374"
  },
  "ingest": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-810f0a1b",
    "status": "running",
    "fixAction": "auto_fix_pr"
  }
}
```

## 4. Lambda logs (full)

### Ingest: function `SelfHealingPipeline-Ingest4069586C-96sTMKxkqcHq`, log group `SelfHealingPipeline-IngestLogs7327CBDC-uNlWWsY2cDq7`

```
15:47:12.811  START RequestId: cb5c0be4-c2d0-4a55-9003-60ae05128fef Version: $LATEST
15:47:16.839  {"execution_id": "exec-810f0a1b", "step": "ingest", "confidence": null, "output": {"outcome": "accepted"}}
15:47:16.839  {"_aws": {"Timestamp": 1791578836839, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 2.408, "execution_id": "exec-810f0a1b", "Stage": "ingest"}
15:47:16.954  END RequestId: cb5c0be4-c2d0-4a55-9003-60ae05128fef
15:47:16.954  REPORT RequestId: cb5c0be4-c2d0-4a55-9003-60ae05128fef	Duration: 4142.38 ms	Billed Duration: 4349 ms	Memory Size: 512 MB	Max Memory Used: 109 MB	Init Duration: 205.93 ms
```

### Route: function `SelfHealingPipeline-RouteA67450D2-mzwTqL6g4d5J`, log group `SelfHealingPipeline-RouteLogs174AF25A-hN541QyQ5Bpa`

```
15:48:07.693  START RequestId: bbdd36ad-db5d-4af0-abd5-da0719ec6397 Version: $LATEST
15:48:11.355  END RequestId: bbdd36ad-db5d-4af0-abd5-da0719ec6397
15:48:11.355  REPORT RequestId: bbdd36ad-db5d-4af0-abd5-da0719ec6397	Duration: 3660.65 ms	Billed Duration: 3871 ms	Memory Size: 256 MB	Max Memory Used: 106 MB	Init Duration: 210.23 ms
```

### RouteAfterFix: function `SelfHealingPipeline-RouteA67450D2-mzwTqL6g4d5J`, log group `SelfHealingPipeline-RouteLogs174AF25A-hN541QyQ5Bpa`

```
15:49:04.159  START RequestId: 15dd2263-4403-4c3e-8953-2feb57f41dfa Version: $LATEST
15:49:04.292  END RequestId: 15dd2263-4403-4c3e-8953-2feb57f41dfa
15:49:04.292  REPORT RequestId: 15dd2263-4403-4c3e-8953-2feb57f41dfa	Duration: 131.89 ms	Billed Duration: 132 ms	Memory Size: 256 MB	Max Memory Used: 106 MB
```

### OpenPr: function `SelfHealingPipeline-OpenPr92F50AD2-i5GWz4JCrZVL`, log group `SelfHealingPipeline-OpenPrLogs4AF57F65-UpFmCDzo2b9E`

```
15:49:54.064  START RequestId: 3db1de03-9df3-4228-a22a-16d68f7590e5 Version: $LATEST
15:49:59.791  {"execution_id": "exec-810f0a1b", "step": "pr", "confidence": 91, "output": {"pr": "https://github.com/dharmendradevops11/healer-demo-app/pull/17", "labels": ["healer", "healer: auto-fix-pr", "healer: blast-radius-medium", "healer: human-review"]}}
15:49:59.862  {"_aws": {"Timestamp": 1791578999862, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 4.029, "execution_id": "exec-810f0a1b", "Stage": "pr"}
15:49:59.862  {"_aws": {"Timestamp": 1791578999862, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Outcome"]], "Metrics": [{"Name": "EndToEndSeconds", "Unit": "Seconds"}]}]}, "EndToEndSeconds": 190.9, "execution_id": "exec-810f0a1b", "Outcome": "pr_opened"}
15:49:59.902  END RequestId: 3db1de03-9df3-4228-a22a-16d68f7590e5
15:49:59.902  REPORT RequestId: 3db1de03-9df3-4228-a22a-16d68f7590e5	Duration: 5837.50 ms	Billed Duration: 6049 ms	Memory Size: 512 MB	Max Memory Used: 109 MB	Init Duration: 211.21 ms
```

### Notify: function `SelfHealingPipeline-Notify29C25B1B-waClKV3bDfn2`, log group `SelfHealingPipeline-NotifyLogsC0ABC89F-qVKu4VXhoO6g`

```
15:50:00.390  START RequestId: fbbb60fc-e16c-4fb1-9948-6e0fa3d837a0 Version: $LATEST
15:50:04.182  {"hop": "notify->sns", "sns_message_id": "82762d6d-ae7b-5314-aae2-4e2efbc759c7", "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingState-NotificationTopicEB7A0DF1-ZxzTplsPy47u", "subject": "[INFO] [Healer] demo-app: Fix ready (91/100)", "attributes": {"escalationTier": "informational", "page": "False", "channel": "slack", "fixAction": "auto_fix_pr"}, "message": "Self-Healer: Fix ready\nEscalation: INFO -> unassigned via slack (page: no)\nRouting: high confidence x medium blast radius -> auto_fix_pr\nService: demo-app\nIssue: AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nRoot cause: In src/auth.py line 24, get_display_name() attempts to access session.user.profile.name without checking if profile is None. For new OAuth users (like user=2041), the profile field is None, causing an AttributeError when .name is accessed.\nConfidence: 91/100\nHuman review required: unowned service: it has no named team or on-call rotation in the registry\nHuman review required: new failure pattern: the ledger has too little history for this category\nPR: https://github.com/dharmendradevops11/healer-demo-app/pull/17"}
15:50:04.182  {"_aws": {"Timestamp": 1791579004182, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 0.115, "execution_id": "exec-810f0a1b", "Stage": "notify"}
15:50:04.223  END RequestId: fbbb60fc-e16c-4fb1-9948-6e0fa3d837a0
15:50:04.224  REPORT RequestId: fbbb60fc-e16c-4fb1-9948-6e0fa3d837a0	Duration: 3832.13 ms	Billed Duration: 4044 ms	Memory Size: 256 MB	Max Memory Used: 106 MB	Init Duration: 211.62 ms
```

## 5. Fargate task logs (full) and task details

### Investigate: task `aa5ec29a7b4640c7b30ebe45ef1d4b6b`, stream `investigate/healer-investigate/aa5ec29a7b4640c7b30ebe45ef1d4b6b`

CPU 1024 / memory 2048 MB, exit code **0**, started 15:47:36, stopped 15:48:06, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-sjN1cxd3l54G/tasks/aa5ec29a7b4640c7b30ebe45ef1d4b6b/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`, stream above.

```
15:47:42.781  {"execution_id": "exec-810f0a1b", "step": "investigate", "confidence": 91, "output": {"root_cause": "In src/auth.py line 24, get_display_name() attempts to access session.user.profile.name without checking if profile is None. For new OAuth users (like user=2041), the profile field is None, causing an... [239 chars]", "model_certainty": 95, "signal": 1.0, "history": null, "composite": 91, "decision": {"composite_confidence": 91, "band": "high", "blast_radius": {"affected_services": 0, "estimated_users": 0, "sensitive_data_at_risk": false, "tier": "medium"}, "tier": "informational", "fix_action": "auto_fix_pr", "recipient": "unassigned", "page": false, "channel": "slack", "owner": "unassigned"}}}
15:47:42.781  {"_aws": {"Timestamp": 1791578862781, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 5.638, "execution_id": "exec-810f0a1b", "Stage": "investigate"}
15:47:42.820  [investigate] execution exec-810f0a1b: status=running
```

### Fix: task `b88ac04c6fcd42d0adfa5c10c9a5e7a6`, stream `fix/healer-fix/b88ac04c6fcd42d0adfa5c10c9a5e7a6`

CPU 1024 / memory 2048 MB, exit code **0**, started 15:48:31, stopped 15:49:02, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-sjN1cxd3l54G/tasks/b88ac04c6fcd42d0adfa5c10c9a5e7a6/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`, stream above.

```
15:48:36.891  {"execution_id": "exec-810f0a1b", "step": "fix", "confidence": null, "output": {"type": "code-fix", "files": ["src/auth.py"]}}
15:48:37.927  {"execution_id": "exec-810f0a1b", "step": "remediate", "confidence": null, "output": {"applied": true, "branch": "healer/2026-10-09-fix-src-auth-py-0f0a1b"}}
15:48:37.929  {"_aws": {"Timestamp": 1791578917929, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 5.994, "execution_id": "exec-810f0a1b", "Stage": "fix"}
15:48:37.977  [fix] execution exec-810f0a1b: status=running
```

### Test: task `c4d5711772fc49efb2d67bfe4d92d787`, stream `test/healer-test/c4d5711772fc49efb2d67bfe4d92d787`

CPU 2048 / memory 4096 MB, exit code **0**, started 15:49:25, stopped 15:49:52, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-sjN1cxd3l54G/tasks/c4d5711772fc49efb2d67bfe4d92d787/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-5PDzjc8j2rtS`, stream above.

```
15:49:28.047  [test:type_check] pass
15:49:28.047  Success: no issues found in 2 source files
15:49:28.047  [test:unit] pass
15:49:28.047  ...                                                                      [100%]
15:49:28.047  3 passed in 0.01s
15:49:28.047  [test:lint] pass
15:49:28.047  All checks passed!
15:49:28.096  {"execution_id": "exec-810f0a1b", "step": "test", "confidence": null, "output": {"checks": ["type-check: pass", "unit: pass", "lint: pass"], "passed": true, "output": {"type_check": "Success: no issues found in 2 source files", "unit": "...                                                                      [100%]\n3 passed in 0.01s", "lint": "All checks passed!"}}}
15:49:28.096  {"_aws": {"Timestamp": 1791578968096, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 1.759, "execution_id": "exec-810f0a1b", "Stage": "test"}
15:49:28.151  [test] execution exec-810f0a1b: status=running
```

## 6. Audit trail (S3) and the final state

### `audit/exec-810f0a1b/step_001_ingest.json`

```json
{
  "execution_id": "exec-810f0a1b",
  "step_number": 1,
  "timestamp": "2026-10-09T20:47:16.793128+00:00",
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

### `audit/exec-810f0a1b/step_002_investigate.json`

```json
{
  "execution_id": "exec-810f0a1b",
  "step_number": 2,
  "timestamp": "2026-10-09T20:47:42.734417+00:00",
  "step_type": "investigate",
  "input": {
    "files": [
      "src/auth.py"
    ],
    "degraded": []
  },
  "output": {
    "root_cause": "In src/auth.py line 24, get_display_name() attempts to access session.user.profile.name without checking if profile is None. For new OAuth users (like user=2041), the profile field is None, causing an AttributeError when .name is accessed.",
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

### `audit/exec-810f0a1b/step_003_fix.json`

```json
{
  "execution_id": "exec-810f0a1b",
  "step_number": 3,
  "timestamp": "2026-10-09T20:48:36.837212+00:00",
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

### `audit/exec-810f0a1b/step_004_remediate.json`

```json
{
  "execution_id": "exec-810f0a1b",
  "step_number": 4,
  "timestamp": "2026-10-09T20:48:37.889915+00:00",
  "step_type": "remediate",
  "input": {
    "files": [
      "src/auth.py"
    ]
  },
  "output": {
    "applied": true,
    "branch": "healer/2026-10-09-fix-src-auth-py-0f0a1b"
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### `audit/exec-810f0a1b/step_005_test.json`

```json
{
  "execution_id": "exec-810f0a1b",
  "step_number": 5,
  "timestamp": "2026-10-09T20:49:28.047400+00:00",
  "step_type": "test",
  "input": {
    "branch": "healer/2026-10-09-fix-src-auth-py-0f0a1b"
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

### `audit/exec-810f0a1b/step_006_pr.json`

```json
{
  "execution_id": "exec-810f0a1b",
  "step_number": 6,
  "timestamp": "2026-10-09T20:49:59.741188+00:00",
  "step_type": "pr",
  "input": {
    "branch": "healer/2026-10-09-fix-src-auth-py-0f0a1b"
  },
  "output": {
    "pr": "https://github.com/dharmendradevops11/healer-demo-app/pull/17",
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

### Final state `pipeline-state/exec-810f0a1b/state.json`

```json
{
  "execution_id": "exec-810f0a1b",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name' (logs test 154649)\nTraceback (most recent call last)\n  File \"src/auth.py\", line 28, in greet\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-09T20:46:49.000000Z",
    "sentryIssueUrl": "https://sentry.io/organizations/<org>/issues/7784073374/events/38e3a47a605b4294abc4a836fcd50b3d/",
    "sentryIssueId": "7784073374",
    "logs": "2026-10-09T20:45:31Z INFO request 69 ok user=1009\n2026-10-09T20:45:35Z INFO request 70 ok user=1010\n2026-10-09T20:45:39Z INFO request 71 ok user=1011\n2026-10-09T20:45:43Z INFO request 72 ok user=1012\n2026-10-09T20:45:47Z INFO request 73 ok user=1013\n2026-10-09T20:45:51Z INFO request 74 ok user=1014\n2026-10-09T20:45:55Z INFO request 75 ok user=1015\n2026-10-09T20:45:59Z INFO request 76 ok user=1016\n2026-10-09T20:46:03Z INFO request 77 ok user=1017\n2026-10-09T20:46:07Z INFO request 78 ok user=1018\n2026-10-09T20:46:11Z INFO request 79 ok user=1019\n2026-10-09T20:46:15Z INFO request 80 ok user=1020\n2026-10-09T20:46:19Z INFO request 81 ok user=1021\n2026-10-09T20:46:23Z INFO request 82 ok user=1022\n2026-10-09T20:46:27Z INFO request 83 ok user=1023\n2026-10-09T20:46:31Z INFO request 84 ok user=1024\n2026-10-09T20:46:35Z INFO request 85 ok user=1025\n2026-10-09T20:46:36Z WARN profile lookup returned None for user=2041\n2026-10-09T20:46:38Z ERROR AttributeError in get_display_name: 'NoneType' object has no attribute 'name' user=2041\n2026-10-09T20:46:39Z ERROR request failed for first-time user user=2041 status=500"
  },
  "status": "pr_opened",
  "reason": "open_pr: supervised: a human reviews every pull request",
  "log_lines": [
    "2026-10-09T20:45:31Z INFO request 69 ok user=1009",
    "2026-10-09T20:45:35Z INFO request 70 ok user=1010",
    "2026-10-09T20:45:39Z INFO request 71 ok user=1011",
    "2026-10-09T20:45:43Z INFO request 72 ok user=1012",
    "2026-10-09T20:45:47Z INFO request 73 ok user=1013",
    "2026-10-09T20:45:51Z INFO request 74 ok user=1014",
    "2026-10-09T20:45:55Z INFO request 75 ok user=1015",
    "2026-10-09T20:45:59Z INFO request 76 ok user=1016",
    "2026-10-09T20:46:03Z INFO request 77 ok user=1017",
    "2026-10-09T20:46:07Z INFO request 78 ok user=1018",
    "2026-10-09T20:46:11Z INFO request 79 ok user=1019",
    "2026-10-09T20:46:15Z INFO request 80 ok user=1020",
    "2026-10-09T20:46:19Z INFO request 81 ok user=1021",
    "2026-10-09T20:46:23Z INFO request 82 ok user=1022",
    "2026-10-09T20:46:27Z INFO request 83 ok user=1023",
    "2026-10-09T20:46:31Z INFO request 84 ok user=1024",
    "2026-10-09T20:46:35Z INFO request 85 ok user=1025",
    "2026-10-09T20:46:36Z WARN profile lookup returned None for user=2041",
    "2026-10-09T20:46:38Z ERROR AttributeError in get_display_name: 'NoneType' object has no attribute 'name' user=2041",
    "2026-10-09T20:46:39Z ERROR request failed for first-time user user=2041 status=500"
  ],
  "diagnosis": {
    "root_cause_hypothesis": "In src/auth.py line 24, get_display_name() attempts to access session.user.profile.name without checking if profile is None. For new OAuth users (like user=2041), the profile field is None, causing an AttributeError when .name is accessed.",
    "confidence_score": 95,
    "evidence_summary": "The code shows Profile is Optional[Profile] = None in the User dataclass. The CloudWatch logs show 'profile lookup returned None for user=2041' immediately before the AttributeError. The commit message explicitly states 'Demo app with one deliberate bug'. Line 24 accesses profile.name without null-checking, and the comment on that line states 'First OAuth login: new users have no profile yet. This line crashes for them.'",
    "affected_files": [
      "src/auth.py"
    ],
    "raw_response": "```json\n{\n  \"rootCauseHypothesis\": \"In src/auth.py line 24, get_display_name() attempts to access session.user.profile.name without checking if profile is None. For new OAuth users (like user=2041), the profile field is None, causing an AttributeError when .name is accessed.\",\n  \"confidenceScore\": 95,\n  \"evidenceSummary\": \"The code shows Profile is Optional[Profile] = None in the User dataclass. The CloudWatch logs show 'profile lookup returned None for user=2041' immediately before the AttributeError. The commit message explicitly states 'Demo app with one deliberate bug'. Line 24 accesses profile.name without null-checking, and the comment on that line states 'First OAuth login: new users have no profile yet. This line crashes for them.'\",\n  \"affectedFiles\": [\n    \"src/auth.py\"\n  ]\n}\n```",
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
    "diff": "diff --git a/src/auth.py b/src/auth.py\n--- a/src/auth.py\n+++ b/src/auth.py\n@@ -18,7 +18,10 @@ class Session:\n \n \n def get_display_name(session: Session) -> str:\n-    # First OAuth login: new users have no profile yet. This line crashes for them.\n-    return session.user.profile.name.strip()  # type: ignore[union-attr]\n+    # First OAuth login: new users have no profile yet.\n+    if session.user.profile is None:\n+        return \"there\"\n+    return session.user.profile.name.strip()\n \n \n def greet(session: Session) -> str:\n",
    "affected_files": [
      "src/auth.py"
    ],
    "explanation": "The fix adds a null check for session.user.profile before accessing the name attribute. When profile is None (as it is for new OAuth users), the function returns the default value \"there\" as expected by the test. For existing users with profiles, it returns the trimmed profile name as before.",
    "raw_response": "```json\n{\n  \"type\": \"code-fix\",\n  \"diff\": \"diff --git a/src/auth.py b/src/auth.py\\n--- a/src/auth.py\\n+++ b/src/auth.py\\n@@ -18,7 +18,10 @@ class Session:\\n \\n \\n def get_display_name(session: Session) -> str:\\n-    # First OAuth login: new users have no profile yet. This line crashes for them.\\n-    return session.user.profile.name.strip()  # type: ignore[union-attr]\\n+    # First OAuth login: new users have no profile yet.\\n+    if session.user.profile is None:\\n+        return \\\"there\\\"\\n+    return session.user.profile.name.strip()\\n \\n \\n def greet(session: Session) -> str:\\n\",\n  \"affectedFiles\": [\"src/auth.py\"],\n  \"explanation\": \"The fix adds a null check for session.user.profile before accessing the name attribute. When profile is None (as it is for new OAuth users), the function returns the default value \\\"there\\\" as expected by the test. For existing users with profiles, it returns the trimmed profile name as before.\"\n}\n```"
  },
  "plan_action": "open_pr: supervised: a human reviews every pull request",
  "branch": "healer/2026-10-09-fix-src-auth-py-0f0a1b",
  "fix_commit": "a2e4fa3",
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
    "number": 17,
    "url": "https://github.com/dharmendradevops11/healer-demo-app/pull/17",
    "title": "[HEALER] fix: AttributeError: 'NoneType' object has no attribute 'name' (logs test 1",
    "branch": "healer/2026-10-09-fix-src-auth-py-0f0a1b",
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
    "audit/exec-810f0a1b/step_001_ingest.json",
    "audit/exec-810f0a1b/step_002_investigate.json",
    "audit/exec-810f0a1b/step_003_fix.json",
    "audit/exec-810f0a1b/step_004_remediate.json",
    "audit/exec-810f0a1b/step_005_test.json",
    "audit/exec-810f0a1b/step_006_pr.json"
  ]
}
```

