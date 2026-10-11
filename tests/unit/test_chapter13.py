"""Chapter 13: autonomous response policy, decision trail, accountability."""

from datetime import UTC, datetime

import pytest

from healer.library.agents import (
    Action,
    Incident,
    MemoryPressurePolicy,
    Service,
    build_decision_trail,
    map_accountability,
    parse_memory_gib,
)


def good_incident(**overrides):
    base = {
        "service": Service("tier-3"),
        "action": Action(is_reversible=True, blast_radius="single_task"),
        "confidence": 90,
    }
    return Incident(**{**base, **overrides})


class TestPolicy:
    policy = MemoryPressurePolicy()

    def test_every_dimension_must_clear(self):
        assert self.policy.should_auto_remediate(good_incident())

    @pytest.mark.parametrize(
        "change",
        [
            {"service": Service("tier-1")},
            {"service": Service("tier-3", handles_sensitive_data=True)},
            {"action": Action(is_reversible=False, blast_radius="single_task")},
            {"action": Action(is_reversible=True, blast_radius="cluster")},
            {"confidence": 84},
            {"service": Service("tier-3", dependent_services_healthy=False)},
            {"during_change_freeze": True},
            {"remediations_last_24h": 3},
        ],
    )
    def test_any_single_failure_escalates(self, change):
        assert not self.policy.should_auto_remediate(good_incident(**change))

    def test_memory_quantities_are_numbers_not_strings(self):
        assert parse_memory_gib("512Mi") == 0.5 and parse_memory_gib("2Gi") == 2
        assert parse_memory_gib("2048Mi") == 2 and parse_memory_gib("1.5Gi") == 1.5
        with pytest.raises(ValueError):
            parse_memory_gib("lots")

    def test_an_oom_gets_50_percent_more_capped_at_4_gib(self):
        assert self.policy.calculate_resource_increase("2Gi", "OOMKilled") == "3Gi"
        assert self.policy.calculate_resource_increase("3Gi", "OOMKilled") == "4Gi"
        assert self.policy.calculate_resource_increase("2Gi", "latency") == "2Gi"

    def test_success_is_defined_before_acting(self):
        assert self.policy.verification_criteria()["pod_restart_count"]["duration"] == "5m"


class TestDecisionTrail:
    def test_evidence_is_scrubbed_before_it_is_recorded(self):
        token = "ghp_" + "a" * 36
        trail = build_decision_trail(
            {"id": "inc-1", "logs": [f"clone failed with {token}"]},
            analyze_log=lambda line: {"relevance": 0.9, "why_relevant": "auth failure"},
            generate_alternatives=lambda d: [
                {
                    "description": "restart",
                    "risk_score": 1,
                    "effectiveness": 0.4,
                    "rejection_reason": "does not fix the leak",
                },
                {"description": "raise limit", "risk_score": 2, "effectiveness": 0.8},
            ],
            select_best_option=lambda opts: {
                **opts[1],
                "selection_rationale": "fixes cause",
                "confidence": 88,
                "estimated_blast_radius": "low",
            },
            find_precedents=lambda d: ["inc-0"],
            now=datetime(2026, 10, 9, tzinfo=UTC),
        )
        assert token not in str(trail) and "[SCRUBBED_SECRET]" in str(trail)
        assert trail["alternatives_evaluated"][0]["rejected_because"] == "does not fix the leak"
        assert trail["decision_factors"]["similar_past_incidents"] == ["inc-0"]
        assert trail["timestamp"].startswith("2026-10-09")


class TestAccountability:
    def test_a_human_owns_it_even_when_ai_made_the_change(self):
        out = map_accountability(
            {"id": "i1", "service_owner": "payments-team", "approved_by": "dana", "oncall": "ravi"}
        )
        assert out["fix_owner"] == "payments-team" and out["change_approved_by"] == "dana"
        assert out["follow_up_owner"] == "ravi" and "AI" in out["change_authored_by"]

    def test_an_ownerless_record_and_a_self_approval_are_refused(self):
        with pytest.raises(ValueError):
            map_accountability({"id": "i2"})
        with pytest.raises(ValueError):
            map_accountability({"id": "i3", "service_owner": "x", "approved_by": "healer-agent"})
