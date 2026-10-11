# Run `exec-d0e8a14f`

Exported 2026-10-11 17:45 local time from region `us-east-1`. Account shown as `<account>`.

| | |
|---|---|
| Step Functions execution | `6934de80-438c-5404-aaee-bdc6520588bf` |
| Status | **SUCCEEDED** |
| Started | 17:36:08 |
| Stopped | 17:38:58 |
| Console | https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/v2/executions/details/arn:aws:states:us-east-1:<account>:execution:StateMachine2E01A3A5-2sIO5pMqKf7d:6934de80-438c-5404-aaee-bdc6520588bf |

## 1. Webhook Lambda (the front door)

Log group `SelfHealingPipeline-WebhookReceiverLogsA2D32536-Al1IPxMZm5Uj`

```
17:36:08.577  {"hop": "webhook->sns", "execution_id": "exec-d0e8a14f", "sns_message_id": "2383c8d9-7343-5685-abcd-ab9f62dba74e", "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingPipeline-TriggerTopic92976BC4-vGCzKrFzLjbk", "service": "demo-app", "title": "AttributeError: 'NoneType' object has no attribute 'name'"}
```

## 2. EventBridge Pipe (queue to Step Functions)

Log group `SelfHealingPipeline-PipeLogs8633E6FA-3qcCXss7rsku`. The first event holds the raw SQS record the pipe read.

