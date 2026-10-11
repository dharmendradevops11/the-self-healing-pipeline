# Contributing

Thanks for experimenting with the book. A few ground rules, most of them from the book itself.

## The pipeline never merges

There is no auto-merge code in this repository and a pull request that adds some will be declined. That is an intentional
design choice, not a missing feature: the reviewer applies context that lives outside the source files, someone accountable makes
a deliberate choice, and a human is the only reliable detector of systematic model error (Chapter 18). If you later want
auto-merge for a narrow class of incidents, earn it with twelve months of PR-only data first.

## Follow the book

[docs/BOOK_SPEC.md](docs/BOOK_SPEC.md) is the contract. A change that moves behaviour away from the book needs a line in
[docs/DECISIONS.md](docs/DECISIONS.md) saying why. The files under `chapters/` and `companion_code/` are the printed listings and
are not edited.

## Set up and check

```bash
make venv
make lint test
make local-up && make local-test   # optional, needs Docker
```

New behaviour needs a test. Tests never reach AWS: they use moto, or LocalStack for the `integration` marker.

## Never commit a secret

No tokens, keys or `.env` files. The allowlist denies them to the pipeline for the same reason.
