# Appendix B: Public incident source notes

- **SolarWinds (2020)**: malicious code injected into the build pipeline's source files, bypassing perimeter controls.
- **CircleCI (January 2023)**: credentials stolen from an engineer's laptop; why keys rotate and secrets stay out of CI logs.
- **Knight Capital (2012)**: about $440 million lost in roughly 45 minutes, from un-deactivated legacy code and no automated
  guardrails.

The repository's answers to them: no secret in an environment variable or a log (`healer/guardrails/secrets.py`,
`scrubber.py`), a path allowlist and patch limits before any change (`allowlist.py`, `patch_policy.py`), and a daily cap plus a
human merge so a runaway automation cannot ship (`phases.py`).
