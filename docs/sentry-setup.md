# Connecting Sentry (verified on real AWS, 2026-10-09)

The pipeline only **receives** alerts. It never calls Sentry's API, so no Sentry auth token is needed. What it needs is the
integration's **Client Secret**, which signs every webhook.

## 1. Create an internal integration (Sentry: Settings, Developer Settings, Custom Integrations)

| Field | Value |
|---|---|
| Name | `self-healing-pipeline` |
| Webhook URL | the `WebhookUrl` output of the stack (`.../prod/webhook`) |
| Alert Rule Action | **on** |
| Webhooks (events) | **leave all unticked** |
| Permissions | `Event: Read` only |

**Leave the event subscriptions off.** An integration that also subscribes to `issue` events sends a second webhook for the same
error (found on real AWS: one error produced two webhooks and two pipeline runs). The alert rule's action is what should call
the webhook: it carries the full stack trace.

## 2. Store the Client Secret in AWS (never in a file or in chat)

```bash
read -sp "Sentry client secret: " SENTRY_SECRET; echo ""
aws secretsmanager put-secret-value --secret-id self-healing-pipeline/webhook --secret-string "$SENTRY_SECRET"
unset SENTRY_SECRET
```

The Lambda reads the secret each time it runs, so nothing needs redeploying.

## 3. Create the alert rule (Sentry: Alerts, Create Alert, Issues)

- **When:** *a new issue is created* and **nothing else**. Sentry's newer alert page can pre-select *issue resolved*, *reappeared*
  and *regression* as well. With those, resolving an issue in Sentry starts an investigation.
- **Then:** *Send a notification via `self-healing-pipeline`*.

## 4. Tell the pipeline which service an error belongs to

The service name decides the blast radius (the registry), the log group (`/aws/ecs/<service>`) and the owner. For an alert-rule
event the pipeline uses, in order: the event's **`service` tag**, `server_name`, the project name, the project id. Set
`sentry_sdk.set_tag("service", "checkout-api")` (or `server_name`) in your app so it matches a key in `healer:service_registry`.

## What the pipeline does with duplicates

Sentry can deliver one error more than once. INGEST records the Sentry issue id (a conditional write, 24 hours) and a second
delivery ends as `duplicate` before it can open a second pull request.

## Check it

Send a test error to the project (its DSN is under *Settings, Client Keys*), then read the webhook Lambda's log. You should see
`{"hop": "webhook->received", "action": "triggered", ...}` followed by `{"hop": "webhook->sns", ...}`, and one new Step Functions
execution. [viewing-logs.md](viewing-logs.md) shows where each hop's evidence is.
