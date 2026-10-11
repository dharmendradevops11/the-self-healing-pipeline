"""Checks that tie the repository to BOOK_SPEC.md: the knobs and files the book names."""

from pathlib import Path

import yaml

from healer.config import Settings
from healer.gate import decide
from healer.gate.escalation import confidence_band
from healer.guardrails.patch_policy import DEFAULT_POLICY, PatchPolicy
from infra.config import DeployConfig
from tests.unit.test_infra import synth

ROOT = Path(__file__).resolve().parents[2]


def test_config_allowlist_yaml_is_the_chapter_17_file():
    assert yaml.safe_load((ROOT / "config" / "allowlist.yaml").read_text()) == yaml.safe_load(
        DEFAULT_POLICY
    )
    policy = PatchPolicy.from_file(ROOT / "config" / "allowlist.yaml")
    assert policy.path_allowed("src/app.py") and not policy.path_allowed("src/.env.production")


def test_the_fix_threshold_is_60_and_a_deployment_parameter():
    assert confidence_band(59) == "low" and confidence_band(60) == "medium"
    assert confidence_band(75, fix_threshold=70) == "medium"
    assert confidence_band(65, fix_threshold=70) == "low"  # Chapter 18: start at 70 to be careful
    registry = {"svc": {"owner": "t", "estimated_users": 10}}
    assert decide("svc", 65, registry).fix_authorized
    assert not decide("svc", 65, registry, fix_threshold=70).fix_authorized


def test_threshold_and_log_lines_flow_from_the_environment_and_cdk_context():
    s = Settings.from_env({"HEALER_CONFIDENCE_THRESHOLD": "70", "HEALER_LOG_LINES": "30"})
    assert (s.fix_threshold, s.log_lines) == (70, 30)
    assert (Settings().fix_threshold, Settings().log_lines) == (60, 20)  # the book's defaults
    cfg = DeployConfig.from_context(
        {"healer:confidence_threshold": "70", "healer:log_lines": "30"}.get
    )
    assert (cfg.confidence_threshold, cfg.log_lines) == (70, 30)
    _, pipeline, _ = synth(confidence_threshold=70, log_lines=30)
    envs = [
        r["Properties"]["Environment"]["Variables"]
        for r in pipeline.find_resources("AWS::Lambda::Function").values()
        if "Environment" in r["Properties"]
    ]
    assert any(
        e.get("HEALER_CONFIDENCE_THRESHOLD") == "70" and e.get("HEALER_LOG_LINES") == "30"
        for e in envs
    )


def test_chapter_14_always_shows_a_human_why_an_issue_is_not_routine():
    from healer.gate.human_review import human_review_flags

    assert human_review_flags("low", 0.9, [], ["src/a.py"], owner="team") == []
    assert "unowned" in human_review_flags("low", 0.9, [], ["src/a.py"], owner="unassigned")[0]
    flags = human_review_flags("critical", None, [], ["src/a.py"], owner="team")
    assert len(flags) == 2 and "critical" in flags[0] and "new failure pattern" in flags[1]
    prior = [{"incident_id": "x1", "human_decision": "merged", "files_changed": ["src/a.py"]}]
    assert "recurring" in human_review_flags("low", 0.9, prior, ["src/a.py"], owner="team")[0]
    rejected = [{"incident_id": "x2", "human_decision": "rejected", "files_changed": ["src/a.py"]}]
    assert human_review_flags("low", 0.9, rejected, ["src/a.py"], owner="team") == []


def test_the_pipeline_labels_and_announces_the_flags(tmp_path):
    import json

    from healer.demo import SCENARIOS, local_services
    from healer.pipeline import run_pipeline

    incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
    with local_services(work_dir=tmp_path) as (services, handles):
        services.check_commands = {"noop": ["true"]}
        result = run_pipeline(incident, services)
    assert result.pr is not None and "healer: human-review" in result.pr.labels  # no history yet
    assert any("Human review required" in body for _, body in handles["notifier"].sent)


def test_a_billing_alarm_is_optional_and_notifies_the_topic():
    state, _, _ = synth()
    state.resource_count_is("AWS::CloudWatch::Alarm", 0)
    state, _, _ = synth(billing_alarm_usd=50)
    state.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {"MetricName": "EstimatedCharges", "Namespace": "AWS/Billing", "Threshold": 50},
    )


def test_appendix_h_retention_audit_90_days_heap_dumps_7_days(stacks=None):
    state, _, _ = synth()
    rules = [
        rule
        for r in state.find_resources("AWS::S3::Bucket").values()
        for rule in r["Properties"].get("LifecycleConfiguration", {}).get("Rules", [])
    ]
    by_id = {r["Id"]: r for r in rules}
    assert by_id["prune-audit-records"]["ExpirationInDays"] == 90
    assert by_id["expire-heap-dumps"]["ExpirationInDays"] == 7
    assert DeployConfig().audit_retention_days == 90


