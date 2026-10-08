# companion_code

Standalone Python reference implementations from the book (Appendix D), plus a correlation module. They illustrate the ideas in the chapters and are not imported by the TypeScript pipeline in `infrastructure/`.

| Module | Purpose |
|---|---|
| `anomaly_detector.py` | EMA trend plus MAD scoring for metric anomalies |
| `rate_limiter.py` | Atomic per-service throttling with DynamoDB conditional writes |
| `decision_tree.py` | Maps a failure signature and confidence to a remediation |
| `signature_validator.py` | Constant-time HMAC-SHA256 webhook validation |
| `secret_scrubber.py` | Logging filter that redacts GitHub and AWS secrets |
| `failure_observer.py` | Async build-failure pattern observer with timeouts |
| `correlation_engine.py` | Lagged correlation between events and metrics |

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Notes

- `detect_anomalies_ema` scores each point against an exponential moving average that the spike itself pulls upward, so the points right after a spike can also be flagged. Lower `alpha` to make the trend slower to follow a spike, or raise `threshold_std` to be stricter.
- `rate_limiter.py` uses an example table name (`remediation_rate_limits`) and needs AWS credentials and that table to exist. The tests mock DynamoDB.
