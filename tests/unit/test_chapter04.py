"""Chapter 4: signals, not dashboards."""

import json
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from healer.ingest.logs import fetch_relevant_logs, get_relevant_logs, last_lines
from healer.library.observability import (
    StructuredLogger,
    calculate_pipeline_health_score,
    correlate_deployment_to_metrics,
    get_metric_average,
    get_metric_percentile,
)


class TestLogFetching:
    def test_fetch_relevant_logs_is_bounded_in_time_and_count(self):
        logs = MagicMock()
        logs.filter_log_events.return_value = {
            "events": [{"timestamp": 1, "message": "boom"}, {"timestamp": 2, "message": "bang"}]
        }
        text = fetch_relevant_logs(logs, "/aws/ecs/api", failure_time=1000)
        kw = logs.filter_log_events.call_args.kwargs
        assert (kw["startTime"], kw["endTime"], kw["limit"]) == (880_000, 1_000_000, 100)
        assert text == "[1] boom\n[2] bang"

    def test_get_relevant_logs_asks_only_for_error_and_fatal(self):
        logs = MagicMock()
        logs.filter_log_events.return_value = {"events": [{"message": "E1"}, {"message": "E2"}]}
        failure = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
        assert get_relevant_logs(logs, "checkout", failure) == ["E1", "E2"]
        kw = logs.filter_log_events.call_args.kwargs
        assert kw["logGroupName"] == "/aws/ecs/checkout"
        assert kw["filterPattern"] == "[level=ERROR || level=FATAL]"
        assert kw["endTime"] - kw["startTime"] == 3 * 60 * 1000

    def test_the_last_twenty_lines(self):
        assert last_lines([str(i) for i in range(50)]) == [str(i) for i in range(30, 50)]
        assert last_lines(["a", "b"]) == ["a", "b"]


class TestStructuredLogger:
    def test_emits_one_json_object_with_the_correlation_ids(self, caplog):
        with caplog.at_level(logging.INFO, logger="checkout"):
            StructuredLogger("checkout").log(
                "INFO", "paid", correlation_id="c1", trace_id="t1", order=7
            )
        entry = json.loads(caplog.records[0].message)
        assert (entry["service"], entry["level"], entry["message"]) == ("checkout", "INFO", "paid")
        assert (entry["correlation_id"], entry["trace_id"], entry["order"]) == ("c1", "t1", 7)
        assert entry["user_id"] is None and entry["timestamp"]


def fake_cloudwatch(averages, p95=None):
    cw = MagicMock()

    def get_metric_statistics(**kw):
        if "ExtendedStatistics" in kw:
            v = (p95 or {}).get(kw["MetricName"])
            return {
                "Datapoints": []
                if v is None
                else [{"ExtendedStatistics": {kw["ExtendedStatistics"][0]: v}}]
            }
        v = averages.get(kw["MetricName"])
        return {"Datapoints": [] if v is None else [{"Average": v}]}

    cw.get_metric_statistics.side_effect = get_metric_statistics
    return cw


class TestMetrics:
    def test_average_and_percentile_helpers(self):
        cw = fake_cloudwatch({"ErrorRate": 0.1}, {"Latency": 250})
        now = datetime.now(UTC)
        assert get_metric_average(cw, "svc", "ErrorRate", now - timedelta(minutes=5), now) == 0.1
        assert (
            get_metric_percentile(cw, "svc", "Latency", 95, now - timedelta(minutes=5), now) == 250
        )
        assert get_metric_average(cw, "svc", "Missing", now - timedelta(minutes=5), now) == 0.0

    def test_health_score_reproduces_the_books_arithmetic(self):
        cw = fake_cloudwatch(
            {"ErrorRate": 0.1, "CPUUtilization": 40, "MemoryUtilization": 60}, {"Latency": 300}
        )
        # error 80*0.4 + latency 90*0.3 + resource 40*0.2 = 67.0
        assert calculate_pipeline_health_score(cw, "svc") == 67.0

    def test_the_books_weights_put_a_flawless_200ms_service_at_90(self):
        cw = fake_cloudwatch(
            {"ErrorRate": 0.0, "CPUUtilization": 0, "MemoryUtilization": 0}, {"Latency": 200}
        )
        assert calculate_pipeline_health_score(cw, "svc") == 90.0

    def test_the_latency_component_is_not_capped_so_faster_scores_higher(self):
        cw = fake_cloudwatch(
            {"ErrorRate": 0.0, "CPUUtilization": 0, "MemoryUtilization": 0}, {"Latency": 100}
        )
        assert calculate_pipeline_health_score(cw, "svc") == 93.0

    def test_scores_never_go_below_zero_per_component(self):
        cw = fake_cloudwatch(
            {"ErrorRate": 5.0, "CPUUtilization": 100, "MemoryUtilization": 100}, {"Latency": 9000}
        )
        assert calculate_pipeline_health_score(cw, "svc") == 0.0


