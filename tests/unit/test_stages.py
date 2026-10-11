"""Each stage on its own, with state passed between them the way separate processes would."""

import json

from healer import stages
from healer.demo import SCENARIOS, STATE_BUCKET, local_services
from healer.pipeline import run_pipeline
from healer.state import MemoryStateStore, PipelineState, S3StateStore

INCIDENT = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
FAST = {"unit": ["python", "-c", "print('ok')"]}


class TestState:
    def test_state_survives_a_json_round_trip_with_typed_views(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            state = stages.investigate(stages.ingest(PipelineState("exec-1", INCIDENT), s), s)
            again = PipelineState.from_json(state.to_json())
            assert again == state
            assert again.diagnosis_obj().confidence_score == 93
            assert again.decision_obj().fix_action == "auto_fix_pr"
            assert again.decision_obj().fix_authorized and again.composite == 90

    def test_the_state_never_carries_source_code(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            state = stages.investigate(stages.ingest(PipelineState("exec-1", INCIDENT), s), s)
            assert "def get_display_name" not in state.to_json()

    def test_stores_round_trip(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            state = PipelineState("exec-9", INCIDENT, status="escalated", reason="because")
            for store in (MemoryStateStore(), S3StateStore(s.s3, STATE_BUCKET)):
                store.save(state)
                assert store.load("exec-9") == state

    def test_the_s3_state_bus_uses_the_documented_key(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            run_pipeline(INCIDENT, s, execution_id="exec-bus")
            body = s.s3.get_object(Bucket=STATE_BUCKET, Key="pipeline-state/exec-bus/state.json")[
                "Body"
            ].read()
            final = json.loads(body)
            assert final["status"] == "pr_opened" and final["branch"].startswith("healer/")
            assert final["pr"]["labels"][0] == "healer" and final["notified"] is True


class TestStagesRunIndependently:
    def test_a_later_stage_needs_only_the_saved_state(self, tmp_path):
        """FIX, TEST and PR each re-open the repository themselves, as separate containers do."""
        with local_services(work_dir=tmp_path) as (s, h):
            s.check_commands = FAST
            store = MemoryStateStore()
            state = PipelineState("exec-ind", INCIDENT)
            for stage in (stages.ingest, stages.investigate):
                store.save(state)
                state = stage(store.load("exec-ind"), s)
            assert stages.route(state) == "auto_fix_pr"

            store.save(state)
            state = stages.fix(store.load("exec-ind"), s)  # a "new process": state only
            assert state.branch and not state.terminal
            store.save(state)
            state = stages.run_tests(store.load("exec-ind"), s)
            store.save(state)
            state = stages.open_pr(store.load("exec-ind"), s)
            assert state.status == "pr_opened" and state.pr["number"] == 1

    def test_audit_numbering_continues_across_stages(self, tmp_path):
        with local_services(work_dir=tmp_path) as (s, _):
            state = stages.ingest(PipelineState("exec-aud", INCIDENT), s)
            state = stages.investigate(state, s)
            names = [k.split("/")[-1] for k in state.audit_keys]
            assert names == ["step_001_ingest.json", "step_002_investigate.json"]

    def test_routing_fails_closed_without_a_decision(self):
        assert stages.route(PipelineState("e", INCIDENT)) == "investigation_only"


class TestCategory:
    def test_failure_categories(self):
        assert stages.category_of({"title": "TypeError: x", "type": "crash"}) == "crash:TypeError"
        assert (
            stages.category_of({"title": "Connection refused", "type": "infra"}) == "infra:unknown"
        )
        assert stages.category_of({"title": "KeyError: 'a'"}) == "crash:KeyError"


def test_stage_log_lines_are_whole_json_with_every_field_present(tmp_path, capsys):
    """The first AWS trace cut a line mid-value ("composite": 8) and looked like a failure."""
    import json

    from healer.demo import SCENARIOS, local_services
    from healer.pipeline import run_pipeline

    incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
    with local_services(work_dir=tmp_path) as (services, _):
        services.check_commands = {"noop": ["true"]}
        run_pipeline(incident, services)
    lines = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{") and '"step"' in line
    ]
    investigate = next(r for r in lines if r["step"] == "investigate")
    assert {"root_cause", "model_certainty", "signal", "history", "composite", "decision"} <= set(
        investigate["output"]
    )
    assert isinstance(investigate["output"]["composite"], int)
    assert len(investigate["output"]["root_cause"]) <= 230  # shortened, and says by how much


def test_the_test_stage_logs_each_checks_own_output_scrubbed(tmp_path, capsys):
    """Asked for on real AWS: show the passing tests, not only the word "pass"."""
    import json

    from healer.demo import SCENARIOS, local_services
    from healer.pipeline import run_pipeline

    incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
    with local_services(work_dir=tmp_path) as (services, _):
        result = run_pipeline(incident, services)
    out = capsys.readouterr().out
    assert result.tests is not None and result.tests.overall_passed
    assert "[test:unit] pass" in out and "3 passed" in out
    assert "[test:type_check] pass" in out and "[test:lint] pass" in out


class TestFailureMessagesDoNotLeakInternalIds:
    """Seen in the real Slack channel: a failure message carried the account number and ARNs."""

    LAMBDA_ERROR = (
        '{"errorMessage": "An error occurred (AccessDeniedException) when calling the GetSecretValue '
        "operation: User: arn:aws:sts::123456789012:assumed-role/Healer-Ingest-Role/x is not authorized "
        'on resource: arn:aws:secretsmanager:us-east-1:123456789012:secret:self-healing-pipeline/slack-webhook-AbC", '
        '"errorType": "ClientError", "requestId": "r-1", "stackTrace": ["  File \\"/var/task/h.py\\""]}'
    )

    def test_arns_and_account_numbers_are_redacted_and_the_stack_is_dropped(self):
        from healer.guardrails.scrubber import summarise_error

        text = summarise_error(self.LAMBDA_ERROR)
        assert text.startswith("ClientError: An error occurred (AccessDeniedException)")
        for leaked in (
            "123456789012",
            "arn:aws",
            "Healer-Ingest-Role",
            "slack-webhook",
            "stackTrace",
        ):
            assert leaked not in text
        assert "[arn]" in text

    def test_plain_text_errors_pass_through_shortened_and_redacted(self):
        from healer.guardrails.scrubber import redact_internal_ids, summarise_error

        assert redact_internal_ids("account 123456789012 failed") == "account [account] failed"
        assert len(summarise_error("x" * 1000)) == 300
        assert "ghp_" + "a" * 36 not in summarise_error("token ghp_" + "a" * 36)

    def test_the_message_a_human_receives_is_the_redacted_one(self, tmp_path):
        import json

        from healer.demo import SCENARIOS, local_services

        incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
        with local_services(work_dir=tmp_path) as (s, handles):
            state = PipelineState("exec-leak", incident)
            S3StateStore(s.s3, STATE_BUCKET).save(state)
            stages.report_failure(state, s, "ingest", self.LAMBDA_ERROR)
        subject, body = handles["notifier"].sent[0]
        assert "123456789012" not in body and "arn:aws" not in body and "ClientError" in body
