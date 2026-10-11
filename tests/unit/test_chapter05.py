"""Chapter 5: the alert that cried wolf."""

from unittest.mock import MagicMock

import boto3
import numpy as np
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from healer.ingest.alert_limiter import create_table as create_limiter_table
from healer.ingest.alert_limiter import record_alert
from healer.ledger.alert_feedback import (
    create_table as create_feedback_table,
)
from healer.ledger.alert_feedback import (
    get_false_positive_rate,
    record_alert_feedback,
)
from healer.library.devops_guru import fetch_and_filter_insights
from healer.library.pipeline_anomaly import detect_anomaly, train_pipeline_anomaly_detector
from healer.library.statistics import (
    detect_anomalies_ema,
    detect_anomalies_mad,
    detect_anomalies_zscore,
    exponential_moving_average,
)

DURATIONS = [245, 251, 248, 252, 249, 1820, 247, 250, 246]
LATENCIES = [48, 52, 51, 49, 2100, 50, 53, 2050, 51, 48, 52]


class TestZScore:
    def test_the_chapter_example_as_printed_flags_nothing(self):
        # The book prints "Output: [1820]". Run as printed it returns no anomalies:
        # with 9 points the largest possible |z| is sqrt(8), about 2.83, below the threshold of 3.0.
        flags = detect_anomalies_zscore(DURATIONS)
        assert [d for d, f in zip(DURATIONS, flags, strict=True) if f] == []
        assert max(abs((x - np.mean(DURATIONS)) / np.std(DURATIONS)) for x in DURATIONS) < 3.0

    def test_a_lower_threshold_does_catch_the_slow_deployment(self):
        flags = detect_anomalies_zscore(DURATIONS, threshold=2.0)
        assert [d for d, f in zip(DURATIONS, flags, strict=True) if f] == [1820]

    def test_it_misses_both_timeouts_in_skewed_data(self):
        # Why the chapter calls it the default that fails: the outliers inflate the std they are judged by.
        assert not any(detect_anomalies_zscore(LATENCIES))

    def test_constant_data_has_no_anomalies(self):
        assert detect_anomalies_zscore([5, 5, 5]) == [False, False, False]


class TestMad:
    def test_catches_both_timeouts_in_skewed_data(self):
        flags = detect_anomalies_mad(LATENCIES, threshold=3.0)
        assert [v for v, f in zip(LATENCIES, flags, strict=True) if f] == [2100, 2050]

    def test_zero_mad_falls_back_to_the_mean_deviation(self):
        # median 10, MAD 0 -> scale becomes the mean deviation (98); modified z of 500 is about 3.37
        assert detect_anomalies_mad([10, 10, 10, 10, 500]) == [False] * 5
        assert detect_anomalies_mad([10, 10, 10, 10, 500], threshold=3.0) == [False] * 4 + [True]

    def test_all_identical_values_do_not_divide_by_zero(self):
        assert detect_anomalies_mad([7, 7, 7]) == [False, False, False]


class TestEma:
    def test_follows_a_trend(self):
        ema = exponential_moving_average([10, 10, 10, 20], alpha=0.5)
        assert ema == [10.0, 10.0, 10.0, 15.0]

    def test_alpha_must_be_between_zero_and_one(self):
        for bad in (0, 1, -0.2, 1.5):
            with pytest.raises(ValueError):
                exponential_moving_average([1, 2], alpha=bad)

    def test_empty_and_short_inputs(self):
        assert exponential_moving_average([]) == []
        assert detect_anomalies_ema([1, 2]) == [False, False]

    def test_flags_a_spike_against_the_trend(self):
        values = [10, 11, 10, 12, 11, 10, 95, 11, 10]
        flags = detect_anomalies_ema(values)
        assert flags[6] and not any(flags[:6])


class TestPipelineIsolationForest:
    def history(self, n=300):
        rng = np.random.default_rng(3)
        return [
            {
                "duration": 245 + rng.normal(0, 4),
                "cpu_peak": 67 + rng.normal(0, 2),
                "memory_peak": 2.1 + rng.normal(0, 0.05),
                "test_failures": 0,
                "artifact_size_mb": 128 + rng.normal(0, 1),
            }
            for _ in range(n)
        ]

    def test_a_normal_run_passes_and_a_runaway_run_is_flagged(self):
        model = train_pipeline_anomaly_detector(self.history())
        normal = detect_anomaly(
            model,
            {
                "duration": 246,
                "cpu_peak": 67,
                "memory_peak": 2.1,
                "test_failures": 0,
                "artifact_size_mb": 128,
            },
        )
        odd = detect_anomaly(
            model,
            {
                "duration": 1800,
                "cpu_peak": 99,
                "memory_peak": 7.5,
                "test_failures": 40,
                "artifact_size_mb": 900,
            },
        )
        assert normal[0] is False and odd[0] is True
        assert odd[1] < normal[1]


class TestDevOpsGuruFilter:
    def test_low_severity_is_dropped_unless_it_touches_a_critical_resource(self):
        client = MagicMock()
        client.list_insights.return_value = {
            "ReactiveInsights": [
                {"Id": "a", "Severity": "HIGH", "ResourceCollection": {"x": 1}},
                {"Id": "b", "Severity": "LOW", "ResourceCollection": {"critical": True}},
                {"Id": "c", "Severity": "LOW", "ResourceCollection": {}},
                {"Id": "d", "ResourceCollection": {}},
            ]
        }
        kept = fetch_and_filter_insights(client, lambda rc: bool(rc.get("critical")))
        assert [i["Id"] for i in kept] == ["a", "b"]


class TestAlertLimiter:
    @pytest.fixture
    def table(self):
        with mock_aws():
            yield create_limiter_table(boto3.resource("dynamodb"))

    def test_three_alerts_pass_then_the_flood_is_stopped(self, table):
        assert [record_alert(table, "checkout", "h1") for _ in range(6)] == [
            True,
            True,
            True,
            False,
            False,
            False,
        ]

    def test_windows_and_services_are_independent(self, table):
        for _ in range(3):
            record_alert(table, "checkout", "h1")
        assert record_alert(table, "checkout", "h2") and record_alert(table, "billing", "h1")

    def test_a_custom_limit(self, table):
        assert [record_alert(table, "s", "h", limit=2) for _ in range(3)] == [True, True, False]

    def test_other_errors_are_raised(self):
        t = MagicMock()
        t.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError"}}, "UpdateItem"
        )
        with pytest.raises(ClientError):
            record_alert(t, "s", "h")


class TestAlertFeedback:
    @pytest.fixture
    def ddb(self):
        with mock_aws():
            client = boto3.client("dynamodb")
            create_feedback_table(client)
            yield client

    def test_false_positive_rate_over_a_rolling_window(self, ddb):
        now = 1_800_000_000.0
        for i, fp in enumerate([True, True, False, True]):
            record_alert_feedback(ddb, f"a{i}", "checkout", "timeout", fp, "ana", now=now - 3600)
        record_alert_feedback(ddb, "old", "checkout", "timeout", False, "ana", now=now - 30 * 86400)
        record_alert_feedback(ddb, "other", "checkout", "oom", False, "ana", now=now - 3600)
        assert get_false_positive_rate(
            ddb, "checkout", "timeout", days=7, now=now
        ) == pytest.approx(0.75)
        assert get_false_positive_rate(ddb, "checkout", "oom", days=7, now=now) == 0.0

    def test_no_data_means_zero(self, ddb):
        assert get_false_positive_rate(ddb, "nobody", "none") == 0.0
