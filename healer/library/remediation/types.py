"""Shared types for the remediation library (Chapter 7)."""

from __future__ import annotations

from enum import Enum


class RemediationResult(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"  # a precondition was not met, or this was a dry run
    FAILED = "failed"
    BLOCKED = "blocked"  # a human said no, or nobody answered


class TransientError(Exception):
    """A failure worth retrying: a timeout, a throttle, a brief outage."""


class RemediationBlockedError(Exception):
    """A proposed fix touches something automation must never touch."""


class InvalidRemediationError(Exception):
    """Remediation selection produced an action outside the valid set."""
