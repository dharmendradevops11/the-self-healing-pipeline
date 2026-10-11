"""Chapter 8: what happens when you give an AI write access."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from healer.gate import compute_confidence, compute_signal_strength, decide
from healer.investigate import (
    AgentExecutor,
    ToolRegistry,
    UnknownToolError,
    contains_resource_keywords,
    extract_stack_trace,
    investigate_failure,
    parse_file_paths_from_trace,
    safe_tool_call,
)
from healer.library.memory_investigation import (
    correlate_memory_with_activity,
    detect_memory_anomaly,
)
from healer.llm import ReplayProvider

# ------------------------------------------------------------------- the tool model


class TestToolRegistry:
    def registry(self):
        r = ToolRegistry()
        r.register(
            "read_logs",
            lambda service, lines: f"{service}:{lines}",
            "Read recent logs",
            {"service": {"type": "string"}, "lines": {"type": "integer"}},
        )
        return r

    def test_converts_tools_to_the_bedrock_schema(self):
        schema = self.registry().as_bedrock_schema()
        assert schema == [
            {
                "name": "read_logs",
                "description": "Read recent logs",
                "input_schema": {
                    "type": "object",
                    "properties": {"service": {"type": "string"}, "lines": {"type": "integer"}},
                    "required": ["service", "lines"],
                },
            }
        ]

    def test_describes_tools_for_the_prompt_and_calls_them(self):
        r = self.registry()
        assert r.describe() == "- read_logs: Read recent logs"
        assert r.call("read_logs", {"service": "api", "lines": 5}) == "api:5"

    def test_an_unregistered_tool_cannot_be_called(self):
        with pytest.raises(UnknownToolError):
            self.registry().call("delete_everything", {})


class TestSafeToolCall:
    def test_success(self):
        assert safe_tool_call(lambda: 42) == {"success": True, "data": 42, "error": None}

    def test_an_optional_failure_degrades_with_the_fallback(self):
        def get_metrics():
            raise TimeoutError("cloudwatch slow")

        out = safe_tool_call(get_metrics, fallback_value={"note": "unavailable"})
        assert out == {
            "success": False,
            "data": {"note": "unavailable"},
            "error": "cloudwatch slow",
            "tool": "get_metrics",
        }

    def test_a_required_failure_fails_fast(self):
        def read_source():
            raise FileNotFoundError("no source")

        with pytest.raises(FileNotFoundError):
            safe_tool_call(read_source, required=True)


# ----------------------------------------------------------------- the agent executor


class TestAgentExecutor:
    @pytest.fixture
    def s3(self):
        with mock_aws():
            client = boto3.client("s3")
            client.create_bucket(Bucket="pipeline-agent-state")
            client.put_object(
                Bucket="pipeline-agent-state",
                Key="run-1/context.json",
                Body=json.dumps({"error": "boom"}),
            )
            yield client

    def response(self, blocks):
        return {"body": MagicMock(read=lambda: json.dumps({"content": blocks}))}

    def test_runs_the_requested_tools_and_stores_the_result(self, s3):
        registry = ToolRegistry()
        registry.register(
            "read_logs",
            lambda service: f"logs of {service}",
            "Read logs",
            {"service": {"type": "string"}},
        )
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = self.response(
            [
                {"type": "text", "text": "Checking the logs."},
                {"type": "tool_use", "id": "t1", "name": "read_logs", "input": {"service": "api"}},
            ]
        )
        result = AgentExecutor(bedrock, s3, registry, model_id="m").execute("run-1")
        assert result["text"] == "Checking the logs."
        assert result["tool_results"] == [
            {"tool": "read_logs", "id": "t1", "result": "logs of api"}
        ]
        sent = json.loads(bedrock.invoke_model.call_args.kwargs["body"])
        assert (
            sent["tools"][0]["name"] == "read_logs"
            and "read_logs" in sent["messages"][0]["content"]
        )
        assert '"error": "boom"' in sent["messages"][0]["content"]
        stored = json.loads(
            s3.get_object(Bucket="pipeline-agent-state", Key="run-1/result.json")["Body"].read()
        )
        assert stored["tool_results"][0]["result"] == "logs of api"

    def test_unregistered_and_failing_tools_are_recorded_not_raised(self, s3):
        registry = ToolRegistry()
        registry.register("boom", lambda: 1 / 0, "Always fails", {})
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = self.response(
            [
                {"type": "tool_use", "id": "a", "name": "rm_rf", "input": {}},
                {"type": "tool_use", "id": "b", "name": "boom", "input": {}},
            ]
        )
        out = AgentExecutor(bedrock, s3, registry).execute("run-1")
        assert "not registered" in out["tool_results"][0]["error"]
        assert out["tool_results"][1]["error"].startswith("ZeroDivisionError")


# --------------------------------------------------------------- investigating a failure

TRACE = (
    "2026-10-09 ERROR request failed\n"
    "Traceback (most recent call last):\n"
    '  File "src/auth.py", line 24, in get_display_name\n'
    '  File "src/session.py", line 9, in load\n'
    "AttributeError: 'NoneType' object has no attribute 'name'\n"
)
DIAGNOSIS = {
    "rootCauseHypothesis": "profile is None for first-time users in src/auth.py:24",
    "confidenceScore": 91,
    "evidenceSummary": "trace and code agree",
    "affectedFiles": ["src/auth.py"],
}
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


class TestParsing:
    def test_extracts_the_traceback_and_the_files_it_names(self):
        assert extract_stack_trace(TRACE).startswith("Traceback (most recent call last)")
        assert parse_file_paths_from_trace(TRACE) == ["src/auth.py", "src/session.py"]

    def test_paths_are_deduplicated_and_traversal_is_dropped(self):
        trace = 'File "src/a.py"\nFile "src/a.py"\nFile "../etc/x.py"\nat lib/b.ts:3'
        assert parse_file_paths_from_trace(trace) == ["src/a.py", "lib/b.ts"]

    def test_a_trace_without_a_marker_is_kept_whole(self):
        assert extract_stack_trace("just text") == "just text"

    def test_resource_keywords(self):
        assert contains_resource_keywords({"a.py": "self.cache_ttl = 604800"})
        assert not contains_resource_keywords({"a.py": "def greet(): return 'hi'"})


def make_event():
    return {"log_stream": TRACE, "repo": "demo", "timestamp": NOW, "message": "AttributeError"}


def llm():
    return ReplayProvider([("investigating a production error", json.dumps(DIAGNOSIS))])


class TestInvestigateFailure:
    files = {
        "src/auth.py": "def get_display_name(s):\n    return s.profile.name\n",
        "src/session.py": "def load(): pass\n",
    }

    def run(self, **overrides):
        args = {
            "failure_event": make_event(),
            "llm": llm(),
            "read_file": lambda repo, path: self.files[path],
            "get_git_history": lambda **kw: "abc123 add profile lookup",
            "log_context": "line1\nline2\nline3",
        }
        args.update(overrides)
        return investigate_failure(**args)

    def test_a_clean_investigation_produces_a_diagnosis_and_evidence(self):
        result = self.run()
        assert result.diagnosis.confidence_score == 91
        assert result.diagnosis.affected_files == ["src/auth.py"]
        assert set(result.source_files) == {"src/auth.py", "src/session.py"}
        ev = result.evidence
        assert (
            ev.log_lines,
            ev.has_stack_trace,
            ev.files_implied,
            ev.files_read,
            ev.has_commit_context,
        ) == (3, True, 2, 2, True)
        assert result.degraded == [] and result.metrics_used is False

    def test_metrics_are_fetched_only_when_the_source_hints_at_a_resource_problem(self):
        metrics = MagicMock(return_value={"MemoryUtilization": 91})
        self.run(get_cloudwatch_metrics=metrics)
        metrics.assert_not_called()  # greeting code has no resource keywords

        leaky = {"src/auth.py": "cache = {}  # never evicted\n", "src/session.py": "x = 1\n"}
        result = self.run(read_file=lambda repo, path: leaky[path], get_cloudwatch_metrics=metrics)
        assert metrics.call_count == 1 and result.metrics_used is True
        kw = metrics.call_args.kwargs
        assert kw["namespace"] == "AWS/ECS" and kw["end"] - kw["start"] == timedelta(hours=2)

    def test_the_prompt_the_model_sees_carries_the_code_and_the_history(self):
        provider = llm()
        self.run(llm=provider)
        prompt = provider.prompts[0]
        assert "s.profile.name" in prompt and "abc123 add profile lookup" in prompt

    def test_a_failing_optional_tool_degrades_the_investigation_and_says_so(self):
        def broken_history(**kw):
            raise TimeoutError("git host down")

        leaky = {"src/auth.py": "cache = {}\n", "src/session.py": "x = 1\n"}
        metrics = MagicMock(side_effect=TimeoutError("cloudwatch down"))
        result = self.run(
            get_git_history=broken_history,
            read_file=lambda r, p: leaky[p],
            get_cloudwatch_metrics=metrics,
        )
        assert result.degraded == ["git_history", "metrics"]
        assert result.evidence.has_commit_context is False
        assert result.diagnosis.confidence_score == 91  # still diagnosed, on less evidence

    def test_unreadable_source_stops_the_investigation(self):
        def missing(repo, path):
            raise FileNotFoundError(path)

        with pytest.raises(RuntimeError, match="implicated source files"):
            self.run(read_file=missing)

    def test_it_reads_at_most_five_files(self):
        trace = "Traceback (most recent call last)\n" + "\n".join(
            f'File "src/f{i}.py"' for i in range(9)
        )
        read = MagicMock(return_value="x = 1\n")
        investigate_failure({**make_event(), "log_stream": trace}, llm(), read, lambda **kw: "")
        assert read.call_count == 5


class TestFromEvidenceToTheGate:
    def test_the_investigation_feeds_the_chapter_9_decision(self):
        """Evidence from INVESTIGATE becomes a composite score, then a routing decision."""
        files = {
            "src/auth.py": "def f(s):\n    return s.profile.name\n",
            "src/session.py": "x = 1\n",
        }
        result = investigate_failure(
            make_event(),
            llm(),
            lambda r, p: files[p],
            lambda **kw: "abc fix",
            log_context="\n".join(["l"] * 20),
        )
        signal = compute_signal_strength(result.evidence)
        assert signal == pytest.approx(1.0)
        composite = compute_confidence(signal, result.diagnosis.confidence_score / 100, None)
        decision = decide(
            "demo", composite, {"demo": {"estimated_users": 1200, "owner": "platform"}}
        )
        # signal 1.0 x 0.30 + model 0.91 x 0.575 + neutral history 0.5 x 0.125 = 0.886
        assert composite == 89 and decision.band == "high"
        assert decision.fix_action == "auto_fix_pr" and decision.fix_authorized


# -------------------------------------------------------------- memory, then logic


def memory_points(averages, start=datetime(2026, 10, 8, 12, 0, tzinfo=UTC)):
    return {
        "Datapoints": [
            {"Timestamp": start + timedelta(minutes=5 * i), "Average": a}
            for i, a in enumerate(averages)
        ]
    }


class TestMemoryAnomaly:
    def cw(self, averages):
        cw = MagicMock()
        cw.get_metric_statistics.return_value = memory_points(averages)
        return cw

    def test_a_steady_service_is_not_anomalous(self):
        assert detect_memory_anomaly(self.cw([50.0] * 60), "api")["is_anomalous"] is False

    def test_fast_growth_ending_above_70_percent_is_anomalous(self):
        out = detect_memory_anomaly(self.cw([40.0] * 24 + [75.0] * 24), "api")
        assert out["is_anomalous"] is True and out["current_memory_pct"] == 75.0
        assert all(p["growth_rate"] > 0.3 for p in out["growth_periods"])

    def test_growth_that_stays_below_70_percent_is_not_anomalous(self):
        assert (
            detect_memory_anomaly(self.cw([20.0] * 24 + [30.0] * 24), "api")["is_anomalous"]
            is False
        )

    def test_guards_for_no_data_and_zero_memory(self):
        assert detect_memory_anomaly(self.cw([]), "api") == {
            "is_anomalous": False,
            "current_memory_pct": None,
            "growth_periods": [],
        }
        assert (
            detect_memory_anomaly(self.cw([0.0] * 24 + [80.0] * 24), "api")["growth_periods"] == []
        )


class TestCorrelation:
    def test_it_looks_an_hour_around_each_growth_period(self):
        period_time = datetime(2026, 10, 9, 6, 0, tzinfo=UTC)
        query, commits = MagicMock(return_value=["err"]), MagicMock(return_value=["abc"])
        out = correlate_memory_with_activity(
            "api", {"growth_periods": [{"timestamp": period_time}]}, query, commits
        )
        assert out == [{"timestamp": period_time, "logs": ["err"], "commits": ["abc"]}]
        args = query.call_args.args
        assert args[0] == "api" and "like /error/" in args[1]
        assert args[3] - args[2] == timedelta(hours=1)
        assert correlate_memory_with_activity("api", {"growth_periods": []}, query, commits) == []


class TestEnrichmentChapter2AsksFor:
    """Chapter 2's prompt has slots for the recent deploy, dependency changes and metric history."""

    def test_the_prompt_receives_all_three_when_the_tools_exist(self):
        from datetime import UTC, datetime

        from healer.investigate import investigate_failure
        from healer.llm import ReplayProvider

        llm = ReplayProvider(
            [
                (
                    "investigating",
                    '{"rootCauseHypothesis": "x", "confidenceScore": 70, '
                    '"evidenceSummary": "e", "affectedFiles": []}',
                )
            ]
        )
        investigate_failure(
            {
                "log_stream": 'Traceback\n  File "src/a.py", line 3, in f\nValueError: boom',
                "repo": "r",
                "timestamp": datetime(2026, 10, 9, tzinfo=UTC),
                "message": "ValueError: boom",
            },
            llm,
            read_file=lambda repo, path: "x = 1",
            get_git_history=lambda **kw: "abc1234 fix",
            get_recent_deployment=lambda: "latest commit: deadbee by Ada: ship it",
            get_dependency_changes=lambda: "commit 1 bump requests",
        )
        prompt = llm.prompts[0]
        assert "deadbee by Ada" in prompt and "bump requests" in prompt

    def test_a_failing_enrichment_tool_degrades_the_answer_instead_of_stopping_it(self):
        from datetime import UTC, datetime

        from healer.investigate import investigate_failure
        from healer.llm import ReplayProvider

        def broken() -> str:
            raise RuntimeError("git exploded")

        llm = ReplayProvider(
            [
                (
                    "investigating",
                    '{"rootCauseHypothesis": "x", "confidenceScore": 70, '
                    '"evidenceSummary": "e", "affectedFiles": []}',
                )
            ]
        )
        result = investigate_failure(
            {
                "log_stream": 'Traceback\n  File "src/a.py", line 3, in f\nValueError: boom',
                "repo": "r",
                "timestamp": datetime(2026, 10, 9, tzinfo=UTC),
            },
            llm,
            read_file=lambda repo, path: "x = 1",
            get_git_history=lambda **kw: "abc",
            get_recent_deployment=broken,
        )
        assert "deployment" in result.degraded

    def test_git_reports_the_latest_change_and_recent_dependency_edits(self, tmp_path):
        import subprocess

        from healer.fix.git_ops import LocalGit

        def git(*a):
            subprocess.run(
                ["git", "-c", "user.name=T", "-c", "user.email=t@e.x", *a],
                cwd=tmp_path,
                check=True,
                capture_output=True,
            )

        git("init", "-q", "-b", "main")
        (tmp_path / "requirements.txt").write_text("requests==2.30\n")
        git("add", "-A")
        git("commit", "-qm", "pin requests")
        (tmp_path / "requirements.txt").write_text("requests==2.31\n")
        git("commit", "-qam", "bump requests")
        repo = LocalGit(tmp_path)
        assert "bump requests" in repo.recent_deployment() and "proxy" in repo.recent_deployment()
        changes = repo.dependency_changes()
        assert "+requests==2.31" in changes and "-requests==2.30" in changes

    def test_the_metrics_fetcher_summarises_each_series(self):
        from datetime import UTC, datetime
        from unittest.mock import MagicMock

        from healer.ingest.enrich import make_metrics_fetcher

        cw = MagicMock()
        cw.list_metrics.return_value = {
            "Metrics": [{"Dimensions": [{"Name": "ServiceName", "Value": "api"}]}]
        }
        t0 = datetime(2026, 10, 9, 10, tzinfo=UTC)
        cw.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Timestamp": t0, "Average": 50.0, "Maximum": 60.0},
                {"Timestamp": t0.replace(hour=11), "Average": 90.123, "Maximum": 95.0},
            ]
        }
        out = make_metrics_fetcher(cw)(
            namespace="AWS/ECS", metrics=["MemoryUtilization"], start=t0, end=t0
        )
        assert out == {
            "MemoryUtilization[ServiceName=api]": {"latest_avg": 90.12, "peak": 95.0, "points": 2}
        }
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        import pytest

        with pytest.raises(LookupError):
            make_metrics_fetcher(cw)(namespace="AWS/ECS", metrics=["X"], start=t0, end=t0)
