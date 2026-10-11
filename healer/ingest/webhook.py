"""Webhook validation and timing attacks (Chapter 11).

Four rules, each one a real way to get this wrong:
  1. Fail closed. No secret configured means reject everything, never accept everything.
  2. Compare in constant time. A plain `!=` short-circuits and leaks how much of a guess was right.
  3. Reject replays. A valid signature on an old payload is still an attack.
  4. Survive rotation. Accept the previous secret for an overlap window after you rotate.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024
MAX_AGE_SECONDS = 300  # "reject anything older than a few minutes"
ROTATION_OVERLAP_SECONDS = 24 * 3600


def validate_webhook(payload: str | bytes, signature: str, secret: str | bytes) -> bool:
    """HMAC-SHA256 over the raw body, compared in constant time. False on anything unexpected."""
    if not secret:
        return False  # fail closed, not open
    body = payload.encode("utf-8") if isinstance(payload, str) else payload
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    expected = hmac.new(key, body, hashlib.sha256).digest()
    try:
        provided = bytes.fromhex((signature or "").removeprefix("sha256="))
    except ValueError:
        return False
    # compare_digest is constant-time and, unlike Node's timingSafeEqual, does not raise when
    # the lengths differ, so a short signature cannot turn a failed check into an exception.
    return hmac.compare_digest(provided, expected)


def validate_with_rotation(
    payload: str | bytes,
    signature: str,
    current_secret: str | bytes,
    previous_secret: str | bytes | None = None,
    rotated_at: float | None = None,
    now: float | None = None,
) -> bool:
    """Validate against the current secret, then the previous one inside the overlap window.

    Without the overlap, every webhook sent between rotating your secret and updating the
    sender's configuration is rejected.
    """
    if validate_webhook(payload, signature, current_secret):
        return True
    if previous_secret and rotated_at is not None:
        moment = time.time() if now is None else now
        if moment - rotated_at <= ROTATION_OVERLAP_SECONDS:
            return validate_webhook(payload, signature, previous_secret)
    return False


def is_fresh(
    payload_timestamp: float, now: float | None = None, max_age: int = MAX_AGE_SECONDS
) -> bool:
    """Replay protection: the payload's own timestamp must be recent, and not from the future."""
    moment = time.time() if now is None else now
    return -60 <= moment - payload_timestamp <= max_age  # 60s of clock skew either way


@dataclass(frozen=True)
class WebhookResult:
    accepted: bool
    reason: str
    status_code: int
    payload: dict[str, Any] | None = None


def authenticate_webhook(
    event: dict[str, Any],
    signature: str,
    current_secret: str | bytes,
    previous_secret: str | bytes | None = None,
    rotated_at: float | None = None,
    timestamp_field: str = "timestamp",
    now: float | None = None,
    timestamp: float | None = None,
) -> WebhookResult:
    """Everything the ingest Lambda checks before it believes a webhook.

    `event` is an API Gateway proxy event: a "body" string and optional "isBase64Encoded".
    The payload is parsed only after the signature has been verified. Pass `timestamp` when the
    sender stamps it in a header (Sentry sends `Sentry-Hook-Timestamp`) instead of in the body.
    """
    if not isinstance(event, dict) or "body" not in event:
        return WebhookResult(False, "missing or malformed body", 400)
    body = event["body"]
    try:
        raw = (
            base64.b64decode(body, validate=True)
            if event.get("isBase64Encoded")
            else str(body).encode("utf-8")
        )
    except (binascii.Error, ValueError):
        return WebhookResult(False, "body is not valid base64", 400)
    if len(raw) > MAX_PAYLOAD_BYTES:
        return WebhookResult(False, "payload too large", 413)

    if not validate_with_rotation(raw, signature, current_secret, previous_secret, rotated_at, now):
        return WebhookResult(False, "invalid signature", 401)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return WebhookResult(False, "body is not JSON", 400)

    stamp = (
        timestamp
        if timestamp is not None
        else (payload.get(timestamp_field) if isinstance(payload, dict) else None)
    )
    if not isinstance(stamp, int | float) or not is_fresh(float(stamp), now):
        return WebhookResult(False, "stale or missing timestamp (possible replay)", 401)

    return WebhookResult(True, "ok", 200, payload)


def validate_signature(
    event: dict[str, Any], secret: bytes, github_signature: str
) -> dict[str, Any]:
    """Validate a GitHub webhook HMAC-SHA256 signature on a Lambda proxy event (Chapter 17).

    Returns an API Gateway style response. Unlike the printed listing, the size limit is applied
    to the decoded bytes, not to the length of the base64 text.
    """
    if not event or not isinstance(event, dict) or "body" not in event:
        return {"statusCode": 400, "body": "Bad Request"}
    try:
        raw = (
            base64.b64decode(event["body"], validate=True)
            if event.get("isBase64Encoded", False)
            else str(event["body"]).encode("utf-8")
        )
        if len(raw) > MAX_PAYLOAD_BYTES:
            return {"statusCode": 413, "body": "Payload Too Large"}
        if not github_signature or not github_signature.startswith("sha256="):
            return {"statusCode": 401, "body": "Unauthorized"}
        if not validate_webhook(raw, github_signature, secret):
            return {"statusCode": 401, "body": "Unauthorized"}
        return {"statusCode": 200, "body": "OK"}
    except (binascii.Error, ValueError):
        return {"statusCode": 400, "body": "Bad Request"}
    except Exception:
        return {"statusCode": 500, "body": "Internal Server Error"}