```
17:36:08.647  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758168647,"executionId":"4af08f14-347c-4e6f-be38-b34b063f1d2d","messageType":"ExecutionStarted","logLevel":"INFO","payload":"{\"Records\":[{\"messageId\":\"29fbd1b3-86d7-4161-80dc-9aa1a190afd4\",\"receiptHandle\":\"AQEB5VzQF6FrJ1YtQ8HV2hA64TalwlmB6SGOUOVyqptsr7KWjg44/KbcbkWx7kMzVdXEVqGfE48//4/SBt5AlCrvjH3Q6kE09U/vJjV/s80MHCb2+GDzDoxqwx2237eKRmfsjcfhAAJfqSiM3Kp7ArlWQyq3/DGEAF01b9CDDmZvCFEYccVDxJGNYWIYrCQun1XkYVrnP0SYggVla7WjvXT3TL46xCqcm3pBuymvcI1xAC0QEn56TcCwdG96AYOQWqd0hZaR1o0WbBho5wATL9jk0lmYz92u8TSvcHsgGzkQ4esI0g/zAQHY4xh3/uMLpHdNvo3nwZBkJ/gW6uM1/8ra3jUdxcIzkLo8XN/UqpGWoxPqvTMWQ7+7rLSfzpbZdpCe6QeLF68W0caOVEWR5zmWITIScbhRyV/8+fSG1AF1bNMidz7Kvs0w+wAot6cXOglc\",\"body\":\"{\\\"executionId\\\": \\\"exec-d0e8a14f\\\", \\\"incident\\\": {\\\"source\\\": \\\"sentry\\\", \\\"severity\\\": \\\"high\\\", \\\"type\\\": \\\"crash\\\", \\\"title\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name'\\\", \\\"stackTrace\\\": \\\"AttributeError: 'NoneType' object has no attribute 'name'\\\\nTraceback (most recent call last)\\\\n  File \\\\\\\"src/auth.py\\\\\\\", line 24, in get_display_name\\\", \\\"affectedService\\\": \\\"demo-app\\\", \\\"cloudwatchLogGroup\\\": \\\"/aws/ecs/demo-app\\\", \\\"triggeredAt\\\": \\\"2026-10-11T22:36:08.140342+00:00\\\", \\\"sentryIssueUrl\\\": \\\"https://example.sentry.io/issues/1791758168/\\\", \\\"sentryIssueId\\\": \\\"1791758168\\\"}}\",\"attributes\":{\"ApproximateReceiveCount\":\"1\",\"AWSTraceHeader\":\"Root=1-6acc0f58-45bf67400b91c33f2644974c;Parent=7511539dda32ccf3;Sampled=0;Lineage=1:48ff261a:0\",\"SentTimestamp\":\"1791758168620\",\"SenderId\":\"AROA3TYMO3BGGTBI3MZUH:AWS-CLOUDCAST\",\"ApproximateFirstReceiveTimestamp\":\"1791758168631\"},\"messageAttributes\":{},\"md5OfBody\":\"422ff1a795a951282b9ccf9fd610fd87\",\"eventSource\":\"aws:sqs\",\"eventSourceARN\":\"arn:aws:sqs:us-east-1:<account>:SelfHealingPipeline-TriggerQueue434C4AA5-Dq9dc5trDD2E\",\"awsRegion\":\"us-east-1\"}]}"}
17:36:08.658  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758168658,"executionId":"4af08f14-347c-4e6f-be38-b34b063f1d2d","messageType":"TargetStageEntered","logLevel":"INFO"}
17:36:08.734  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758168734,"executionId":"4af08f14-347c-4e6f-be38-b34b063f1d2d","messageType":"TargetStageSucceeded","logLevel":"INFO","payload":""}
17:36:08.734  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758168734,"executionId":"4af08f14-347c-4e6f-be38-b34b063f1d2d","messageType":"ExecutionSucceeded","logLevel":"INFO"}
17:39:34.970  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758374970,"executionId":"ad416b09-aa20-4736-b211-d06daa03bff9","messageType":"ExecutionStarted","logLevel":"INFO","payload":"{\"Records\":[{\"messageId\":\"fb8c2e92-9598-42f5-941d-0b0f98440e30\",\"receiptHandle\":\"AQEB8YfUQPpsSfgtW68Rc8tjWy5RGv2Eqvv5xVmHs4Elm7aBOcsiRVC1h5+jGo+bUvt8duTl56sJOEu0tvpCLzarHreh4jL3ufQItSKnqHXbk/SDG86ecTANOXlDZJzsMQjUGeG/w7gwJZWIreQ0fSXee9ij15hOE+uzFH43VDzwGc5jQZW2U9vDQCNu8MTeCdNG4PY3DLZMMgYB7ENOdy9H9sIrBiNMTRpJcL4rimK1DNhGvuVute+85pd7BoWkQNTzb36uD2T6nGC2IoDiXN0zjilLrBGKd34G4kvTvPkIMBodTHq6O8xep4oFYrRsYyRY14BJnIIFKjdi9zG15BAotgxMjvcOGeeRooT9jSEAD1RykgsWLLcsTeGUz9Df5DwxGHAJc/p8NX4/JSB9pY4vCDhyZMxpVhE6axm/DP4Ld5uRZrTp8BZu/cFz7pH75CEO\",\"body\":\"{\\\"executionId\\\": \\\"exec-9677880a\\\", \\\"incident\\\": {\\\"source\\\": \\\"sentry\\\", \\\"severity\\\": \\\"high\\\", \\\"type\\\": \\\"crash\\\", \\\"title\\\": \\\"Something odd happened\\\", \\\"stackTrace\\\": \\\"Something odd happened\\\", \\\"affectedService\\\": \\\"unknown-svc\\\", \\\"cloudwatchLogGroup\\\": \\\"/aws/ecs/unknown-svc\\\", \\\"triggeredAt\\\": \\\"2026-10-11T22:39:34.128358+00:00\\\", \\\"sentryIssueId\\\": \\\"1791758374\\\"}}\",\"attributes\":{\"ApproximateReceiveCount\":\"1\",\"AWSTraceHeader\":\"Root=1-6acc1026-2d5503f74ee4a49c43086a06;Parent=22a235a9f50d22f9;Sampled=0;Lineage=1:48ff261a:0\",\"SentTimestamp\":\"1791758374952\",\"SenderId\":\"AROA3TYMO3BGGTBI3MZUH:AWS-CLOUDCAST\",\"ApproximateFirstReceiveTimestamp\":\"1791758374958\"},\"messageAttributes\":{},\"md5OfBody\":\"aed83193eb2b1c9477effb661e6a817b\",\"eventSource\":\"aws:sqs\",\"eventSourceARN\":\"arn:aws:sqs:us-east-1:<account>:SelfHealingPipeline-TriggerQueue434C4AA5-Dq9dc5trDD2E\",\"awsRegion\":\"us-east-1\"}]}"}
17:39:34.980  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758374980,"executionId":"ad416b09-aa20-4736-b211-d06daa03bff9","messageType":"TargetStageEntered","logLevel":"INFO"}
17:39:35.054  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758375054,"executionId":"ad416b09-aa20-4736-b211-d06daa03bff9","messageType":"ExecutionSucceeded","logLevel":"INFO"}
17:39:35.054  {"resourceArn":"arn:aws:pipes:us-east-1:<account>:pipe/TriggerPipe-ReOiUvaOGV9a","timestamp":1791758375054,"executionId":"ad416b09-aa20-4736-b211-d06daa03bff9","messageType":"TargetStageSucceeded","logLevel":"INFO","payload":""}
```

