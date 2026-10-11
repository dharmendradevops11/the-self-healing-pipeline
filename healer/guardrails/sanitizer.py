"""Prompt sanitizing for untrusted text (Chapters 3 and 11).

Error messages, stack traces and log lines are attacker-influenced input. Two versions live
here. `sanitize_basic` is the two-regex filter printed in Chapter 3. `sanitize_for_prompt` is
the Chapter 11 version: it also strips code-fence escapes and role markers, and breaks the
obvious injection phrasings.

Chapter 11 is explicit about the limit: regular expressions are a fragile, easily bypassed
layer. Encoding, translation or paraphrase gets past a blocklist. Never treat this as your
primary control. It sits under delimiters, a classifier, a sandbox and hard IAM limits.
"""

from __future__ import annotations

import re

MAX_CHARS = 2000
REDACTION = "[SANITIZED]"


def sanitize_basic(raw_text: str) -> str:
    """The Chapter 3 listing, as printed."""
    # Strip anything that looks like an instruction
    text = re.sub(
        r"(ignore|disregard|forget).*(previous|prior|above)",
        REDACTION,
        raw_text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(you are|act as|pretend to be)", REDACTION, text, flags=re.IGNORECASE)
    # The model doesn't need 10k chars of stack trace
    return text[:MAX_CHARS]


_FENCE = re.compile(r"`{3,}|~{3,}")
_ROLE_MARKER = re.compile(r"(?im)^[ \t]*(system|assistant|human|user|developer)[ \t]*:")
_INJECTION_PATTERNS = [
    re.compile(
        r"\b(ignore|disregard|forget|override)\b[^.\n]*\b(previous|prior|above|earlier|instructions?|rules?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(you are now|you must now|from now on you|act as|pretend to be)\b", re.IGNORECASE
    ),
    re.compile(r"\b(system|developer|hidden|initial)[ _-]+prompt\b", re.IGNORECASE),
    re.compile(r"\bnew (directive|instructions?|rules?)\b", re.IGNORECASE),
    re.compile(r"\b(debug|developer|admin|god) mode\b", re.IGNORECASE),
]


def sanitize_for_prompt(raw_text: str) -> str:
    """Strip code-fence escapes and role markers, break obvious injection patterns, cap length."""
    text = _FENCE.sub("", raw_text)
    text = _ROLE_MARKER.sub(REDACTION + ":", text)
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub(REDACTION, text)
    return text[:MAX_CHARS]
