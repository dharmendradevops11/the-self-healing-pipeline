# Appendix D: Reference implementation index

The six modules the book lists under `companion_code/`, kept exactly as printed, and where the same idea lives in the pipeline.

| Book file (`companion_code/`) | Purpose | In the pipeline |
|---|---|---|
| `anomaly_detector.py` | Robust EMA and MAD-based anomaly scoring | `healer/library/statistics.py` |
| `rate_limiter.py` | DynamoDB atomic-transaction alert throttling | `healer/ingest/rate_limiter.py`, `alert_limiter.py` |
| `decision_tree.py` | SRE heuristics and auto-remediation routing | `healer/library/remediation/` |
| `signature_validator.py` | API Gateway webhook signature validation | `healer/ingest/webhook.py` |
| `failure_observer.py` | Asynchronous build failure pattern monitoring | `healer/library/build_failure.py` |
| `secret_scrubber.py` | Log scrubbing for tokens and secrets (Ch. 11) | `healer/guardrails/scrubber.py` (fails closed) |

`companion_code/` has its own tests and requirements and is not edited. See [../docs/book-to-code.md](../docs/book-to-code.md)
for the chapter-by-chapter map.