## 3. Step Functions: every state, its time, input and output

| State | Started | Seconds |
|---|---|---|
| InputShape | 17:36:08 | 0.0 |
| UnwrapBatch | 17:36:08 | 0.0 |
| Ingest | 17:36:08 | 3.8 |
| Accepted | 17:36:12 | 0.0 |
| Investigate | 17:36:12 | 53.8 |
| Route | 17:37:06 | 4.0 |
| Gate | 17:37:10 | 0.0 |
| Fix | 17:37:10 | 50.1 |
| RouteAfterFix | 17:38:00 | 0.2 |
| FixOutcome | 17:38:00 | 0.0 |
| Test | 17:38:00 | 46.8 |
| OpenPr | 17:38:47 | 6.1 |
| Notify | 17:38:53 | 4.6 |
| PullRequestOpened | 17:38:58 | 0.0 |

### Ingest

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  }
}
```

### Investigate

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  }
}
```

### Route

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

### Fix

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

### RouteAfterFix

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

### Test

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

### OpenPr

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

### Notify

Input:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

Output:

```json
{
  "executionId": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168"
  },
  "ingest": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "reason": ""
  },
  "route": {
    "executionId": "exec-d0e8a14f",
    "status": "running",
    "fixAction": "fix_pr_standard_review"
  }
}
```

## 4. Lambda logs (full)

### Ingest: function `SelfHealingPipeline-Ingest4069586C-l6SUIWnsvNVh`, log group `SelfHealingPipeline-IngestLogs7327CBDC-5Q7cV9QIKogV`

```
17:36:09.224  START RequestId: bd3f1815-a923-43c5-91f0-3cdf30c6c8c0 Version: $LATEST
17:36:12.511  {"execution_id": "exec-d0e8a14f", "step": "ingest", "confidence": null, "output": {"outcome": "accepted"}}
17:36:12.511  {"_aws": {"Timestamp": 1791758172511, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 1.687, "execution_id": "exec-d0e8a14f", "Stage": "ingest"}
17:36:12.603  END RequestId: bd3f1815-a923-43c5-91f0-3cdf30c6c8c0
17:36:12.603  REPORT RequestId: bd3f1815-a923-43c5-91f0-3cdf30c6c8c0	Duration: 3377.90 ms	Billed Duration: 3584 ms	Memory Size: 512 MB	Max Memory Used: 109 MB	Init Duration: 205.13 ms
```

### Route: function `SelfHealingPipeline-RouteA67450D2-qyGfx0MdQCGR`, log group `SelfHealingPipeline-RouteLogs174AF25A-PaXJJhBrCfI8`

```
17:37:06.880  START RequestId: 50ff7c42-055c-4600-b9dc-ef2175dc1792 Version: $LATEST
17:37:10.414  END RequestId: 50ff7c42-055c-4600-b9dc-ef2175dc1792
17:37:10.414  REPORT RequestId: 50ff7c42-055c-4600-b9dc-ef2175dc1792	Duration: 3532.87 ms	Billed Duration: 3754 ms	Memory Size: 256 MB	Max Memory Used: 106 MB	Init Duration: 221.04 ms
```

### RouteAfterFix: function `SelfHealingPipeline-RouteA67450D2-qyGfx0MdQCGR`, log group `SelfHealingPipeline-RouteLogs174AF25A-PaXJJhBrCfI8`

```
17:38:00.652  START RequestId: aeb6f361-bf0c-42a3-9a05-ebc9964f6d89 Version: $LATEST
17:38:00.774  END RequestId: aeb6f361-bf0c-42a3-9a05-ebc9964f6d89
17:38:00.774  REPORT RequestId: aeb6f361-bf0c-42a3-9a05-ebc9964f6d89	Duration: 120.87 ms	Billed Duration: 121 ms	Memory Size: 256 MB	Max Memory Used: 106 MB
```

### OpenPr: function `SelfHealingPipeline-OpenPr92F50AD2-XmvMeaOed8P5`, log group `SelfHealingPipeline-OpenPrLogs4AF57F65-5ccozDcsfoi9`

