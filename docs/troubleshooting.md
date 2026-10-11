# Troubleshooting (Chapter 17, "Living With It")

## AccessDeniedException on GetSecretValue, though the IAM policy looks right
It is almost never Secrets Manager. It is **KMS**. Secrets Manager decrypts under the caller's role, and a missing
`kms:Decrypt` surfaces as a Secrets Manager error that never mentions KMS. CloudFormation only checks that the secret
exists, so the stack deploys clean and fails on first use. If you encrypt with a customer-managed key, grant
`kms:Decrypt` and `kms:DescribeKey` on it next to `secretsmanager:GetSecretValue`. This stack uses the AWS-managed
key, where the grant is automatic.

## Webhook signature validation fails though the secret is right
Encoding, every time. API Gateway's proxy integration may deliver the body base64-encoded. GitHub and Sentry sign the **raw
bytes**, so the handler must hash the literal body, not a re-serialised one. `healer/ingest/webhook.py` honours
`isBase64Encoded`, caps the payload at 5 MB and compares in constant time. Also check the replay window: a request older than
300 seconds is rejected, so a skewed clock looks like a bad signature.

## The wrong architecture
Pip on an Apple Silicon Mac fetches ARM binaries, Lambda runs x86_64, and the function crashes on every invocation with
"cannot import". Build for the target: `docker build --platform linux/amd64 …`.

## Costs spike with no obvious cause
Check Bedrock's input and output token metrics first. A healthy execution costs roughly $0.70 to $2.20 end to end. An
input jump usually means the failure log format changed and you now ship ten times the context. An output jump means the
temperature crept up or debug logging was left on for a function whose logs feed the model.

## Nothing happens after an alert
Walk the path: API Gateway → webhook Lambda logs → SNS → SQS (and its dead-letter queue) → the pipe → the Step Functions
execution list. Then the rate limiter: three investigations per service per hour, and the daily PR cap (3). Both are
silent by design; the audit bucket records the reason.

## "Needs a human" for everything
Expected at first. With no ledger history the composite score leans on the model, and a first-seen failure category gets the
`healer: human-review` label. See [BOOK_SPEC.md](BOOK_SPEC.md) §4.
