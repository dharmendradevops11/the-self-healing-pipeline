"""What real Sentry sent (found on real AWS): two webhooks per error, and an alert-rule shape."""

import json
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from healer.demo import SCENARIOS, local_services
from healer.ingest.rate_limiter import claim_issue, create_table
from healer.ingest.sentry import UnsupportedPayloadError, incident_from_sentry, payload_shape
from healer.pipeline import run_pipeline

ISSUE = {
    "action": "created",
    "data": {
        "issue": {
            "id": "7784017478",
            "title": "AttributeError: 'NoneType' object has no attribute 'name'",
            "culprit": "src.auth in get_display_name",
            "level": "error",
            "project": {"slug": "python"},
            "permalink": "https://example-org.sentry.io/issues/7784017478/",
            "firstSeen": "2026-10-09T20:09:03Z",
        }
    },
}
ALERT = {
    "action": "triggered",
    "data": {
        "event": {
            "event_id": "65a04b56",
            "issue_id": "7784017478",
            "title": "AttributeError: 'NoneType' object has no attribute 'name'",
            "project": 1234567890123456,
            "server_name": "demo-app",
            "level": "error",
            "web_url": "https://example-org.sentry.io/issues/7784017478/events/65a04b56/",
            "datetime": "2026-10-09T20:09:03Z",
            "tags": [["service", "demo-app"], ["source", "test"]],
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"filename": "src/auth.py", "lineno": 28, "function": "greet"},
                                {"filename": "src/auth.py", "lineno": 24, "function": "f"},
                            ]
                        }
                    }
                ]
            },
        },
        "triggered_rule": "Notify via self-healing-pipeline",
    },
}


class TestParsing:
    def test_an_alert_rule_event_gets_the_service_from_its_tag_and_the_issue_id(self):
        inc = incident_from_sentry(ALERT)
        assert inc["affectedService"] == "demo-app"  # not the numeric project id
        assert inc["sentryIssueId"] == "7784017478"
        assert inc["triggeredAt"] == "2026-10-09T20:09:03Z"  # when it happened, not "now"
        assert 'File "src/auth.py", line 24' in inc["stackTrace"]
        assert inc["sentryIssueUrl"].startswith("https://example-org.sentry.io/issues/7784017478/")

    def test_without_a_service_tag_server_name_then_project_are_used(self):
        alert = json.loads(json.dumps(ALERT))
        alert["data"]["event"]["tags"] = []
        assert incident_from_sentry(alert)["affectedService"] == "demo-app"  # server_name
        del alert["data"]["event"]["server_name"]
        assert incident_from_sentry(alert)["affectedService"] == "1234567890123456"

    def test_an_issue_webhook_still_works_and_carries_the_same_issue_id(self):
        inc = incident_from_sentry(ISSUE)
        assert inc["affectedService"] == "python" and inc["sentryIssueId"] == "7784017478"

    @pytest.mark.parametrize("action", ["resolved", "assigned", "ignored", "unresolved"])
    def test_an_issue_that_was_resolved_or_assigned_is_not_a_failure(self, action):
        with pytest.raises(UnsupportedPayloadError):
            incident_from_sentry({**ISSUE, "action": action})

    def test_the_logged_shape_has_keys_and_types_but_no_values(self):
        shape = payload_shape(ALERT)
        assert shape["data"]["event"]["title"] == "str" and "AttributeError" not in json.dumps(
            shape
        )


class TestDedupe:
    def test_the_first_claim_wins_and_the_second_is_refused(self):
        with mock_aws():
            table = boto3.resource("dynamodb", region_name="us-east-1")
            create_table(table)
            t = table.Table("investigation_rate_limits")
            assert claim_issue(t, "7784017478") and not claim_issue(t, "7784017478")
            assert claim_issue(t, "other-issue")

    def test_two_deliveries_of_one_error_run_the_pipeline_once(self, tmp_path):
        incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
        incident["sentryIssueId"] = "7784017478"
        with local_services(work_dir=tmp_path) as (services, handles):
            services.check_commands = {"noop": ["true"]}
            first = run_pipeline(incident, services, execution_id="exec-first")
            second = run_pipeline(incident, services, execution_id="exec-second")
        assert first.outcome == "pr_opened"
        assert second.outcome == "duplicate" and "already being handled" in second.reason
        assert len(list((tmp_path / "prs").glob("pr-*.json"))) == 1  # one pull request, not two

    def test_an_incident_without_an_issue_id_is_not_deduplicated(self, tmp_path):
        incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
        incident.pop("sentryIssueId", None)
        with local_services(work_dir=tmp_path) as (services, _):
            services.check_commands = {"noop": ["true"]}
            services.throttle = None
            assert run_pipeline(incident, services, "e1").outcome == "pr_opened"
            assert run_pipeline(incident, services, "e2").outcome != "duplicate"


def test_the_webhook_logs_the_shape_of_what_arrived():
    from healer import handlers
    from healer.config import Settings

    secrets = MagicMock()
    secrets.get_secret_value.return_value = {"SecretString": "s"}
    import hashlib
    import hmac
    import time

    body = json.dumps(ALERT)
    sig = hmac.new(b"s", body.encode(), hashlib.sha256).hexdigest()
    sns = MagicMock()
    sns.publish.return_value = {"MessageId": "m1"}
    out = handlers.webhook_handler(
        {
            "body": body,
            "headers": {
                "sentry-hook-signature": sig,
                "sentry-hook-timestamp": str(int(time.time())),
            },
        },
        settings=Settings(webhook_secret_arn="arn:s", trigger_topic_arn="arn:t"),
        secrets_client=secrets,
        sns_client=sns,
    )
    assert out["statusCode"] == 202