```
17:38:48.031  START RequestId: bead0bb3-dd3f-4265-b8d6-26e48c941949 Version: $LATEST
17:38:53.553  {"execution_id": "exec-d0e8a14f", "step": "pr", "confidence": 82, "output": {"pr": "https://github.com/dharmendradevops11/healer-demo-app/pull/22", "labels": ["healer", "healer: standard-review", "healer: blast-radius-medium", "healer: human-review"]}}
17:38:53.609  {"_aws": {"Timestamp": 1791758333608, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 3.831, "execution_id": "exec-d0e8a14f", "Stage": "pr"}
17:38:53.609  {"_aws": {"Timestamp": 1791758333609, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Outcome"]], "Metrics": [{"Name": "EndToEndSeconds", "Unit": "Seconds"}]}]}, "EndToEndSeconds": 165.5, "execution_id": "exec-d0e8a14f", "Outcome": "pr_opened"}
17:38:53.671  END RequestId: bead0bb3-dd3f-4265-b8d6-26e48c941949
17:38:53.671  REPORT RequestId: bead0bb3-dd3f-4265-b8d6-26e48c941949	Duration: 5638.46 ms	Billed Duration: 5846 ms	Memory Size: 512 MB	Max Memory Used: 109 MB	Init Duration: 207.35 ms
```

### Notify: function `SelfHealingPipeline-Notify29C25B1B-K0M24lTWnT78`, log group `SelfHealingPipeline-NotifyLogsC0ABC89F-a0vm3RfnpCgi`

```
17:38:54.161  START RequestId: 4de2f417-fa69-4eed-9fe3-0995a02d3eca Version: $LATEST
17:38:58.201  {"hop": "notify->sns", "sns_message_id": "8ed07134-04e9-5228-9066-127216ab00d3", "topic": "arn:aws:sns:us-east-1:<account>:SelfHealingState-NotificationTopicEB7A0DF1-yd3dgu1Ec8Sc", "subject": "[WARNING] [Healer] demo-app: Fix ready (82/100)", "attributes": {"escalationTier": "warning", "page": "business_hours_only", "channel": "slack+ticket", "fixAction": "fix_pr_standard_review"}, "message": "Self-Healer: Fix ready\nEscalation: WARNING -> unassigned via slack+ticket (page: business_hours_only)\nRouting: medium confidence x medium blast radius -> fix_pr_standard_review\nService: demo-app\nIssue: AttributeError: 'NoneType' object has no attribute 'name'\nRoot cause: In src/auth.py line 24, get_display_name() attempts to access .name on session.user.profile without checking if profile is None. When new OAuth users login, they have no profile yet (profile=None), causing AttributeError when calling .name on NoneType.\nConfidence: 82/100\nHuman review required: unowned service: it has no named team or on-call rotation in the registry\nHuman review required: new failure pattern: the ledger has too little history for this category\nPR: https://github.com/dharmendradevops11/healer-demo-app/pull/22"}
17:38:58.201  {"_aws": {"Timestamp": 1791758338201, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 0.114, "execution_id": "exec-d0e8a14f", "Stage": "notify"}
17:38:58.259  END RequestId: 4de2f417-fa69-4eed-9fe3-0995a02d3eca
17:38:58.259  REPORT RequestId: 4de2f417-fa69-4eed-9fe3-0995a02d3eca	Duration: 4096.49 ms	Billed Duration: 4358 ms	Memory Size: 256 MB	Max Memory Used: 106 MB	Init Duration: 261.23 ms
```

## 5. Fargate task logs (full) and task details

### Investigate: task `06aeb71c3b794b398508d25b4ce814c1`, stream `investigate/healer-investigate/06aeb71c3b794b398508d25b4ce814c1`

