"""Step 3: FIX.

Generate a diff, enforce the allowlist, apply it, push a healer/ branch. (Ch 2, 7, 17).
"""

from healer.fix.git_ops import GitError, GitOps, LocalGit, PatchResult
from healer.fix.remediation import apply_remediation, diff_summary, files_in_diff, slugify

__all__ = [
    "GitError",
    "GitOps",
    "LocalGit",
    "PatchResult",
    "apply_remediation",
    "diff_summary",
    "files_in_diff",
    "slugify",
]
