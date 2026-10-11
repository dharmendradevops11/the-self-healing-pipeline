"""The git operations the book's remediation listing assumes (Chapter 2).

The listing calls checkout_branch, apply_patch, push_branch, rollback_branch and
delete_branch without defining them. LocalGit implements them with the real `git` binary.
It is meant for a clone the pipeline owns (a temp directory), never for a developer's
working copy: rollback discards uncommitted changes in it.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PatchResult:
    success: bool
    error: str = ""


class GitOps(Protocol):
    def checkout_branch(self, branch: str, base: str = "main") -> None: ...
    def apply_patch(self, diff: str) -> PatchResult: ...
    def commit(self, message: str) -> None: ...
    def push_branch(self, branch: str) -> None: ...
    def rollback_branch(self, branch: str, base: str = "main") -> None: ...
    def delete_branch(self, branch: str) -> None: ...


class GitError(RuntimeError):
    pass


DEPENDENCY_MANIFESTS = (
    "requirements*.txt",
    "pyproject.toml",
    "Pipfile.lock",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "Gemfile.lock",
)


TEST_PATHS = (
    "tests/",
    "test/",
    "**/test_*.py",
    "**/*_test.py",
    "**/*.test.ts",
    "**/*.test.js",
    "**/*.spec.ts",
    "**/*.spec.js",
)


class LocalGit:
    def __init__(
        self,
        repo_path: str | Path,
        remote: str = "origin",
        author_name: str = "AI Self-Healer",
        author_email: str = "healer@example.com",
        auth_header: str | None = None,
    ):
        self.repo = str(repo_path)
        self.remote = remote
        # An HTTP Authorization header passed on the command line, so a token is never written
        # into the remote URL or .git/config.
        self._auth = ["-c", f"http.extraHeader={auth_header}"] if auth_header else []
        self._env = {
            **os.environ,
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }

    def _git(self, *args: str, stdin: str | None = None, check: bool = True) -> str:
        # An argument list with shell=False: nothing from the model or the diff is ever
        # interpreted by a shell.
        result = subprocess.run(
            ["git", *self._auth, *args],
            cwd=self.repo,
            input=stdin,
            capture_output=True,
            text=True,
            env=self._env,
        )
        if check and result.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def checkout_branch(self, branch: str, base: str = "main") -> None:
        self._git("checkout", base)
        self._git("checkout", "-b", branch)

    def apply_patch(self, diff: str) -> PatchResult:
        # --recount: models often miscount hunk line numbers; let git recompute them.
        # A patch must end with a newline, or git reports "corrupt patch".
        patch = diff if diff.endswith("\n") else diff + "\n"
        try:
            self._git("apply", "--3way", "--recount", "--whitespace=fix", "-", stdin=patch)
        except GitError as exc:
            return PatchResult(False, str(exc))
        return PatchResult(True)

    def commit(self, message: str) -> None:
        self._git("add", "-A")
        self._git("commit", "-m", message)

    def push_branch(self, branch: str) -> None:
        self._git("push", "--set-upstream", self.remote, branch)

    def rollback_branch(self, branch: str, base: str = "main") -> None:
        """Leave the base branch untouched: discard the half-applied change and the branch."""
        self._git("reset", "--hard", check=False)
        self._git("checkout", "-f", base)
        self._git("branch", "-D", branch, check=False)

    def delete_branch(self, branch: str) -> None:
        self._git("push", self.remote, "--delete", branch, check=False)
        self._git("branch", "-D", branch, check=False)

    def checkout_remote_branch(self, branch: str) -> None:
        """Check out a branch another stage pushed. A fresh clone does not have it locally.

        The clone may be shallow and single-branch, where a plain fetch leaves no local ref, so
        the branch is created from FETCH_HEAD.
        """
        self._git("fetch", self.remote, branch)
        self._git("checkout", "-B", branch, "FETCH_HEAD")

    def commit_file(self, branch: str, path: str, content: str, message: str) -> None:
        """Add or update one file on a branch and push it."""
        self.checkout_remote_branch(branch)
        target = Path(self.repo) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self._git("add", path)
        self._git("commit", "-m", message)
        self._git("push", self.remote, branch)

    def head_sha(self) -> str:
        return self._git("rev-parse", "--short", "HEAD").strip()

    def log_for(self, files: list[str], count: int = 5) -> str:
        """Recent commits touching these files, one per line (Chapter 8 reads this as context)."""
        if not files:
            return ""
        out = self._git(
            "log", f"-{count}", "--format=%h %ad %s", "--date=short", "--", *files, check=False
        )
        return out.strip()

    def recent_deployment(self) -> str:
        """The newest change on the checked-out branch: the nearest thing to "what deployed last".

        A git repository does not know what was deployed. The head commit is the best proxy it
        has, and the label says so, so the model does not treat it as a deploy record.
        """
        out = self._git(
            "log", "-1", "--format=%h %ad by %an: %s", "--date=iso-strict", check=False
        ).strip()
        return f"latest commit on the base branch (proxy for the last deploy): {out}" if out else ""

    def dependency_changes(self, days: int = 14, limit: int = 1500) -> str:
        """Commits that touched dependency manifests recently, with the lines they changed."""
        out = self._git(
            "log",
            f"--since={days}.days",
            "-p",
            "--unified=0",
            "--format=commit %h %ad %s",
            "--date=short",
            "--",
            *DEPENDENCY_MANIFESTS,
            check=False,
        ).strip()
        return out[:limit] if out else f"no dependency manifest changed in the last {days} days"

    def related_tests(self, files: list[str], limit: int = 3) -> list[str]:
        """Test files that mention a module the fix will change, so the fix can pass them.

        A test is a statement of what the code must do. A fix written without reading it can be
        right about the bug and wrong about the expected behaviour (found on real AWS: the model
        returned "Guest" where the test required "there").
        """
        names = sorted({Path(f).stem for f in files if Path(f).suffix})
        if not names:
            return []
        found = self._git(
            "grep",
            "-l",
            "-F",
            *[a for n in names for a in ("-e", n)],
            "--",
            *TEST_PATHS,
            check=False,
        )
        paths = [p for p in found.splitlines() if p and p not in files]
        return paths[:limit]

    def read_file(self, relative_path: str) -> str:
        """Read a file from the working tree, refusing anything that escapes the repository."""
        root = Path(self.repo).resolve()
        target = (root / relative_path).resolve()
        if root != target and root not in target.parents:
            raise PermissionError(f"path escapes the repository: {relative_path}")
        return target.read_text(encoding="utf-8")


def basic_auth_header(token: str) -> str:
    """The header GitHub accepts for HTTPS git access with a personal access token."""
    import base64

    encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
    return f"Authorization: Basic {encoded}"


def clone_repo(
    url: str, base_branch: str, dest: str | Path, token: str | None = None, depth: int = 1
) -> LocalGit:
    """Clone a repository into `dest` and return a LocalGit for it.

    The token travels as an HTTP header for this process only. It is never in the URL, in the
    clone's config, or in the environment.
    """
    header = basic_auth_header(token) if token else None
    prefix = ["-c", f"http.extraHeader={header}"] if header else []
    result = subprocess.run(
        ["git", *prefix, "clone", "--depth", str(depth), "--branch", base_branch, url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"git clone failed: {result.stderr.replace(token or chr(0), '***').strip()}")
    return LocalGit(dest, auth_header=header)
