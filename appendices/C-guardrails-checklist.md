# Appendix C: Security and guardrails checklist

Each box from the book, with where this repository enforces it and the test that proves it.

| Box | Enforced by | Test |
|---|---|---|
| **Delimiters active.** Untrusted input wrapped in distinct XML tags and passed through `sanitizeForPrompt()` | `healer/guardrails/delimiters.py`, `sanitize_for_prompt` in `sanitizer.py`; `diagnose.py` fences telemetry | `tests/unit/test_chapter11.py` |
| **Ephemeral sandboxed execution.** Generated fixes run only in ephemeral, least-privileged sandboxes, egress off | Fargate tasks are ephemeral and own least-privilege roles (`Healer-Test-Role` has no model access). 🟡 **Egress is not disabled**: the FIX and TEST tasks must reach GitHub, and the stack uses public subnets with no NAT to avoid its cost. For stricter isolation, put the TEST task in an isolated subnet with a VPC endpoint or an egress proxy | `tests/unit/test_infra.py` |
| **Branch guardrails.** `healer/*` branch-only writes; human review before `main` | `apply_remediation` creates `healer/…` only; no merge code exists | `tests/unit/test_chapter02.py`, `test_pipeline.py` |
| **Secrets scrubbed.** `SecretScrubber` attached to all stdout/stderr logging | `healer/guardrails/scrubber.py` (`install_scrubber`, fails closed) | `tests/unit/test_chapter11.py` |
