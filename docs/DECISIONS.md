# Decisions

Short, dated, with what was rejected and why (Chapter 14's `DECISIONS.md`).

## 2026-10-09 · Follow the published book, and say where the book disagrees with itself
The book is published, so the repository is its companion, not a redesign. [BOOK_SPEC.md](BOOK_SPEC.md) lists what the book
promises and where it contradicts itself. Where it does, the prose wins over the figure, and the figure's intent is kept too.

## 2026-10-09 · Below the fix threshold: an investigation-only PR *and* a message
The prose (Ch. 1, 2, 12, 14, 16, 18) says a PR containing `HEALER_REPORT.md` and no source change. Figure 2.1 shows
"Escalate / Slack". We do both: the PR carries the evidence, the message makes sure a person sees it. *Rejected:* message
only (loses the durable record the PR gives); PR only (an unread PR is not an escalation).

## 2026-10-09 · Python and CDK, not the TypeScript and CloudFormation in Chapter 18's prose
Appendix E and Chapter 17 fix the stack: Python 3.11, CDK 2.138+, LocalStack 3.4+, boto3 1.34. Every listing is Python. The
architecture (seven stages, S3 state bus, Step Functions, atomic rate limiting, allowlist, PR-only) is unchanged.

## 2026-10-09 · S3 as the state bus, not a DynamoDB coordination record
Chapter 14 says coordination belongs in DynamoDB with a consistent read, because polling S3 races. We do not poll: Step
Functions runs each task to completion (`.sync`) before the next state, and passes only the execution ID. There is no
read-before-write window to race on, so there is nothing for a coordination record to guard. *Revisit* if a stage is ever
launched asynchronously.

## 2026-10-09 · Two buckets
Chapter 17's teardown names an audit bucket (Object Lock) and a separate state bucket. State is disposable; the audit trail
must never be. Bucket names carry the account id because S3 names are global.

## 2026-10-09 · The webhook is a zip Lambda; the Dockerfile is optional
Chapter 17 builds a container for the webhook receiver. The handler needs only boto3 and PyYAML, so CDK bundles it as a zip
(well under Lambda's limit). The Dockerfile exists for readers who want the image route.

## 2026-10-09 · A deterministic replay model for local runs
A reader experimenting with the book should get the same answer every time and pay nothing. `ReplayProvider` returns a
recorded diagnosis. `--llm bedrock` switches to a real model.

## 2026-10-09 · The audit trail stores sanitised prompts
Chapter 8 stores raw prompts; Chapters 11 and 18 say to sanitise and scrub. A prompt can contain a customer's data, so the
sanitised prompt and scrubbed response are stored.

## 2026-10-09 · Rate-limited alerts are dropped, not queued
Chapter 2's printed limiter returns False and the comment says "drop the event". Chapters 16 and 18 say the limiter "queues"
a storm. The listing is the specification: a dropped alert is written to the audit trail with its reason. Queueing would need a
delay queue and a retry budget, and it would let a storm reappear an hour later. Revisit if you lose alerts you wanted.

## 2026-10-09 · A PCI-scoped service is investigated, never fixed
Chapter 11: PCI DSS 6.2.3 and 6.2.4 require review before release, and an autonomous fix bypasses it. Tag a service
`pci_scoped` in the registry and the matrix result is forced to `investigation_only`, at any confidence.

## 2026-10-09 · Telemetry is CloudWatch Embedded Metric Format on stdout
Per-stage duration and end-to-end time need no extra permission, no PutMetricData call and no sidecar. One execution id is on
every line, which is the single trace id Chapter 14 asks for.
