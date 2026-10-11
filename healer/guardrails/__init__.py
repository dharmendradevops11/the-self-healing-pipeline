"""Guardrails.

Prompt sanitizer, secret scrubber, path allowlist, circuit breakers. (Ch 3, 7, 11, 17).
"""

from healer.guardrails.allowlist import (
    FORBIDDEN_PATH_PATTERNS,
    SAFE_PATH_PREFIXES,
    is_path_remediable,
    validate_fix_paths,
)
from healer.guardrails.classifier import Verdict, classify_payload
from healer.guardrails.delimiters import build_secure_prompt, wrap_untrusted
from healer.guardrails.patch_policy import PatchPolicy
from healer.guardrails.phases import Phase, PhaseController, PRThrottle
from healer.guardrails.sanitizer import sanitize_basic, sanitize_for_prompt
from healer.guardrails.scrubber import SecretScrubber, install_scrubber

__all__ = [
    "FORBIDDEN_PATH_PATTERNS",
    "SAFE_PATH_PREFIXES",
    "PRThrottle",
    "PatchPolicy",
    "Phase",
    "PhaseController",
    "SecretScrubber",
    "Verdict",
    "build_secure_prompt",
    "classify_payload",
    "install_scrubber",
    "is_path_remediable",
    "sanitize_basic",
    "sanitize_for_prompt",
    "validate_fix_paths",
    "wrap_untrusted",
]
