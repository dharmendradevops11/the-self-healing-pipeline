"""The path allowlist (Chapter 2, "Safe, Reversible, Auditable").

Source code gets remediated. Infrastructure definitions, CI configuration, database
migrations and deploy scripts never do. The boundary is enforced before any diff gets near
`git apply`, not left to the model's good manners.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

SAFE_PATH_PREFIXES = ["src/", "lib/", "app/", "packages/"]

FORBIDDEN_PATH_PATTERNS = [
    r"^infrastructure/",
    r"^\.github/",
    r"(^|/)migrations/",
    r"(^|/)Dockerfile$",
    r"\.ya?ml$",
    r"\.sh$",
]


# Chapter 7's version of the lists is wider than Chapter 2's: six safe prefixes and the .husky
# hooks directory. The two chapters differ, so both sets are kept and either can be passed in.
EXTENDED_SAFE_PATH_PREFIXES = ["src/", "lib/", "app/", "packages/", "server/", "api/"]
EXTENDED_FORBIDDEN_PATH_PATTERNS = [
    r"^infrastructure/",
    r"^\.github/",
    r"^\.husky/",
    r"(^|/)migrations/",
    r"(^|/)Dockerfile$",
    r"\.ya?ml$",
    r"\.sh$",
]


def _is_inside_repo(file_path: str) -> bool:
    """False for absolute paths, `..` segments, backslashes, NUL bytes and `./` detours."""
    if not file_path or "\x00" in file_path or "\\" in file_path or file_path.startswith("/"):
        return False
    parts = file_path.split("/")
    return ".." not in parts and "." not in parts and "" not in parts


def check_path(
    file_path: str, safe_prefixes: Iterable[str], forbidden_patterns: Iterable[str]
) -> str | None:
    """The one policy. Returns why a path is refused, or None when automation may touch it."""
    if not _is_inside_repo(file_path):
        return f"path escapes the repository: {file_path!r}"
    if any(re.search(pattern, file_path) for pattern in forbidden_patterns):
        return f"Fix touches forbidden path: {file_path}"
    if not any(file_path.startswith(prefix) for prefix in safe_prefixes):
        return f"Fix touches path outside allowlist: {file_path}"
    return None


def is_path_remediable(
    file_path: str,
    safe_prefixes: Iterable[str] = SAFE_PATH_PREFIXES,
    forbidden_patterns: Iterable[str] = FORBIDDEN_PATH_PATTERNS,
) -> bool:
    """True only if the path is under a safe prefix and matches no forbidden pattern."""
    return check_path(file_path, list(safe_prefixes), list(forbidden_patterns)) is None


def validate_fix_paths(
    changed_files: Iterable[str],
    safe_prefixes: Iterable[str] = EXTENDED_SAFE_PATH_PREFIXES,
    forbidden_patterns: Iterable[str] = EXTENDED_FORBIDDEN_PATH_PATTERNS,
) -> bool:
    """Raise RemediationBlockedError for the first path automation must not touch (Chapter 7)."""
    from healer.library.remediation.types import RemediationBlockedError

    prefixes, patterns = list(safe_prefixes), list(forbidden_patterns)
    for path in changed_files:
        reason = check_path(path, prefixes, patterns)
        if reason:
            raise RemediationBlockedError(reason)
    return True
