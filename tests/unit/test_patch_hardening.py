"""One path policy for both entry points, and diffs that try to slip past it."""

from unittest.mock import MagicMock

import pytest

from healer.fix.remediation import apply_remediation
from healer.guardrails.allowlist import is_path_remediable, validate_fix_paths
from healer.library.remediation.types import RemediationBlockedError

BAD_PATHS = [
    "src/../.github/workflows/ci.yml",
    "/src/app.py",
    "src/./app.py",
    "src//app.py",
    "src\\..\\x.py",
    "src/app.py\x00.txt",
    "",
    "../src/app.py",
]


@pytest.mark.parametrize("path", BAD_PATHS)
def test_both_entry_points_refuse_the_same_bad_paths(path):
    assert is_path_remediable(path) is False
    with pytest.raises(RemediationBlockedError):
        validate_fix_paths([path])


@pytest.mark.parametrize("path", ["src/a.py", "lib/x/y.py", "server/api.py"])
def test_both_entry_points_accept_a_good_path(path):
    assert validate_fix_paths([path]) is True


def _git():
    git = MagicMock()
    git.apply_patch.return_value = MagicMock(success=True)
    return git


SYMLINK = (
    "diff --git a/src/link b/src/link\nnew file mode 120000\n--- /dev/null\n+++ b/src/link\n"
    "@@ -0,0 +1 @@\n+/etc/passwd\n"
)
RENAME_OUT = (
    "diff --git a/src/a.py b/.github/workflows/a.yml\nsimilarity index 100%\n"
    "rename from src/a.py\nrename to .github/workflows/a.yml\n"
)
NO_HEADER = "--- a/src/a.py\n+++ b/.github/workflows/ci.yml\n@@ -1 +1 @@\n-a\n+b\n"


def test_a_symbolic_link_is_refused():
    git = _git()
    out = apply_remediation(SYMLINK, ["src/link"], git)
    assert out["applied"] is False and "symbolic link" in out["reason"]
    git.checkout_branch.assert_not_called()


def test_a_rename_into_a_forbidden_path_is_refused():
    git = _git()
    out = apply_remediation(RENAME_OUT, ["src/a.py"], git)
    assert out["applied"] is False
    git.checkout_branch.assert_not_called()


def test_a_diff_without_a_git_header_cannot_hide_a_forbidden_file():
    git = _git()
    out = apply_remediation(NO_HEADER, ["src/a.py"], git)
    assert out["applied"] is False
    git.checkout_branch.assert_not_called()


@pytest.mark.parametrize("junk", ["", "not a diff at all", "@@ -1 +1 @@\n-a\n+b\n"])
def test_a_malformed_diff_never_reaches_git(junk):
    git = _git()
    out = apply_remediation(junk, ["src/a.py"], git)
    assert out["applied"] is False
    git.apply_patch.assert_not_called()
