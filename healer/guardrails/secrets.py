"""Secrets: never in environment variables (Chapter 11).

Fetch at invocation time, scoped to the secret's name, and rotate without a gap.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


def get_secret(secrets_client: Any, secret_id: str, key: str | None = None) -> str:
    """Read a secret at the moment you need it.

    The book stores `{"token": "..."}` and reads `.token`. A bare string works too, so a secret
    created either way is accepted. Pass `key` to pick a field from a JSON secret.
    """
    value = secrets_client.get_secret_value(SecretId=secret_id)["SecretString"]
    if key is None:
        return str(value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return str(value)
    return str(parsed[key]) if isinstance(parsed, dict) and key in parsed else str(value)


def get_github_token(secrets_client: Any, secret_id: str = "prod/github/healer-pat") -> str:
    return get_secret(secrets_client, secret_id, key="token")


def rotate_secret(
    event: dict[str, Any],
    secrets_client: Any,
    create_token: Callable[[], str],
    validate_token: Callable[[str], None],
    revoke_token: Callable[[str], None],
) -> str:
    """The three-step rotation from the chapter: createSecret, testSecret, finishSecret.

    The old token stays valid until the new one is proven, so there is never a moment when the
    pipeline has no working credential. `validate_token` must raise if the token does not work.

    The book's listing reads the pending token with a plain getSecret(), which returns the
    current version, so testSecret and finishSecret would never find `pending`. Secrets Manager
    keeps the pending value under the AWSPENDING stage, so that is where it is read from here.
    """
    secret_id, step = event["SecretId"], event["Step"]

    def read(stage: str = "AWSCURRENT") -> dict[str, str]:
        parsed: dict[str, str] = json.loads(
            secrets_client.get_secret_value(SecretId=secret_id, VersionStage=stage)["SecretString"]
        )
        return parsed

    def put(value: dict[str, str], stage: str) -> None:
        secrets_client.put_secret_value(
            SecretId=secret_id, SecretString=json.dumps(value), VersionStages=[stage]
        )

    if step == "createSecret":
        current = read()["current"]
        put({"current": current, "pending": create_token()}, "AWSPENDING")
    elif step == "testSecret":
        validate_token(read("AWSPENDING")["pending"])
    elif step == "finishSecret":
        data = read("AWSPENDING")
        revoke_token(data["current"])
        put({"current": data["pending"]}, "AWSCURRENT")
    else:
        raise ValueError(f"unknown rotation step {step!r}")
    return step
