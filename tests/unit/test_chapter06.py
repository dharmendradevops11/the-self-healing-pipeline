"""Chapter 6: the slow-motion outage."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from healer.library.deploy_risk import calculate_deployment_risk
from healer.library.flakiness import calculate_flakiness_scores
from healer.library.forecasting import (
    ForecastEngine,
    check_redis_memory,
    predict_redis_exhaustion,
    predict_resource_exhaustion,
    predict_with_seasonality,
)

DAY = 86400


class TestReactiveVersusPredictive:
    def test_the_reactive_check_fires_only_once_you_are_in_trouble(self):
        alert = MagicMock()
        assert check_redis_memory(87, alert) is True
        assert alert.call_args.kwargs["severity"] == "critical"
        alert.reset_mock()
        assert check_redis_memory(68, alert) is False
        alert.assert_not_called()

    def history(self, start_pct, per_day, days=7):
        return [(i * DAY, start_pct + per_day * i) for i in range(days)]

    def test_the_forecast_warns_days_ahead_while_memory_is_still_68_percent(self):
        alert = MagicMock()
        # 62% rising 3 points a day: 68% on day 2, 95% around day 11 - outside the 7-day alert window
        data = self.history(62, 3, days=3)
        data += [(i * DAY, 62 + 3 * i) for i in range(3, 7)]
        assert predict_redis_exhaustion(data, alert) is not None

    def test_it_alerts_when_exhaustion_is_inside_a_week(self):
        alert = MagicMock()
        days_left = predict_redis_exhaustion(
            self.history(60, 5), alert
        )  # 90% by day 6, 95% by day 7
        assert days_left == 1
        kw = alert.call_args.kwargs
        assert (
            kw["severity"] == "warning"
            and "95%" in kw["message"]
            and kw["trend"] == pytest.approx(5)
        )

    def test_it_returns_the_answer_without_alerting_when_exhaustion_is_further_out(self):
        alert = MagicMock()
        days_left = predict_redis_exhaustion(self.history(40, 2), alert)
        assert days_left is not None and days_left >= 7
        alert.assert_not_called()

    def test_a_flat_or_falling_trend_is_safe(self):
        assert predict_redis_exhaustion(self.history(50, 0)) is None
        assert predict_redis_exhaustion(self.history(70, -1)) is None

    def test_it_needs_a_week_of_data(self):
        assert predict_redis_exhaustion(self.history(60, 5, days=6)) is None


class TestArima:
    def series(self, slope, n=200, start=40.0):
        rng = np.random.default_rng(0)
        index = pd.date_range("2026-10-09", periods=n, freq="5min")
        return pd.Series(start + slope * np.arange(n) + rng.normal(0, 0.05, n), index=index)

    def test_a_rising_disk_is_predicted_to_cross_the_threshold(self):
        s = self.series(0.2)  # ends near 80 and climbs about 0.2 per step
        out = predict_resource_exhaustion(s, threshold=81, hours_ahead=1)
        assert out["will_exhaust"] is True
        assert 0 <= out["minutes_until"] <= 60 and out["minutes_until"] % 5 == 0
        assert out["predicted_value"] >= 81 and out["current_value"] == s.iloc[-1]

    def test_a_threshold_beyond_the_horizon_is_not_crossed(self):
        assert predict_resource_exhaustion(self.series(0.2), threshold=95)["will_exhaust"] is False

    def test_a_flat_series_is_not(self):
        out = predict_resource_exhaustion(self.series(0.0), threshold=90)
        assert out["will_exhaust"] is False and len(out["forecast"]) == 12

    def test_the_horizon_controls_how_far_ahead_it_looks(self):
        s = self.series(0.05)  # ends near 50, +0.05 per step
        assert not predict_resource_exhaustion(s, 51, hours_ahead=1)["will_exhaust"]
        assert predict_resource_exhaustion(s, 51, hours_ahead=3)["will_exhaust"]


class TestProphet:
    def test_seasonal_forecast_completes_the_printed_fragment(self):
        pytest.importorskip("prophet")
        index = pd.date_range("2026-09-01", periods=24 * 12 * 14, freq="5min")
        s = pd.Series(50 + 0.002 * np.arange(len(index)), index=index)
        out = predict_with_seasonality(s, threshold=1000, hours_ahead=1)
        assert out["will_exhaust"] is False

    def test_the_engine_forecasts_only_the_future(self):
        history = pd.Series(
            np.arange(30.0), index=pd.date_range("2026-09-01", periods=30, freq="D")
        )
        prophet = MagicMock()
        prophet.make_future_dataframe.return_value = "future-frame"
        prophet.predict.return_value = pd.DataFrame(
            {"ds": pd.date_range("2026-09-25", periods=10, freq="D"), "yhat": range(10)}
        )
        metrics = MagicMock()
        metrics.get_metric_history.return_value = history
        engine = ForecastEngine(metrics, prophet_factory=lambda: prophet)
        out = engine.forecast_resource("DiskUsed", "AWS/EC2", days_ahead=14)
        metrics.get_metric_history.assert_called_once_with("DiskUsed", "AWS/EC2", days=30)
        prophet.make_future_dataframe.assert_called_once_with(periods=14, freq="D")
        assert (out["ds"] > history.index.max()).all() and len(out) == 4
        assert engine.alert_threshold_days == 7


class TestFlakiness:
    def runs(self, name, outcomes):
        return [{"test_name": name, "timestamp": i, "passed": ok} for i, ok in enumerate(outcomes)]

    def test_a_coin_flip_test_is_maximally_flaky_and_steady_tests_are_not(self):
        data = (
            self.runs("coin", [True, False] * 10)
            + self.runs("solid", [True] * 20)
            + self.runs("broken", [False] * 20)
        )
        scores = calculate_flakiness_scores(data)
        assert scores["coin"]["flakiness_score"] == pytest.approx(1.0)
        assert (
            scores["solid"]["flakiness_score"] == 0.0 and scores["broken"]["flakiness_score"] == 0.0
        )
        assert scores["coin"]["pass_rate"] == 0.5 and scores["coin"]["sample_size"] == 20

    def test_mostly_passing_is_mildly_flaky(self):
        scores = calculate_flakiness_scores(self.runs("t", [True] * 18 + [False] * 2))
        assert scores["t"]["flakiness_score"] == pytest.approx(0.2)

    def test_too_few_runs_are_skipped_and_only_the_recent_window_counts(self):
        assert calculate_flakiness_scores(self.runs("few", [True, False] * 4)) == {}
        recent = calculate_flakiness_scores(
            self.runs("t", [False] * 100 + [True] * 50), window_size=50
        )
        assert recent["t"]["pass_rate"] == 1.0 and recent["t"]["sample_size"] == 50


class TestDeploymentRisk:
    base = datetime(2026, 10, 7, 11, 0)  # a Wednesday morning

    def meta(self, when=None, adds=10, dels=5, files=3, since=timedelta(hours=24), count=2):
        when = when or self.base
        return {
            "timestamp": when,
            "diff_stats": {"additions": adds, "deletions": dels},
            "files_modified": ["f"] * files,
            "last_success": when - since,
            "cluster_deploy_count_24h": count,
        }

    def test_a_calm_midweek_deploy_scores_zero(self):
        assert calculate_deployment_risk(self.meta()) == 0

    @pytest.mark.parametrize(
        ("when", "points"),
        [
            (datetime(2026, 10, 9, 16, 0), 25),  # Friday afternoon
            (datetime(2026, 10, 10, 11, 0), 35),  # Saturday
            (datetime(2026, 10, 7, 3, 0), 15),  # off-hours
        ],
    )
    def test_time_based_risk(self, when, points):
        assert calculate_deployment_risk(self.meta(when=when)) == points

    def test_change_size_file_count_staleness_and_density_add_up(self):
        assert calculate_deployment_risk(self.meta(adds=1500, dels=600)) == 20
        assert calculate_deployment_risk(self.meta(adds=400, dels=200)) == 10
        assert calculate_deployment_risk(self.meta(files=60)) == 15
        assert calculate_deployment_risk(self.meta(files=25)) == 8
        assert calculate_deployment_risk(self.meta(since=timedelta(hours=100))) == 20
        assert calculate_deployment_risk(self.meta(since=timedelta(minutes=30))) == 10
        assert calculate_deployment_risk(self.meta(count=11)) == 15

    def test_the_score_is_capped_at_100(self):
        worst = self.meta(
            when=datetime(2026, 10, 10, 2, 0),
            adds=3000,
            files=80,
            since=timedelta(hours=200),
            count=20,
        )
        assert calculate_deployment_risk(worst) == 100