def test_the_github_client_needs_no_third_party_http_library():
    """Found on real AWS: the Lambda runtime has no `requests`."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from healer.pr.hosts import GitHubPRHost

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(201)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            seen.append(
                (self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            )
            self._reply({"number": 7, "html_url": "http://example/pr/7"})

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        host = GitHubPRHost("o", "r", "tok", api=f"http://127.0.0.1:{server.server_port}")
        pr = host.open_pull_request(
            title="t", body="b", branch="healer/x", base="main", labels=["healer"], draft=False
        )
    finally:
        server.shutdown()
    assert pr.number == 7 and pr.url == "http://example/pr/7"
    assert [p for p, _ in seen] == ["/repos/o/r/pulls", "/repos/o/r/issues/7/labels"]


class TestMonitoringTheHealer:
    """Chapter 14: per-stage time, end-to-end time, one trace id."""

    def test_every_stage_reports_its_duration_with_the_execution_id(self, tmp_path, capsys):
        import json

        from healer.demo import SCENARIOS, local_services
        from healer.pipeline import run_pipeline

        incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
        with local_services(work_dir=tmp_path) as (services, _):
            services.check_commands = {"noop": ["true"]}
            run_pipeline(incident, services, execution_id="exec-trace1")
        records = [
            json.loads(line)
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("{") and "_aws" in line
        ]
        stages = {r["Stage"] for r in records if "StageSeconds" in r}
        assert {"ingest", "investigate", "fix", "test", "pr", "notify"} <= stages
        assert {r["execution_id"] for r in records} == {"exec-trace1"}  # one trace id throughout
        assert any("EndToEndSeconds" in r and r["Outcome"] == "pr_opened" for r in records)

    def test_the_record_is_valid_embedded_metric_format(self):
        import json

        from healer.telemetry import emf

        record = json.loads(emf("StageSeconds", 1.5, "Seconds", "exec-1", Stage="fix"))
        directive = record["_aws"]["CloudWatchMetrics"][0]
        assert directive["Dimensions"] == [["Stage"]] and record["StageSeconds"] == 1.5
        assert directive["Metrics"] == [{"Name": "StageSeconds", "Unit": "Seconds"}]


def test_the_escalate_lambda_can_open_its_report_pr_without_git():
    """Found on real AWS: a Lambda has no git binary, so the report branch goes through the API."""
    from healer.pr.hosts import GitHubPRHost

    calls = []

    class Reply:
        def __init__(self, payload=None):
            self.payload = payload or {}

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class Session:
        headers: dict = {}

        def get(self, url, **kw):
            calls.append(("GET", url))
            return Reply({"object": {"sha": "abc123"}})

        def post(self, url, json=None, **kw):
            calls.append(("POST", url, json))
            return Reply()

    GitHubPRHost("o", "r", "tok", session=Session()).create_branch("healer/x", "main")
    assert calls == [
        ("GET", "https://api.github.com/repos/o/r/git/ref/heads/main"),
        (
            "POST",
            "https://api.github.com/repos/o/r/git/refs",
            {"ref": "refs/heads/healer/x", "sha": "abc123"},
        ),
    ]


def test_the_sns_notifier_logs_what_it_sent_and_where(capsys):
    """Asked for in the AWS walkthrough: the Notify hop must leave a readable line."""
    import json
    from unittest.mock import MagicMock

    from healer.gate import decide
    from healer.notify.notifiers import SNSNotifier

    sns = MagicMock()
    sns.publish.return_value = {"MessageId": "mid-1"}
    decision = decide("svc", 90, {"svc": {"owner": "t", "estimated_users": 10}})
    SNSNotifier(sns, "arn:topic").send("[INFO] subject", "the body", decision)
    line = next(
        json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith('{"hop"')
    )
    assert line["hop"] == "notify->sns" and line["sns_message_id"] == "mid-1"
    assert line["subject"] == "[INFO] subject" and line["message"] == "the body"
    assert line["attributes"]["fixAction"] == "auto_fix_pr"


def test_the_slack_notifier_logs_its_hop_without_the_url(capsys):
    import json
    from unittest.mock import MagicMock

    from healer.gate import decide
    from healer.notify.notifiers import SlackNotifier

    session = MagicMock()
    session.post.return_value.status_code = 200
    url = "https://hooks.slack.com/services/T000/B000/secretvalue"
    decision = decide("svc", 90, {"svc": {"owner": "t", "estimated_users": 10}})
    SlackNotifier(url, session=session).send("[INFO] subject", "body", decision)
    out = capsys.readouterr().out
    assert json.loads(out.splitlines()[0]) == {
        "hop": "notify->slack",
        "status": 200,
        "subject": "[INFO] subject",
    }
    assert "secretvalue" not in out and "hooks.slack.com" not in out


class TestSlackSecretIsReadOnlyWhenSending:
    """Found on real AWS: building the services read the Slack secret, so INGEST failed with AccessDenied."""

    def test_building_the_services_never_touches_the_slack_secret(self):
        from unittest.mock import MagicMock

        from healer.config import Settings, build_services

        session = MagicMock()
        secrets = session.client.return_value
        build_services(
            Settings(slack_secret_arn="arn:slack", github_secret_arn="arn:gh"), session=session
        )
        assert not any(
            c.kwargs.get("SecretId") == "arn:slack" for c in secrets.get_secret_value.call_args_list
        )

    def test_the_url_is_fetched_once_on_the_first_message_and_validated(self):
        from unittest.mock import MagicMock

        import pytest

        from healer.gate import decide
        from healer.notify.notifiers import SlackNotifier

        fetched = MagicMock(return_value="https://hooks.slack.com/services/T/B/x")
        session = MagicMock()
        session.post.return_value.status_code = 200
        notifier = SlackNotifier(fetched, session=session)
        assert fetched.call_count == 0
        d = decide("svc", 90, {"svc": {"owner": "t", "estimated_users": 10}})
        notifier.send("a", "b", d)
        notifier.send("c", "d", d)
        assert fetched.call_count == 1 and session.post.call_count == 2
        with pytest.raises(ValueError):
            SlackNotifier("https://evil.example/hook")

    def test_a_secret_that_cannot_be_read_never_stops_the_pipeline(self):
        from unittest.mock import MagicMock

        from healer.gate import decide
        from healer.notify.notifiers import SlackNotifier

        def denied() -> str:
            raise PermissionError("AccessDenied")

        d = decide("svc", 90, {"svc": {"owner": "t", "estimated_users": 10}})
        SlackNotifier(denied, session=MagicMock()).send("a", "b", d)  # logged, not raised
