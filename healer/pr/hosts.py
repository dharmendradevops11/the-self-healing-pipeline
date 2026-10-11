"""Where pull requests go (Chapter 2, Step 4: PR).

`LocalPRHost` writes the pull request to disk, so the whole pipeline can run on a laptop.
`GitHubPRHost` opens a real one through the GitHub REST API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from healer.gate.decision import Decision

ACTION_LABELS = {
    "auto_fix_pr": "healer: auto-fix-pr",
    "fix_pr_standard_review": "healer: standard-review",
    "fix_pr_expedited_review": "healer: expedited-review",
    "investigation_only": "healer: investigation-only",
}


def build_labels(
    decision: Decision, confidence: int, large_diff: bool = False, human_review: bool = False
) -> list[str]:
    """Labels that let a reviewer triage the queue at a glance."""
    labels = [
        "healer",
        ACTION_LABELS[decision.fix_action],
        f"healer: blast-radius-{decision.blast_radius['tier']}",
    ]
    if decision.band == "low":
        labels.append("healer: low-confidence")
    if human_review:
        labels.append("healer: human-review")
    if large_diff:
        labels.append("healer: large-diff")
    return labels


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str
    title: str
    branch: str
    labels: list[str] = field(default_factory=list)


class PullRequestHost(Protocol):
    def create_branch(self, branch: str, base: str) -> None: ...

    def commit_file(self, branch: str, path: str, content: str, message: str) -> None: ...

    def open_pull_request(
        self, *, title: str, body: str, branch: str, base: str, labels: list[str], draft: bool
    ) -> PullRequest: ...


class LocalPRHost:
    """Writes each pull request as a markdown file plus a JSON sidecar under a folder."""

    def __init__(self, folder: str | Path, git: Any = None):
        self.folder = Path(folder)
        self.git = git  # a LocalGit, used to commit the reviewer packet onto the branch

    def create_branch(self, branch: str, base: str) -> None:
        if self.git is not None:
            self.git.checkout_branch(branch, base=base)
            self.git.push_branch(branch)

    def commit_file(self, branch: str, path: str, content: str, message: str) -> None:
        if self.git is None:
            (self.folder / "files").mkdir(parents=True, exist_ok=True)
            (self.folder / "files" / path).write_text(content, encoding="utf-8")
            return
        self.git.commit_file(branch, path, content, message)

    def open_pull_request(
        self, *, title: str, body: str, branch: str, base: str, labels: list[str], draft: bool
    ) -> PullRequest:
        self.folder.mkdir(parents=True, exist_ok=True)
        number = len(list(self.folder.glob("pr-*.json"))) + 1
        meta = {
            "number": number,
            "title": title,
            "branch": branch,
            "base": base,
            "labels": labels,
            "draft": draft,
        }
        (self.folder / f"pr-{number}.json").write_text(json.dumps(meta, indent=2))
        (self.folder / f"pr-{number}.md").write_text(
            f"# {title}\n\n`{branch}` -> `{base}`  \n"
            f"Labels: {', '.join(labels)}  \nDraft: {draft}\n\n{body}"
        )
        return PullRequest(number, str(self.folder / f"pr-{number}.md"), title, branch, labels)


class _Response:
    def __init__(self, status: int, body: bytes):
        self.status_code, self._body = status, body

    def json(self) -> Any:
        return json.loads(self._body or b"null")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"GitHub API error {self.status_code}: {self._body[:300]!r}")


class UrllibSession:
    """The few requests.Session calls we use, on the standard library.

    The Lambda runtime does not ship `requests` (found on real AWS), and bundling it for three
    HTTP calls is not worth a dependency.
    """

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def _call(self, method: str, url: str, params: Any, body: Any, timeout: float) -> _Response:
        import urllib.error
        import urllib.parse
        import urllib.request

        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers=self.headers)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
                return _Response(resp.status, resp.read())
        except urllib.error.HTTPError as err:
            return _Response(err.code, err.read())

    def get(self, url: str, params: Any = None, timeout: float = 20) -> _Response:
        return self._call("GET", url, params, None, timeout)

    def put(self, url: str, json: Any = None, timeout: float = 20) -> _Response:
        return self._call("PUT", url, None, json, timeout)

    def post(self, url: str, json: Any = None, timeout: float = 20) -> _Response:
        return self._call("POST", url, None, json, timeout)


class GitHubPRHost:
    """Opens a pull request with the GitHub REST API (`session` is a requests.Session)."""

    def __init__(
        self,
        owner: str,
        repo: str,
        token: str,
        session: Any = None,
        api: str = "https://api.github.com",
    ):
        self.owner, self.repo, self.api = owner, repo, api
        self.session = session or UrllibSession()
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        )

    def create_branch(self, branch: str, base: str) -> None:
        """Create a branch at the tip of `base` through the API (a Lambda has no git binary)."""
        repo = f"{self.api}/repos/{self.owner}/{self.repo}"
        ref = self.session.get(f"{repo}/git/ref/heads/{base}", timeout=20)
        ref.raise_for_status()
        sha = ref.json()["object"]["sha"]
        self.session.post(
            f"{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha}, timeout=20
        ).raise_for_status()

    def commit_file(self, branch: str, path: str, content: str, message: str) -> None:
        """Create or update a file on a branch through the contents API (no git binary needed)."""
        import base64

        url = f"{self.api}/repos/{self.owner}/{self.repo}/contents/{path}"
        existing = self.session.get(url, params={"ref": branch}, timeout=20)
        payload: dict[str, Any] = {
            "message": message,
            "branch": branch,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if existing.status_code == 200:
            payload["sha"] = existing.json()["sha"]
        self.session.put(url, json=payload, timeout=20).raise_for_status()

    def open_pull_request(
        self, *, title: str, body: str, branch: str, base: str, labels: list[str], draft: bool
    ) -> PullRequest:
        response = self.session.post(
            f"{self.api}/repos/{self.owner}/{self.repo}/pulls",
            json={"title": title, "head": branch, "base": base, "body": body, "draft": draft},
            timeout=20,
        )
        response.raise_for_status()
        pr = response.json()
        label_response = self.session.post(
            f"{self.api}/repos/{self.owner}/{self.repo}/issues/{pr['number']}/labels",
            json={"labels": labels},
            timeout=20,
        )
        label_response.raise_for_status()
        return PullRequest(pr["number"], pr["html_url"], title, branch, labels)
