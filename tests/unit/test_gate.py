import pytest

from healer.gate import (
    ESCALATION_MATRIX,
    SignalEvidence,
    compute_confidence,
    compute_signal_strength,
    confidence_band,
    decide,
    estimate_blast_radius,
    route_escalation,
)


class TestComputeConfidence:
    def test_blends_signal_model_and_history(self):
        assert compute_confidence(1, 1, 1) == 100
        assert compute_confidence(0, 0, 0) == 0
        assert compute_confidence(0.8, 0.9, 0.7) == 82  # 0.24 + 0.405 + 0.175

    def test_sparse_history_moves_half_its_weight_to_the_model(self):
        # weights become signal 0.30, model 0.575, history 0.125, neutral prior 0.5
        assert compute_confidence(0.8, 0.9, None) == 82  # 0.24 + 0.5175 + 0.0625

    def test_a_confident_model_alone_cannot_clear_the_gate(self):
        assert compute_confidence(0.0, 0.95, 0.2) < 60


class TestSignalStrength:
    def test_full_and_empty_evidence(self):
        assert compute_signal_strength(SignalEvidence(20, True, 2, 2, True)) == pytest.approx(1.0)
        assert compute_signal_strength(SignalEvidence(0, False, 0, 0, False)) == 0.0

    def test_credit_is_capped(self):
        capped = SignalEvidence(500, False, 1, 5, False)
        assert compute_signal_strength(capped) == pytest.approx(0.6)


class TestBlastRadius:
    registry = {
        "gateway": {"dependents": ["checkout", "reports"], "estimated_users": 1000},
        "checkout": {"estimated_users": 60_000, "handles_pii_or_payment": True},
        "reports": {"estimated_users": 200},
        "internal": {"estimated_users": 100},
        "mid": {"estimated_users": 6_000},
        "big": {"estimated_users": 60_000},
        "huge": {"estimated_users": 600_000},
    }

    def test_walks_dependents_and_flags_sensitive_data(self):
        r = estimate_blast_radius("gateway", self.registry)
        assert r == {
            "affected_services": 2,
            "estimated_users": 61_200,
            "sensitive_data_at_risk": True,
            "tier": "critical",
        }

    @pytest.mark.parametrize(
        ("service", "tier"),
        [("internal", "low"), ("mid", "medium"), ("big", "high"), ("huge", "critical")],
    )
    def test_user_counts_map_to_tiers(self, service, tier):
        assert estimate_blast_radius(service, self.registry)["tier"] == tier

    def test_survives_cycles_and_unknown_services(self):
        cyclic = {"a": {"dependents": ["b"]}, "b": {"dependents": ["a"]}}
        assert estimate_blast_radius("a", cyclic)["affected_services"] == 1
        assert estimate_blast_radius("nope", {})["affected_services"] == 0


def test_bands_are_low_below_60_medium_to_84_high_from_85():
    assert [confidence_band(c) for c in (59, 60, 84, 85)] == ["low", "medium", "medium", "high"]


class TestEscalationMatrix:
    def test_has_all_twelve_cells(self):
        assert len(ESCALATION_MATRIX) == 12

    @pytest.mark.parametrize(
        ("confidence", "blast", "tier", "action"),
        [
            (90, "low", "informational", "auto_fix_pr"),
            (90, "medium", "informational", "auto_fix_pr"),
            (90, "high", "warning", "fix_pr_expedited_review"),
            (90, "critical", "critical", "fix_pr_expedited_review"),
            (70, "low", "informational", "auto_fix_pr"),
            (70, "medium", "warning", "fix_pr_standard_review"),
            (70, "high", "warning", "fix_pr_expedited_review"),
            (70, "critical", "critical", "investigation_only"),
            (40, "low", "warning", "investigation_only"),
            (40, "medium", "warning", "investigation_only"),
            (40, "high", "critical", "investigation_only"),
            (40, "critical", "critical", "investigation_only"),
        ],
    )
    def test_each_cell(self, confidence, blast, tier, action):
        r = route_escalation(confidence, blast, "owner")
        assert (r["tier"], r["fix_action"]) == (tier, action)

    def test_only_critical_pages_the_oncall(self):
        oncall = lambda owner: f"oncall-of-{owner}"  # noqa: E731
        assert route_escalation(70, "medium", "team", oncall)["recipient"] == "team"
        crit = route_escalation(40, "critical", "team", oncall)
        assert (crit["recipient"], crit["page"], crit["channel"]) == (
            "oncall-of-team",
            "always",
            "pagerduty",
        )

    def test_paging_policy_by_tier(self):
        warn = route_escalation(70, "medium", "o")
        info = route_escalation(90, "low", "o")
        assert (warn["page"], warn["channel"]) == ("business_hours_only", "slack+ticket")
        assert (info["page"], info["channel"]) == (False, "slack")


class TestDecide:
    registry = {
        "checkout-api": {
            "dependents": ["ledger"],
            "estimated_users": 800,
            "owner": "payments",
            "oncall": "payments-oncall",
        },
        "ledger": {"estimated_users": 100, "handles_pii_or_payment": True},
        "internal-tool": {"estimated_users": 50, "owner": "platform"},
    }

    def test_payment_adjacent_service_is_critical_and_pages_the_oncall(self):
        d = decide("checkout-api", 90, self.registry)
        assert d.blast_radius["tier"] == "critical"
        assert (d.tier, d.fix_action, d.recipient) == (
            "critical",
            "fix_pr_expedited_review",
            "payments-oncall",
        )

    def test_contained_high_confidence_fix_is_informational(self):
        d = decide("internal-tool", 90, self.registry)
        assert (d.fix_action, d.tier, d.recipient) == ("auto_fix_pr", "informational", "platform")
        assert d.fix_authorized

    def test_unknown_service_gets_the_default_tier_not_zero_risk(self):
        d = decide("mystery", 70, self.registry, unknown_service_tier="high")
        assert d.blast_radius["tier"] == "high"
        assert d.fix_action == "fix_pr_expedited_review"
        assert d.recipient == "unassigned"

    def test_below_60_is_never_authorized_to_write_code(self):
        assert not decide("internal-tool", 59, self.registry).fix_authorized


class TestPciScope:
    """Chapter 11: a PCI-scoped service is never touched by the agent, at any confidence."""

    REGISTRY = {"pay": {"owner": "p", "estimated_users": 10, "pci_scoped": True}}

    def test_a_tagged_service_gets_a_report_not_a_fix_even_at_high_confidence(self):
        from healer.gate import decide

        d = decide("pay", 99, self.REGISTRY)
        assert d.fix_action == "investigation_only" and not d.fix_authorized

    def test_an_untagged_service_at_the_same_confidence_gets_a_fix(self):
        from healer.gate import decide

        assert decide("pay", 99, {"pay": {"owner": "p", "estimated_users": 10}}).fix_authorized
