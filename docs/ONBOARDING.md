# Adding a service (Chapter 14)

No interpretation required. Follow in order.

1. **Name an owner and an on-call** for the Sentry project. Unowned alerts are how the checkout test died in Chapter 1.
2. **Register the service** in the blast-radius registry (`healer:service_registry`, or `scenarios/registry.json` locally):
   ```json
   "checkout-api": {"owner": "payments-team", "oncall": "payments-oncall",
                    "estimated_users": 120000, "handles_pii_or_payment": true, "dependents": ["orders"]}
   ```
   Payment or PII, or more than 500,000 users, makes the tier **critical**. A service missing from the registry gets
   `healer:unknown_service_tier` (default medium), never zero.
3. **Check the allowlist** (`config/allowlist.yaml`): allowed paths for this repository's layout, and the denied paths that
   must stay denied (secrets, infrastructure, migrations, Dockerfile). Deny always wins.
4. **Point Sentry's webhook** at the `WebhookUrl` output and set the signing secret.
5. **Start in shadow mode** for two to four weeks ([shadow-mode.md](shadow-mode.md)). Review the shadow records.
6. **Move to supervised** on this one service, business hours, three PRs a day.
7. **Write down** which failure types always go to a human (migrations, anything security-tagged), who reviews fast, and what
   the confidence numbers mean in practice. The calibration knowledge matters more than the code.
