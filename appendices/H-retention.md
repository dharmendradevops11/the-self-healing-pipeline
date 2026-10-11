# Appendix H: Data-retention and governance

| Book | Here |
|---|---|
| Raw telemetry passes through `SecretScrubber` before storage. A scrubber is a control, not a guarantee | `healer/guardrails/scrubber.py`; the audit logger stores sanitised prompts and scrubbed text |
| Audit records (S3): **90 days** under **GOVERNANCE**-mode Object Lock; lifecycle then prunes them | `healer:audit_retention_days` (default 90), `healer:audit_object_lock`; lifecycle rule `prune-audit-records` |
| Staging heap dumps cleared after **7 days** | lifecycle rule `expire-heap-dumps` on the state bucket (`heap-dumps/`) |
| Exclusion matrix: prompts, source files and completions never in plaintext log streams or persistent variables | the scrubber filter on every handler; secrets are read at use and never held in environment variables |

Object Lock is **off** by default so a reader's experiment can be torn down completely. Turn it on for anything real, and never
bypass it just to clean up ([../docs/teardown.md](../docs/teardown.md)).
