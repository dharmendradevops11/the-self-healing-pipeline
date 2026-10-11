"""The allowlist as configuration (Chapter 17, "The Allowlist: Defining the Blast Radius").

Chapter 2 prints the allowlist as Python constants, Chapter 7 as a wider set, and this chapter
as a reviewable YAML document with globs and hard patch limits. All three express the same
idea: automation may only touch source code, in small changes, with tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_POLICY = """
file_patterns:
  allowed:
    - "src/**/*.py"
    - "tests/**/*"
    - "requirements.txt"
  denied:
    - "**/.env*"
    - "**/secrets.yaml"
    - "infrastructure/**/*"
    - "**/database/migrations/*"
    - "Dockerfile"

validation:
  max_files_per_patch: 5
  max_lines_per_file: 500
  require_tests: true
"""


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob: `**` crosses directories, `*` and `?` stay inside one."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


@dataclass(frozen=True)
class PatchCheck:
    ok: bool
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatchPolicy:
    allowed: list[re.Pattern[str]]
    denied: list[re.Pattern[str]]
    max_files_per_patch: int = 5
    max_lines_per_file: int = 500
    require_tests: bool = True

    @classmethod
    def from_file(cls, path: str | Path = "config/allowlist.yaml") -> PatchPolicy:
        """Load the reviewable policy file the book names, `config/allowlist.yaml`."""
        return cls.from_yaml(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_yaml(cls, text: str = DEFAULT_POLICY) -> PatchPolicy:
        import yaml  # imported here so a Lambda that only validates webhooks needs no PyYAML

        doc: dict[str, Any] = yaml.safe_load(text) or {}
        patterns = doc.get("file_patterns", {})
        validation = doc.get("validation", {})
        return cls(
            allowed=[glob_to_regex(p) for p in patterns.get("allowed", [])],
            denied=[glob_to_regex(p) for p in patterns.get("denied", [])],
            max_files_per_patch=int(validation.get("max_files_per_patch", 5)),
            max_lines_per_file=int(validation.get("max_lines_per_file", 500)),
            require_tests=bool(validation.get("require_tests", True)),
        )

    def path_allowed(self, path: str) -> bool:
        """Denied wins over allowed. Anything not allowed is refused."""
        if ".." in path.split("/") or path.startswith("/"):
            return False
        if any(p.match(path) for p in self.denied):
            return False
        return any(p.match(path) for p in self.allowed)

    def check_patch(self, lines_changed: dict[str, int], includes_tests: bool) -> PatchCheck:
        """lines_changed maps each touched path to the number of lines changed in it."""
        problems: list[str] = []
        for path in lines_changed:
            if not self.path_allowed(path):
                problems.append(f"path not allowed: {path}")
        if len(lines_changed) > self.max_files_per_patch:
            problems.append(
                f"{len(lines_changed)} files exceeds the limit of {self.max_files_per_patch}"
            )
        for path, lines in lines_changed.items():
            if lines > self.max_lines_per_file:
                problems.append(f"{path}: {lines} lines exceeds {self.max_lines_per_file}")
        if self.require_tests and not includes_tests:
            problems.append("patch does not include tests")
        return PatchCheck(ok=not problems, problems=problems)
