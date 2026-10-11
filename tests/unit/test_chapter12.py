"""Chapter 12: DORA, SLOs for a non-deterministic system, the retrospective."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from healer.library.slo import (
    Investigation,
    compute_slo,
    dora_summary,
    get_deployments,
    get_incidents,
    review_threshold_adjustment,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def stamp(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def reply(payload):
    r = MagicMock()
    r.json.return_value = payload
    return r


class TestDora:
    def test_deployments_are_paged_until_the_window_is_left(self):
        pages = [
            [{"created_at": stamp(1)}, {"created_at": stamp(5)}],
            [{"created_at": stamp(20)}, {"created_at": stamp(40)}],  # 40 days ago: outside
            [{"created_at": stamp(60)}],  # never fetched
        ]
        get = MagicMock(side_effect=[reply(p) for p in pages])
        found = get_deployments(get, "o/r", "t", days=30, now=NOW)
        assert len(found) == 3 and get.call_count == 2

    def test_an_empty_page_ends_the_loop(self):
        assert get_deployments(MagicMock(return_value=reply([])), "o/r", "t", now=NOW) == []

    def test_incidents_follow_pagerduty_offsets(self):
        first = reply({"incidents": [{"id": 1}], "more": True})
        second = reply({"incidents": [{"id": 2}], "more": False})
        get = MagicMock(side_effect=[first, second])
        assert [i["id"] for i in get_incidents(get, "t", ["P1"], now=NOW)] == [1, 2]
        assert get.call_args_list[1].kwargs["params"]["offset"] == 100

    def test_the_summary_is_frequency_and_mean_time_to_recover(self):
        incidents = [
            {"created_at": "2026-10-01T00:00:00Z", "last_status_change_at": "2026-10-01T00:30:00Z"},
            {"created_at": "2026-10-02T00:00:00Z", "last_status_change_at": "2026-10-02T01:00:00Z"},
        ]
        summary = dora_summary([{}] * 60, incidents, days=30)
        assert summary["deployment_frequency_per_day"] == 2.0
        assert summary["mttr_minutes"] == 45.0 and summary["incident_count"] == 2
        assert dora_summary([], [])["mttr_minutes"] == 0


class TestSlo:
    def inv(self, outcome, confidence=80, days_ago=1):
        now = NOW.replace(tzinfo=None)
        return Investigation(now - timedelta(days=days_ago), confidence, outcome)

    def test_burn_rate_is_how_fast_the_5_percent_budget_goes(self):
        runs = [self.inv("merged_clean")] * 18 + [self.inv("rejected")] * 2
        slo = compute_slo(runs, now=NOW.replace(tzinfo=None))
        assert slo == {"window_accuracy": 0.9, "sample_size": 20, "burn_rate": 2.0, "alert": False}
        worse = compute_slo(
            [self.inv("merged_edited")] * 8 + [self.inv("rejected")] * 2,
            now=NOW.replace(tzinfo=None),
        )
        assert worse["alert"] and worse["burn_rate"] == 4.0

    def test_low_confidence_fallback_is_not_an_error(self):
        runs = [self.inv("investigation_only", confidence=30)] * 5
        assert compute_slo(runs, now=NOW.replace(tzinfo=None)) is None

    def test_old_runs_leave_the_window(self):
        runs = [self.inv("rejected", days_ago=45)]
        assert compute_slo(runs, now=NOW.replace(tzinfo=None)) is None


class TestRetrospective:
    def test_lowers_only_on_sustained_accuracy_with_enough_samples(self):
        stats = {50: {"accuracy": 0.95, "sample_size": 20}}
        assert review_threshold_adjustment(stats, 60) == (
            55,
            "lower: sustained accuracy at lower confidence",
        )
        thin = {50: {"accuracy": 0.99, "sample_size": 5}}
        assert review_threshold_adjustment(thin, 60)[0] == 60

    def test_raises_when_the_current_bucket_underperforms(self):
        stats = {60: {"accuracy": 0.8, "sample_size": 30}}
        assert review_threshold_adjustment(stats, 60) == (
            70,
            "raise: current threshold underperforming",
        )

    def test_holds_without_evidence(self):
        assert review_threshold_adjustment({}, 60)[0] == 60


class TestConfidenceDistribution:
    def test_the_ledger_becomes_the_retrospectives_input(self):
        from healer.library.slo import bucket_stats_from_ledger, review_threshold_adjustment

        rows = (
            [{"confidence_score": 52, "human_verdict": "approved"}] * 16
            + [{"confidence_score": 63, "human_verdict": "approved"}] * 2
            + [{"confidence_score": 63, "human_verdict": "rejected"}] * 2
            + [{"confidence_score": 88, "human_verdict": "modified"}]
            + [{"confidence_score": 90, "human_verdict": "pending"}]  # unresolved: not counted
        )
        stats = bucket_stats_from_ledger(rows)
        assert stats == {
            50: {"accuracy": 1.0, "sample_size": 16},
            60: {"accuracy": 0.5, "sample_size": 4},
            80: {"accuracy": 0.5, "sample_size": 1},
        }
        # sustained accuracy in the 50s: the retrospective suggests lowering 60 to 55 (Ch 13 anecdote)
        assert review_threshold_adjustment(stats, 60)[0] == 55
