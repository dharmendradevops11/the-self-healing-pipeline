"""The loop closes: a reviewer's decision becomes a ledger verdict (Chapters 2 and 9)."""

import hashlib
import hmac
import json

import boto3
import pytest
from moto import mock_aws

from healer import handlers
from healer.config import Settings
from healer.ledger import remediation_history, trust_ledger
from healer.ledger.feedback import apply_pr_outcome, rejection_reason

BODY = "## Self-Healing Pipeline: Fix\n\n_Execution: `exec-abc123`_\n"
REPORT = "## Self-Healing Pipeline: Investigation only\n\n_Execution: `exec-abc123`_\n"


def pr_event(merged=False, commits=2, body=BODY, ref="healer/2026-10-09-x-abc123", action="closed"):
    return {
        "action": action,
        "pull_request": {"head": {"ref": ref}, "merged": merged, "commits": commits, "body": body},
    }


@pytest.fixture
def tables():
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        trust_ledger.create_table(db)
        remediation_history.create_table(db)
        trust_ledger.record_outcome(db, "exec-abc123", "h", 90, "pending", None, category="c")
        remediation_history.record_remediation(
            db,
            remediation_history.RemediationRecord("exec-abc123", "svc", "h", 90, "repair"),
        )
        yield db


def verdict(db):
    ledger = db.Table(trust_ledger.TABLE_NAME).get_item(Key={"execution_id": "exec-abc123"})
    history = db.Table(remediation_history.TABLE_NAME).get_item(Key={"incident_id": "exec-abc123"})
    return ledger["Item"]["human_verdict"], history["Item"]["human_decision"]


class TestVerdicts:
    def run(self, db, event):
        return apply_pr_outcome(db, event, trust_ledger.TABLE_NAME, remediation_history.TABLE_NAME)

    def test_a_merge_is_approval(self, tables):
        assert self.run(tables, pr_event(merged=True))["verdict"] == "approved"
        assert verdict(tables) == ("approved", "merged")

    def test_a_merge_with_extra_commits_is_a_modification(self, tables):
        self.run(tables, pr_event(merged=True, commits=3))
        assert verdict(tables) == ("modified", "edited_then_merged")

    def test_closing_without_merging_is_a_rejection_and_keeps_the_reason(self, tables):
        body = BODY + "- [x] Wrong root cause\n- [ ] Breaks compliance\n"
        out = self.run(tables, pr_event(merged=False, body=body))
        assert out == {
            "execution_id": "exec-abc123",
            "verdict": "rejected",
            "reason": "Wrong root cause",
        }
        item = tables.Table(remediation_history.TABLE_NAME).get_item(
            Key={"incident_id": "exec-abc123"}
        )
        assert item["Item"]["rejection_reason"] == "Wrong root cause"

    @pytest.mark.parametrize(
        "event",
        [
            pr_event(action="opened"),
            pr_event(ref="feature/x"),
            pr_event(body="no execution here"),
            pr_event(body=REPORT, merged=True),
        ],
    )
    def test_everything_else_is_ignored(self, tables, event):
        assert "ignored" in self.run(tables, event)
        assert verdict(tables) == ("pending", None)

    def test_the_reason_must_be_ticked(self):
        assert rejection_reason("- [ ] Wrong approach") is None
        assert rejection_reason("- [X] Security concern") == "Security concern"

    def test_verdicts_feed_the_composite_confidence_once_there_are_enough(self, tables):
        for i in range(5):
            trust_ledger.record_outcome(tables, f"e{i}", "h", 80, "approved", None, category="c")
        assert trust_ledger.historical_success_rate(tables, "c") == 1.0


class TestWebhook:
    SECRET = "gh-hook-secret"

    def signed(self, payload, event_name="pull_request", secret=SECRET):
        body = json.dumps(payload)
        sig = "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        return {
            "body": body,
            "headers": {"X-Hub-Signature-256": sig, "X-GitHub-Event": event_name},
        }

    def settings(self):
        return Settings(github_webhook_secret_arn="arn:secret")

    def secrets(self):
        class Fake:
            def get_secret_value(self, SecretId):  # noqa: N803
                return {"SecretString": TestWebhook.SECRET}

        return Fake()

    def call(self, db, event, settings=None):
        return handlers.github_webhook_handler(
            event, settings=settings or self.settings(), secrets_client=self.secrets(), dynamodb=db
        )

    def test_a_signed_merge_updates_the_ledger(self, tables):
        out = self.call(tables, self.signed(pr_event(merged=True)))
        assert out["statusCode"] == 200 and json.loads(out["body"])["verdict"] == "approved"
        assert verdict(tables)[0] == "approved"

    def test_a_forged_signature_changes_nothing(self, tables):
        out = self.call(tables, self.signed(pr_event(merged=True), secret="wrong"))
        assert out["statusCode"] == 401 and verdict(tables)[0] == "pending"

    def test_without_a_configured_secret_it_fails_closed(self, tables):
        out = self.call(tables, self.signed(pr_event(merged=True)), settings=Settings())
        assert out["statusCode"] == 401 and verdict(tables)[0] == "pending"

    def test_other_github_events_are_acknowledged_and_ignored(self, tables):
        out = self.call(tables, self.signed({"zen": "x"}, event_name="ping"))
        assert out["statusCode"] == 200 and "ignored" in json.loads(out["body"])


def test_the_webhook_logs_the_verdict_it_recorded(tables, capsys):
    """The first real merge left no log line to show the ledger update."""
    secrets = TestWebhook().secrets()
    event = TestWebhook().signed(pr_event(merged=True))
    handlers.github_webhook_handler(
        event,
        settings=Settings(github_webhook_secret_arn="arn:s"),
        secrets_client=secrets,
        dynamodb=tables,
    )
    line = json.loads(
        next(x for x in capsys.readouterr().out.splitlines() if x.startswith('{"hop"'))
    )
    assert line == {
        "hop": "github->ledger",
        "execution_id": "exec-abc123",
        "verdict": "approved",
        "reason": None,
    }
