# Scenarios

Practice material for the whole pipeline. Everything here is data you can change.

| Path | What it is |
|---|---|
| `demo-app/` | A tiny Python app with one deliberate bug. One test fails on purpose. |
| `incidents/null-profile.json` | The error event that bug produces, with log lines. |
| `replays/null-profile.json` | Canned model answers (a diagnosis, then a fix). The offline "model". |
| `registry.json` | A service registry for the blast-radius step. A small internal service. |
| `registry-payments.json` | The same service, but marked as handling payment data. |

Try changing `registry.json` to `registry-payments.json`, or `confidenceScore` in the replay file, and watch the
pipeline's decision change. Run `make demo`.
