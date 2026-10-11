"""The deployable entry points: webhook receiver, Lambda handlers, Fargate task runner, configuration."""

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from healer import handlers, stages
from healer.config import Settings, build_services
from healer.demo import SCENARIOS, STATE_BUCKET, local_services
from healer.fix.git_ops import GitError, basic_auth_header, clone_repo
from healer.ingest.enrich import make_log_fetcher
from healer.ingest.sentry import UnsupportedPayloadError, incident_from_sentry
from healer.ingest.webhook import authenticate_webhook
from healer.state import PipelineState, S3StateStore
from healer.tasks import main as task_main
from healer.tasks import run_task

INCIDENT = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
SECRET = "whsec"


def sentry_payload(**issue):
    base = {
        "id": "123",
        "title": "TypeError: x is undefined",
        "culprit": "src/auth.ts in getDisplayName",
        "permalink": "https://sentry.io/organizations/o/issues/123/",
        "level": "error",
        "project": {"slug": "checkout-api"},
        "lastSeen": "2026-10-09T12:00:00Z",
    }
    return {"action": "created", "data": {"issue": {**base, **issue}}}


# ------------------------------------------------------------------------ sentry


class TestSentryMapping:
    def test_an_issue_becomes_an_incident(self):
        inc = incident_from_sentry(sentry_payload())
        assert (inc["source"], inc["severity"], inc["type"]) == ("sentry", "high", "crash")
        assert (
            inc["affectedService"] == "checkout-api"
            and inc["cloudwatchLogGroup"] == "/aws/ecs/checkout-api"
        )
        assert "src/auth.ts" in inc["stackTrace"] and inc["sentryIssueUrl"].endswith("/issues/123/")
        assert inc["triggeredAt"] == "2026-10-09T12:00:00Z"

    @pytest.mark.parametrize(
        ("level", "sev"),
        [("fatal", "critical"), ("error", "high"), ("warning", "medium"), ("info", "medium")],
    )
    def test_severity_comes_from_the_level(self, level, sev):
        assert incident_from_sentry(sentry_payload(level=level))["severity"] == sev

    def test_timeouts_are_performance_issues(self):
        assert (
            incident_from_sentry(sentry_payload(title="Request timed out after 30s"))["type"]
            == "performance"
        )

    def test_real_exception_frames_become_a_traceback(self):
        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"filename": "src/a.py", "lineno": 3, "function": "load"},
                                {"filename": "src/b.py", "lineno": 9, "function": "run"},
                            ]
                        }
                    }
                ]
            }
        }
        payload = {"data": {"event": {"title": "KeyError: 'id'", "project": "api", **event}}}
        inc = incident_from_sentry(payload)
        assert (
            'File "src/a.py", line 3, in load' in inc["stackTrace"]
            and inc["affectedService"] == "api"
        )

    def test_other_webhooks_are_not_incidents(self):
        with pytest.raises(UnsupportedPayloadError):
            incident_from_sentry({"action": "installed", "data": {}})


# ---------------------------------------------------------------------- the webhook


class TestWebhookAuthWithHeaderTimestamp:
    def test_a_header_timestamp_is_used_instead_of_a_body_field(self):
        body = json.dumps({"a": 1})
        sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        ok = authenticate_webhook({"body": body}, sig, SECRET, timestamp=1000, now=1100)
        stale = authenticate_webhook({"body": body}, sig, SECRET, timestamp=1000, now=9999)
        assert ok.accepted and not stale.accepted and "replay" in stale.reason


