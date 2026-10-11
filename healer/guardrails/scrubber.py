"""Keep secrets out of the logs (Chapter 11, "Rotation Without Breaking the Pipeline")."""

from __future__ import annotations

import logging
import re


class SecretScrubber(logging.Filter):
    """Logging filter to scrub GitHub and AWS tokens from application logs.

    Fails closed: if scrubbing itself breaks, the record is redacted instead of emitted.
    (The Appendix D copy in companion_code fails open and lets the record through.)
    """

    PATTERNS = [
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),  # GitHub PAT
        re.compile(r"aws_access_key_id=[a-zA-Z0-9]{20}", re.IGNORECASE),
        re.compile(r"aws_secret_access_key=[a-zA-Z0-9/+=]{40}", re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                for pattern in self.PATTERNS:
                    record.msg = pattern.sub("[SCRUBBED_SECRET]", record.msg)
            return True
        except Exception:
            # Fail closed: never emit a record we could not scrub.
            record.msg = "[LOG REDACTED: secret scrubbing failed]"
            record.args = ()
            logging.getLogger("secret_scrubber").error(
                "SecretScrubber failed on a log record; record was redacted"
            )
            return True


def install_scrubber(logger: logging.Logger | None = None) -> SecretScrubber:
    """Attach the scrubber to every handler of a logger (the root logger by default)."""
    scrubber = SecretScrubber()
    target = logger or logging.getLogger()
    for handler in target.handlers:
        handler.addFilter(scrubber)
    return scrubber


_ARN = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:\d*:[^\s\"',}\]]+")
_ACCOUNT = re.compile(r"(?<!\d)\d{12}(?!\d)")


def redact_internal_ids(text: str) -> str:
    """Take AWS ARNs and account numbers out of text that is going to a chat channel.

    They are not credentials, but a failure message copied into Slack should not hand out the
    account number, role names and secret names. The full error stays in the logs.
    """
    return _ACCOUNT.sub("[account]", _ARN.sub("[arn]", text))


def summarise_error(error: str, limit: int = 300) -> str:
    """The error a person needs: type and message, without the stack, ids or ARNs."""
    import json

    try:
        data = json.loads(error)
        if isinstance(data, dict) and (data.get("errorType") or data.get("errorMessage")):
            error = f"{data.get('errorType', 'Error')}: {data.get('errorMessage', '')}"
    except (ValueError, TypeError):
        pass
    return redact_internal_ids(scrub_sensitive_data(error))[:limit]


def scrub_sensitive_data(text: str) -> str:
    """Scrub one string, for the decision trail (Chapter 13 calls this before writing evidence).

    Fails closed like the logging filter: a string that cannot be scrubbed is not returned.
    """
    try:
        for pattern in SecretScrubber.PATTERNS:
            text = pattern.sub("[SCRUBBED_SECRET]", text)
        return text
    except Exception:  # noqa: BLE001
        return "[REDACTED: secret scrubbing failed]"
