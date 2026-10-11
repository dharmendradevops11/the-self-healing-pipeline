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


def is_path_remediable(
    file_path: str,
    safe_prefixes: Iterable[str] = SAFE_PATH_PREFIXES,
    forbidden_patterns: Iterable[str] = FORBIDDEN_PATH_PATTERNS,
) -> bool:
    """True only if the path is under a safe prefix and matches no forbidden pattern."""
    if ".." in file_path.split("/") or file_path.startswith("/"):
        return False  # path traversal or an absolute path: never inside the repo's source tree
    if any(re.search(pattern, file_path) for pattern in forbidden_patterns):
        return False
    return any(file_path.startswith(prefix) for prefix in safe_prefixes)


def validate_fix_paths(
    changed_files: Iterable[str],
    safe_prefixes: Iterable[str] = EXTENDED_SAFE_PATH_PREFIXES,
    forbidden_patterns: Iterable[str] = EXTENDED_FORBIDDEN_PATH_PATTERNS,
) -> bool:
    """Raise RemediationBlockedError for the first path automation must not touch (Chapter 7)."""
    from healer.library.remediation.types import RemediationBlockedError

    prefixes, patterns = list(safe_prefixes), list(forbidden_patterns)
    for path in changed_files:
        if any(re.search(pattern, path) for pattern in patterns):
            raise RemediationBlockedError(f"Fix touches forbidden path: {path}")
        if not any(path.startswith(prefix) for prefix in prefixes):
            raise RemediationBlockedError(f"Fix touches path outside allowlist: {path}")
    return True