class TestWebhookHandler:
    def setup_method(self):
        self.cfg = Settings(
            webhook_secret_arn="whsec-arn", trigger_topic_arn="arn:aws:sns:us-east-1:1:trigger"
        )

    def call(self, payload, secret=SECRET, ts=None, signature_secret=SECRET):
        body = json.dumps(payload)
        sig = hmac.new(signature_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        secrets = MagicMock()
        secrets.get_secret_value.return_value = {"SecretString": secret}
        sns = MagicMock()
        event = {
            "body": body,
            "headers": {
                "Sentry-Hook-Signature": sig,
                "Sentry-Hook-Timestamp": str(ts or time.time()),
            },
        }
        out = handlers.webhook_handler(
            event, None, settings=self.cfg, secrets_client=secrets, sns_client=sns
        )
        return out, sns, secrets

    def test_a_valid_webhook_publishes_the_incident_to_sns(self):
        out, sns, secrets = self.call(sentry_payload())
        assert out["statusCode"] == 202
        message = json.loads(sns.publish.call_args.kwargs["Message"])
        assert message["incident"]["affectedService"] == "checkout-api" and message[
            "executionId"
        ].startswith("exec-")
        assert sns.publish.call_args.kwargs["TopicArn"].endswith(":trigger")
        secrets.get_secret_value.assert_called_once_with(
            SecretId="whsec-arn"
        )  # read at use, not from the environment

    def test_a_bad_signature_publishes_nothing(self):
        out, sns, _ = self.call(sentry_payload(), signature_secret="attacker")
        assert out["statusCode"] == 401
        sns.publish.assert_not_called()

    def test_a_replayed_webhook_publishes_nothing(self):
        out, sns, _ = self.call(sentry_payload(), ts=time.time() - 3600)
        assert out["statusCode"] == 401 and "replay" in json.loads(out["body"])["error"]
        sns.publish.assert_not_called()

    def test_no_configured_secret_fails_closed(self):
        self.cfg = Settings(trigger_topic_arn="t")
        out, sns, _ = self.call(sentry_payload())
        assert out["statusCode"] == 401
        sns.publish.assert_not_called()

    def test_a_webhook_we_do_not_act_on_is_acknowledged_not_published(self):
        out, sns, _ = self.call({"action": "installed", "data": {}})
        assert out["statusCode"] == 200 and "ignored" in json.loads(out["body"])
        sns.publish.assert_not_called()


# ------------------------------------------------------------- state machine steps


class TestLambdaHandlers:
    def test_ingest_route_pr_and_notify_hand_the_run_along_through_s3(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, h):
            s.check_commands = {"unit": ["python", "-c", "print('ok')"]}
            out = handlers.ingest_handler({"executionId": "exec-L", "incident": INCIDENT}, None, s)
            assert out == {"executionId": "exec-L", "status": "running", "reason": ""}

            store = S3StateStore(s.s3, STATE_BUCKET)
            store.save(stages.investigate(store.load("exec-L"), s))
            assert handlers.route_handler({"executionId": "exec-L"}, None, s) == {
                "executionId": "exec-L",
                "status": "running",
                "fixAction": "auto_fix_pr",
            }

            store.save(stages.run_tests(stages.fix(store.load("exec-L"), s), s))
            assert handlers.pr_handler({"executionId": "exec-L"}, None, s)["status"] == "pr_opened"
            assert (
                handlers.notify_handler({"executionId": "exec-L"}, None, s)["status"] == "pr_opened"
            )
            assert h["notifier"].sent[0][0].startswith("[INFO] [Healer] demo-app: Fix ready")

    def test_ingest_reports_a_dropped_alert_so_the_state_machine_can_stop(self, tmp_path):
        with local_services(guardrail_reply="MALICIOUS", work_dir=tmp_path) as (s, _):
            out = handlers.ingest_handler({"executionId": "exec-D", "incident": INCIDENT}, None, s)
            assert out["status"] == "blocked"

    def test_notify_escalation_and_failure_modes(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, h):
            store = S3StateStore(s.s3, STATE_BUCKET)
            store.save(stages.investigate(stages.ingest(PipelineState("exec-E", INCIDENT), s), s))
            out = handlers.notify_handler(
                {"executionId": "exec-E", "mode": "escalate", "reason": "needs a human"}, None, s
            )
            assert (
                out["status"] == "escalated"
                and "Needs a human" in h["notifier"].sent[0][0] + h["notifier"].sent[0][1]
            )
            out = handlers.notify_handler(
                {
                    "executionId": "exec-E",
                    "mode": "failure",
                    "stage": "fix",
                    "error": {"Cause": "task failed: OOM"},
                },
                None,
                s,
            )
            assert out["status"] == "escalated"
            assert (
                "pipeline error in fix" in h["notifier"].sent[1][0]
                and "OOM" in h["notifier"].sent[1][1]
            )

    def test_the_gate_fails_closed_for_a_run_with_no_decision(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            S3StateStore(s.s3, STATE_BUCKET).save(PipelineState("exec-N", INCIDENT))
            assert (
                handlers.route_handler({"executionId": "exec-N"}, None, s)["fixAction"]
                == "investigation_only"
            )


# ------------------------------------------------------------------------ fargate


class TestTaskRunner:
    def test_a_task_loads_state_runs_its_stage_and_saves(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            store = S3StateStore(s.s3, STATE_BUCKET)
            store.save(stages.ingest(PipelineState("exec-T", INCIDENT), s))
            state = run_task("investigate", "exec-T", s)
            assert (
                state.composite == 90
                and store.load("exec-T").decision["fix_action"] == "auto_fix_pr"
            )

    def test_unknown_tasks_and_missing_configuration_are_rejected(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _), pytest.raises(SystemExit):
            run_task("deploy", "x", s)
        assert task_main(["investigate"], env={}) == 2
        assert task_main([], env={"EXECUTION_ID": "x"}) == 2


# ------------------------------------------------------------------- configuration


class TestSettings:
    def test_it_reads_the_environment(self):
        cfg = Settings.from_env(
            {
                "HEALER_AUDIT_BUCKET": "b",
                "HEALER_PHASE": "shadow",
                "GITHUB_REPO_URL": "https://github.com/acme/api.git",
                "HEALER_SERVICE_REGISTRY": '{"api": {"estimated_users": 10}}',
                "HEALER_MAX_DAILY_PRS": "5",
            }
        )
        assert (cfg.audit_bucket, cfg.phase, cfg.max_daily_prs) == ("b", "shadow", 5)
        assert cfg.registry == {"api": {"estimated_users": 10}} and cfg.repo_owner_and_name == (
            "acme",
            "api",
        )

    def test_defaults_are_safe(self):
        cfg = Settings.from_env({})
        assert (
            cfg.phase == "supervised"
            and cfg.max_daily_prs == 3
            and cfg.unknown_service_tier == "medium"
        )

    def test_a_malformed_repo_url_is_rejected(self):
        with pytest.raises(ValueError):
            Settings(github_repo_url="https://github.com/just-an-owner").repo_owner_and_name

    def test_services_never_read_the_github_secret_until_a_stage_needs_it(self):
        with mock_aws():
            boto3.client("s3").create_bucket(Bucket="healer-test-bucket")
            sm = boto3.client("secretsmanager")
            sm.create_secret(Name="gh", SecretString=json.dumps({"token": "ghp_x"}))
            cfg = Settings(
                audit_bucket="healer-test-bucket",
                github_secret_arn="gh",
                github_repo_url="https://github.com/a/b",
            )
            session = MagicMock(wraps=boto3)
            secrets = MagicMock(wraps=sm)
            session.client = lambda name, **kw: (
                secrets if name == "secretsmanager" else boto3.client(name, **kw)
            )
            svc = build_services(cfg, session=session)
            assert not secrets.get_secret_value.called
            assert svc.phase.value == "supervised" and svc.throttle.max_daily_prs == 3


# ----------------------------------------------------------------------------- git


class TestGitAuth:
    def test_the_token_is_a_header_never_a_url(self):
        header = basic_auth_header("ghp_secret")
        assert header.startswith("Authorization: Basic ") and "ghp_secret" not in header

    def test_a_failed_clone_never_echoes_the_token(self, tmp_path):
        with pytest.raises(GitError) as err:
            clone_repo("file:///does/not/exist", "main", tmp_path / "x", token="ghp_supersecret")
        assert "ghp_supersecret" not in str(err.value)

    def test_a_clone_works_and_its_config_holds_no_credentials(self, tmp_path):
        from healer.demo import make_repo

        remote, _ = make_repo(tmp_path)
        git = clone_repo(f"file://{remote}", "main", tmp_path / "c", token="ghp_x")
        config = (tmp_path / "c" / ".git" / "config").read_text()
        assert "ghp_x" not in config and "extraHeader" not in config
        assert git.read_file("src/auth.py").startswith('"""A small app')


class TestLogFetcher:
    def test_it_fetches_the_last_lines_in_time_order_and_never_raises(self):
        logs = MagicMock()
        logs.filter_log_events.return_value = {
            "events": [{"timestamp": 2, "message": "E2"}, {"timestamp": 1, "message": "E1"}]
        }
        assert make_log_fetcher(logs)(INCIDENT) == "E1\nE2"
        assert "filterPattern" not in logs.filter_log_events.call_args.kwargs  # every level
        logs.filter_log_events.side_effect = TimeoutError("down")
        assert make_log_fetcher(logs)(INCIDENT) == ""

    def test_ingest_attaches_logs_the_alert_did_not_carry(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            bare = {k: v for k, v in INCIDENT.items() if k != "logs"}
            s.fetch_logs = lambda incident: "\n".join(f"ERROR line {i}" for i in range(30))
            state = stages.ingest(PipelineState("exec-F", bare), s)
            assert len(state.log_lines) == 20 and state.log_lines[-1] == "ERROR line 29"


def test_a_crash_before_any_state_was_saved_still_notifies_a_human(tmp_path):
    """Found on real AWS: INGEST crashed first, so there was no state for the failure notice."""
    with local_services(work_dir=tmp_path) as (services, handles):
        out = handlers.notify_handler(
            {
                "mode": "failure",
                "executionId": "exec-nostate",
                "stage": "ingest",
                "incident": INCIDENT,
                "error": {"Cause": "boom"},
            },
            services=services,
        )
    assert out["status"] == "escalated" and handles["notifier"].sent
    assert "boom" in handles["notifier"].sent[0][1]