CPU 1024 / memory 2048 MB, exit code **0**, started 17:36:32, stopped 17:37:05, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-TfMMOxbp3uoB/tasks/06aeb71c3b794b398508d25b4ce814c1/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-hegLAe2FOcHF`, stream above.

```
17:36:40.330  {"execution_id": "exec-d0e8a14f", "step": "investigate", "confidence": 82, "output": {"root_cause": "In src/auth.py line 24, get_display_name() attempts to access .name on session.user.profile without checking if profile is None. When new OAuth users login, they have no profile yet (profile=None), ca... [252 chars]", "model_certainty": 95, "signal": 0.7, "history": null, "composite": 82, "decision": {"composite_confidence": 82, "band": "medium", "blast_radius": {"affected_services": 0, "estimated_users": 0, "sensitive_data_at_risk": false, "tier": "medium"}, "tier": "warning", "fix_action": "fix_pr_standard_review", "recipient": "unassigned", "page": "business_hours_only", "channel": "slack+ticket", "owner": "unassigned"}}}
17:36:40.330  {"_aws": {"Timestamp": 1791758200330, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 7.01, "execution_id": "exec-d0e8a14f", "Stage": "investigate"}
17:36:40.412  [investigate] execution exec-d0e8a14f: status=running
```

### Fix: task `b02d486c352a48be99d11c63696008eb`, stream `fix/healer-fix/b02d486c352a48be99d11c63696008eb`

CPU 1024 / memory 2048 MB, exit code **0**, started 17:37:29, stopped 17:37:59, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-TfMMOxbp3uoB/tasks/b02d486c352a48be99d11c63696008eb/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-hegLAe2FOcHF`, stream above.

```
17:37:34.674  {"execution_id": "exec-d0e8a14f", "step": "fix", "confidence": null, "output": {"type": "code-fix", "files": ["src/auth.py"]}}
17:37:35.652  {"execution_id": "exec-d0e8a14f", "step": "remediate", "confidence": null, "output": {"applied": true, "branch": "healer/2026-10-11-fix-src-auth-py-e8a14f"}}
17:37:35.654  {"_aws": {"Timestamp": 1791758255654, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 5.787, "execution_id": "exec-d0e8a14f", "Stage": "fix"}
17:37:35.694  [fix] execution exec-d0e8a14f: status=running
```

### Test: task `bbd2984066d54c119665d59363462c18`, stream `test/healer-test/bbd2984066d54c119665d59363462c18`

CPU 2048 / memory 4096 MB, exit code **0**, started 17:38:19, stopped 17:38:46, role `from the task definition`.

Console: https://us-east-1.console.aws.amazon.com/ecs/v2/clusters/SelfHealingPipeline-ClusterEB0386A7-TfMMOxbp3uoB/tasks/bbd2984066d54c119665d59363462c18/configuration?region=us-east-1

CloudWatch: log group `SelfHealingPipeline-AgentLogs05C568C3-hegLAe2FOcHF`, stream above.

```
17:38:21.228  [test:type_check] pass
17:38:21.228  Success: no issues found in 2 source files
17:38:21.228  [test:unit] pass
17:38:21.228  ...                                                                      [100%]
17:38:21.228  3 passed in 0.01s
17:38:21.228  [test:lint] pass
17:38:21.228  All checks passed!
17:38:21.274  {"execution_id": "exec-d0e8a14f", "step": "test", "confidence": null, "output": {"checks": ["type-check: pass", "unit: pass", "lint: pass"], "passed": true, "output": {"type_check": "Success: no issues found in 2 source files", "unit": "...                                                                      [100%]\n3 passed in 0.01s", "lint": "All checks passed!"}}}
17:38:21.274  {"_aws": {"Timestamp": 1791758301274, "CloudWatchMetrics": [{"Namespace": "SelfHealingPipeline", "Dimensions": [["Stage"]], "Metrics": [{"Name": "StageSeconds", "Unit": "Seconds"}]}]}, "StageSeconds": 1.767, "execution_id": "exec-d0e8a14f", "Stage": "test"}
17:38:21.310  [test] execution exec-d0e8a14f: status=running
```

## 6. Audit trail (S3) and the final state

### `audit/exec-d0e8a14f/step_001_ingest.json`

```json
{
  "execution_id": "exec-d0e8a14f",
  "step_number": 1,
  "timestamp": "2026-10-11T22:36:12.466403+00:00",
  "step_type": "ingest",
  "input": {
    "service": "demo-app",
    "log_lines": 0
  },
  "output": {
    "outcome": "accepted"
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### `audit/exec-d0e8a14f/step_002_investigate.json`

```json
{
  "execution_id": "exec-d0e8a14f",
  "step_number": 2,
  "timestamp": "2026-10-11T22:36:40.254926+00:00",
  "step_type": "investigate",
  "input": {
    "files": [
      "src/auth.py"
    ],
    "degraded": []
  },
  "output": {
    "root_cause": "In src/auth.py line 24, get_display_name() attempts to access .name on session.user.profile without checking if profile is None. When new OAuth users login, they have no profile yet (profile=None), causing AttributeError when calling .name on NoneType.",
    "model_certainty": 95,
    "signal": 0.7,
    "history": null,
    "composite": 82,
    "decision": {
      "composite_confidence": 82,
      "band": "medium",
      "blast_radius": {
        "affected_services": 0,
        "estimated_users": 0,
        "sensitive_data_at_risk": false,
        "tier": "medium"
      },
      "tier": "warning",
      "fix_action": "fix_pr_standard_review",
      "recipient": "unassigned",
      "page": "business_hours_only",
      "channel": "slack+ticket",
      "owner": "unassigned"
    }
  },
  "tool_calls": [],
  "confidence_score": 82
}
```

### `audit/exec-d0e8a14f/step_003_fix.json`

```json
{
  "execution_id": "exec-d0e8a14f",
  "step_number": 3,
  "timestamp": "2026-10-11T22:37:34.627779+00:00",
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

### `audit/exec-d0e8a14f/step_004_remediate.json`

```json
{
  "execution_id": "exec-d0e8a14f",
  "step_number": 4,
  "timestamp": "2026-10-11T22:37:35.621914+00:00",
  "step_type": "remediate",
  "input": {
    "files": [
      "src/auth.py"
    ]
  },
  "output": {
    "applied": true,
    "branch": "healer/2026-10-11-fix-src-auth-py-e8a14f"
  },
  "tool_calls": [],
  "confidence_score": null
}
```

### `audit/exec-d0e8a14f/step_005_test.json`

```json
{
  "execution_id": "exec-d0e8a14f",
  "step_number": 5,
  "timestamp": "2026-10-11T22:38:21.228105+00:00",
  "step_type": "test",
  "input": {
    "branch": "healer/2026-10-11-fix-src-auth-py-e8a14f"
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

### `audit/exec-d0e8a14f/step_006_pr.json`

```json
{
  "execution_id": "exec-d0e8a14f",
  "step_number": 6,
  "timestamp": "2026-10-11T22:38:53.493535+00:00",
  "step_type": "pr",
  "input": {
    "branch": "healer/2026-10-11-fix-src-auth-py-e8a14f"
  },
  "output": {
    "pr": "https://github.com/dharmendradevops11/healer-demo-app/pull/22",
    "labels": [
      "healer",
      "healer: standard-review",
      "healer: blast-radius-medium",
      "healer: human-review"
    ]
  },
  "tool_calls": [],
  "confidence_score": 82
}
```

### Final state `pipeline-state/exec-d0e8a14f/state.json`

```json
{
  "execution_id": "exec-d0e8a14f",
  "incident": {
    "source": "sentry",
    "severity": "high",
    "type": "crash",
    "title": "AttributeError: 'NoneType' object has no attribute 'name'",
    "stackTrace": "AttributeError: 'NoneType' object has no attribute 'name'\nTraceback (most recent call last)\n  File \"src/auth.py\", line 24, in get_display_name",
    "affectedService": "demo-app",
    "cloudwatchLogGroup": "/aws/ecs/demo-app",
    "triggeredAt": "2026-10-11T22:36:08.140342+00:00",
    "sentryIssueUrl": "https://example.sentry.io/issues/1791758168/",
    "sentryIssueId": "1791758168",
    "logs": ""
  },
  "status": "pr_opened",
  "reason": "open_pr: supervised: a human reviews every pull request",
  "log_lines": [],
  "diagnosis": {
    "root_cause_hypothesis": "In src/auth.py line 24, get_display_name() attempts to access .name on session.user.profile without checking if profile is None. When new OAuth users login, they have no profile yet (profile=None), causing AttributeError when calling .name on NoneType.",
    "confidence_score": 95,
    "evidence_summary": "The error message 'AttributeError: NoneType object has no attribute name' directly matches the code pattern at line 24. The User dataclass defines profile as Optional[Profile]=None, and the comment on line 23 explicitly states 'First OAuth login: new users have no profile yet. This line crashes for them.' The type: ignore[union-attr] comment acknowledges the type checker detected this unsafe attribute access.",
    "affected_files": [
      "src/auth.py"
    ],
    "raw_response": "```json\n{\n  \"rootCauseHypothesis\": \"In src/auth.py line 24, get_display_name() attempts to access .name on session.user.profile without checking if profile is None. When new OAuth users login, they have no profile yet (profile=None), causing AttributeError when calling .name on NoneType.\",\n  \"confidenceScore\": 95,\n  \"evidenceSummary\": \"The error message 'AttributeError: NoneType object has no attribute name' directly matches the code pattern at line 24. The User dataclass defines profile as Optional[Profile]=None, and the comment on line 23 explicitly states 'First OAuth login: new users have no profile yet. This line crashes for them.' The type: ignore[union-attr] comment acknowledges the type checker detected this unsafe attribute access.\",\n  \"affectedFiles\": [\n    \"src/auth.py\"\n  ]\n}\n```",
    "fix_strategy": "",
    "reasoning": ""
  },
  "evidence": {
    "log_lines": 0,
    "has_stack_trace": true,
    "files_implied": 1,
    "files_read": 1,
    "has_commit_context": true
  },
  "degraded": [],
  "category": "crash:AttributeError",
  "history": null,
  "signal": 0.7,
  "composite": 82,
  "decision": {
    "composite_confidence": 82,
    "band": "medium",
    "blast_radius": {
      "affected_services": 0,
      "estimated_users": 0,
      "sensitive_data_at_risk": false,
      "tier": "medium"
    },
    "tier": "warning",
    "fix_action": "fix_pr_standard_review",
    "recipient": "unassigned",
    "page": "business_hours_only",
    "channel": "slack+ticket",
    "owner": "unassigned"
  },
  "proposal": {
    "type": "code-fix",
    "diff": "diff --git a/src/auth.py b/src/auth.py\n--- a/src/auth.py\n+++ b/src/auth.py\n@@ -20,7 +20,10 @@ class Session:\n \n \n def get_display_name(session: Session) -> str:\n-    # First OAuth login: new users have no profile yet. This line crashes for them.\n-    return session.user.profile.name.strip()  # type: ignore[union-attr]\n+    # First OAuth login: new users have no profile yet.\n+    if session.user.profile is None:\n+        return \"there\"\n+    return session.user.profile.name.strip()\n \n \n def greet(session: Session) -> str:",
    "affected_files": [
      "src/auth.py"
    ],
    "explanation": "The fix adds a null check before accessing the profile's name attribute. When session.user.profile is None (as it is for new OAuth users on first login), the function now returns the default value \"there\" instead of attempting to access .name on NoneType, which was causing the AttributeError.",
    "raw_response": "```json\n{\n  \"type\": \"code-fix\",\n  \"diff\": \"diff --git a/src/auth.py b/src/auth.py\\n--- a/src/auth.py\\n+++ b/src/auth.py\\n@@ -20,7 +20,10 @@ class Session:\\n \\n \\n def get_display_name(session: Session) -> str:\\n-    # First OAuth login: new users have no profile yet. This line crashes for them.\\n-    return session.user.profile.name.strip()  # type: ignore[union-attr]\\n+    # First OAuth login: new users have no profile yet.\\n+    if session.user.profile is None:\\n+        return \\\"there\\\"\\n+    return session.user.profile.name.strip()\\n \\n \\n def greet(session: Session) -> str:\",\n  \"affectedFiles\": [\"src/auth.py\"],\n  \"explanation\": \"The fix adds a null check before accessing the profile's name attribute. When session.user.profile is None (as it is for new OAuth users on first login), the function now returns the default value \\\"there\\\" instead of attempting to access .name on NoneType, which was causing the AttributeError.\"\n}\n```"
  },
  "plan_action": "open_pr: supervised: a human reviews every pull request",
  "branch": "healer/2026-10-11-fix-src-auth-py-e8a14f",
  "fix_commit": "fe8b12a",
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
    "number": 22,
    "url": "https://github.com/dharmendradevops11/healer-demo-app/pull/22",
    "title": "[HEALER] fix: AttributeError: 'NoneType' object has no attribute 'name'",
    "branch": "healer/2026-10-11-fix-src-auth-py-e8a14f",
    "labels": [
      "healer",
      "healer: standard-review",
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
    "audit/exec-d0e8a14f/step_001_ingest.json",
    "audit/exec-d0e8a14f/step_002_investigate.json",
    "audit/exec-d0e8a14f/step_003_fix.json",
    "audit/exec-d0e8a14f/step_004_remediate.json",
    "audit/exec-d0e8a14f/step_005_test.json",
    "audit/exec-d0e8a14f/step_006_pr.json"
  ]
}
```

