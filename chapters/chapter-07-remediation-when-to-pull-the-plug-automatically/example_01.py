import re

SAFE_PATH_PREFIXES = [
    "src/",
    "lib/",
    "app/",
    "packages/",
    "server/",
    "api/",
]

FORBIDDEN_PATH_PATTERNS = [
    r"^infrastructure/",
    r"^\.github/",
    r"^\.husky/",
    r"(^|/)migrations/",
    r"(^|/)Dockerfile$",
    r"\.ya?ml$",
    r"\.sh$",
]

def validate_fix_paths(changed_files):
    for path in changed_files:
        if any(re.search(pattern, path) for pattern in FORBIDDEN_PATH_PATTERNS):
            raise RemediationBlockedError(f"Fix touches forbidden path: {path}")
        if not any(path.startswith(prefix) for prefix in SAFE_PATH_PREFIXES):
            raise RemediationBlockedError(f"Fix touches path outside allowlist: {path}")
    return True