class TestDeploymentCorrelation:
    deploy = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)

    def cw_by_window(self, before, after):
        cw = MagicMock()

        def stats(**kw):
            window = "after" if kw["StartTime"] >= self.deploy else "before"
            table = after if window == "after" else before
            if "ExtendedStatistics" in kw:
                return {
                    "Datapoints": [
                        {"ExtendedStatistics": {kw["ExtendedStatistics"][0]: table["Latency"]}}
                    ]
                }
            return {"Datapoints": [{"Average": table["ErrorRate"]}]}

        cw.get_metric_statistics.side_effect = stats
        return cw

    def test_flags_a_deploy_that_tripled_errors(self):
        cw = self.cw_by_window(
            {"ErrorRate": 0.02, "Latency": 200}, {"ErrorRate": 0.06, "Latency": 210}
        )
        out = correlate_deployment_to_metrics("svc", self.deploy, cw)
        assert out["correlated"] and out["error_impact"] == pytest.approx(3.0)

    def test_flags_a_deploy_that_slowed_things_down(self):
        cw = self.cw_by_window(
            {"ErrorRate": 0.02, "Latency": 200}, {"ErrorRate": 0.02, "Latency": 400}
        )
        assert correlate_deployment_to_metrics("svc", self.deploy, cw)["correlated"]

    def test_a_quiet_deploy_is_not_correlated(self):
        cw = self.cw_by_window(
            {"ErrorRate": 0.02, "Latency": 200}, {"ErrorRate": 0.021, "Latency": 205}
        )
        assert not correlate_deployment_to_metrics("svc", self.deploy, cw)["correlated"]


class TestLastLogLines:
    """Found on real CloudWatch: the printed ERROR/FATAL pattern matched none of 27 ordinary lines."""

    def _group(self, lines):
        import time

        import boto3
        from moto import mock_aws

        ctx = mock_aws()
        ctx.start()
        logs = boto3.client("logs", region_name="us-east-1")
        logs.create_log_group(logGroupName="/aws/ecs/svc")
        logs.create_log_stream(logGroupName="/aws/ecs/svc", logStreamName="s")
        now = time.time()
        logs.put_log_events(
            logGroupName="/aws/ecs/svc",
            logStreamName="s",
            logEvents=[
                {"timestamp": int((now - 100 + i) * 1000), "message": m}
                for i, m in enumerate(lines)
            ],
        )
        return ctx, logs

    def test_it_returns_the_newest_twenty_lines_of_every_level_in_order(self):
        from datetime import UTC, datetime

        from healer.ingest.logs import last_log_lines

        lines = [f"2026-10-09T20:00:{i:02d}Z INFO request {i} ok" for i in range(30)]
        lines[-1] = "2026-10-09T20:00:29Z ERROR request failed for user=1"
        ctx, logs = self._group(lines)
        try:
            got = last_log_lines(logs, "svc", datetime.now(UTC))
        finally:
            ctx.stop()
        assert len(got) == 20 and got[-1].endswith("ERROR request failed for user=1")
        assert got[0] == lines[10] and "INFO" in got[1]  # the lines that led up to the error

    def test_a_missing_log_group_is_an_error_the_fetcher_turns_into_no_lines(self):
        from datetime import UTC, datetime
        from unittest.mock import MagicMock

        from healer.ingest.enrich import make_log_fetcher

        client = MagicMock()
        client.filter_log_events.side_effect = RuntimeError("ResourceNotFoundException")
        incident = {"triggeredAt": datetime.now(UTC).isoformat(), "affectedService": "ghost"}
        assert make_log_fetcher(client)(incident) == ""  # INGEST continues with less evidence
