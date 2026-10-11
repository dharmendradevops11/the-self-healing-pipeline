# What the audit trail keeps

One answer to "is the model's prompt stored?", so the README, `docs/BOOK_SPEC.md` and the code agree.

| Question | Answer |
|---|---|
| What is written | One JSON file per pipeline step: `audit/<execution_id>/step_NNN_<step>.json` (`healer/ledger/audit.py`). Each holds the step's **input**, **output**, tool calls and confidence. |
| Is the raw prompt stored | **No.** What is stored is the *sanitised* input and the *scrubbed* output of the step (decision D5 in `docs/BOOK_SPEC.md`). The prompt and response text sent to the model are not archived verbatim. |
| What can still be in it | A scrubbed excerpt of an error message, stack-trace file names, a diagnosis and a diff summary. Treat it as sensitive: source details can appear in these fields even after scrubbing. |
| Scrubbing | `healer/guardrails/scrubber.py` removes secrets and internal identifiers before anything is written. It is pattern-based, so it cannot promise to catch every secret. |
| Who can read it | The pipeline's Lambda roles get read and write on the bucket (`infra/pipeline_stack.py`), and the Fargate task roles are scoped per task. Everyone else needs access you grant yourself. Review these grants before you deploy. |
| How long | `healer:audit_retention_days`, default **90**. With `healer:audit_object_lock=true` the bucket uses **Governance** mode: objects cannot be deleted before expiry without a deliberate bypass permission. After the window a lifecycle rule deletes them. |
| Teardown | `scripts/teardown.sh` never bypasses Object Lock. A locked audit bucket is kept until retention expires. |

If your data policy forbids source details in logs, shorten the retention window and review `healer/guardrails/scrubber.py`
before you deploy.
