"""Stage 3, Test: type-check, unit tests and lint against the change (Chapter 2).

TEST runs before anything reaches a human. For the Python demo app the checks are mypy (type
check), pytest (unit tests) and ruff (lint). A check whose tool is not installed is reported as
skipped, never as passed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_COMMANDS: dict[str, list[str]] = {
    "type_check": [sys.executable, "-m", "mypy", "src"],
    "unit": [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
    "lint": [sys.executable, "-m", "ruff", "check", "src"],
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # pass | fail | skipped
    output: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass
class TestReport:
    __test__ = False  # not a pytest test class

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall_passed(self) -> bool:
        """Every check that ran passed, and the unit tests did run."""
        ran = [c for c in self.checks if c.status != "skipped"]
        unit = next((c for c in self.checks if c.name == "unit"), None)
        return bool(ran) and all(c.passed for c in ran) and unit is not None and unit.passed

    def summary(self) -> list[str]:
        return [f"{c.name.replace('_', '-')}: {c.status}" for c in self.checks]


def _module_available(command: list[str]) -> bool:
    if len(command) >= 3 and command[1] == "-m":
        probe = subprocess.run(
            [
                command[0],
                "-c",
                f"import importlib.util as u,sys; sys.exit(u.find_spec('{command[2]}') is None)",
            ],
            capture_output=True,
        )
        return probe.returncode == 0
    return shutil.which(command[0]) is not None


def run_checks(
    repo_path: str | Path,
    commands: dict[str, list[str]] | None = None,
    timeout: int = 300,
    setup: list[list[str]] | None = None,
) -> TestReport:
    """Run each check in the repository. An argument list with no shell: nothing is interpreted.

    `setup` commands (for example installing the repository's own dependencies) run first. If one
    fails, every check is reported as failed rather than silently skipped.
    """
    report = TestReport()
    for command in setup or []:
        failure = ""
        try:
            done = subprocess.run(
                command, cwd=str(repo_path), capture_output=True, text=True, timeout=timeout
            )
            if done.returncode != 0:
                failure = (done.stdout + done.stderr)[-1500:]
        except (subprocess.TimeoutExpired, OSError) as exc:
            failure = str(exc)
        if failure:
            for name in commands or DEFAULT_COMMANDS:
                report.checks.append(CheckResult(name, "fail", f"setup failed: {failure}"))
            return report
    for name, command in (commands or DEFAULT_COMMANDS).items():
        if not _module_available(command):
            report.checks.append(
                CheckResult(
                    name,
                    "skipped",
                    f"{command[2] if len(command) > 2 else command[0]} is not installed",
                )
            )
            continue
        try:
            result = subprocess.run(
                command, cwd=str(repo_path), capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            report.checks.append(CheckResult(name, "fail", f"timed out after {timeout}s"))
            continue
        status = "pass" if result.returncode == 0 else "fail"
        report.checks.append(CheckResult(name, status, (result.stdout + result.stderr)[-2000:]))
    return report
