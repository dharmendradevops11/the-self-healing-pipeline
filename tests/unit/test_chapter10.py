"""Chapter 10: validating the healer with chaos."""

import json

import pytest

from healer.library.chaos import (
    generate_hypotheses,
    predict_blast_radius,
    propose_scenarios,
    update_library,
)
from healer.llm import ReplayProvider

INCIDENTS = (
    [{"root_cause_category": "downstream_timeout", "service": "checkout"}] * 3
    + [{"root_cause_category": "resource_exhaustion", "service": "search"}] * 2
    + [{"root_cause_category": "bad_config", "service": "auth"}]
)


class TestHypotheses:
    def test_history_decides_which_experiments_come_first(self):
        top = generate_hypotheses(INCIDENTS, top_n=2)
        assert [h.target_service for h in top] == ["checkout", "search"]
        assert top[0].confidence == 0.5 and "fallback path" in top[0].hypothesis
        assert "OOM" in top[1].hypothesis

    def test_an_unknown_category_gets_the_generic_hypothesis(self):
        last = generate_hypotheses(INCIDENTS)[-1]
        assert last.fault_type == "bad_config" and "degrades gracefully" in last.hypothesis

    def test_it_also_reads_a_json_file(self, tmp_path):
        path = tmp_path / "incidents.json"
        path.write_text(json.dumps(INCIDENTS))
        assert len(generate_hypotheses(str(path))) == 3


class TestScenarios:
    def test_the_model_proposals_come_back_as_data(self):
        reply = json.dumps([{"target_service": "cart", "fault_type": "latency"}])
        llm = ReplayProvider([("chaos engineering", reply)])
        assert propose_scenarios(llm, [{"id": 1}], [])[0]["target_service"] == "cart"

    def test_a_fenced_reply_is_accepted_and_a_non_array_is_refused(self):
        fenced = ReplayProvider([("chaos", '```json\n[{"a": 1}]\n```')])
        assert propose_scenarios(fenced, [], []) == [{"a": 1}]
        with pytest.raises(ValueError):
            propose_scenarios(ReplayProvider([("chaos", '{"a": 1}')]), [], [])

    def test_the_library_forgets_boring_experiments_and_keeps_novel_ones(self):
        library: list[dict] = []
        update_library(library, "cart", "latency", found_new_issue=True)
        assert library[0]["novelty_score"] == 1.0
        update_library(library, "cart", "latency", found_new_issue=False)
        assert library[0] == {
            "service": "cart",
            "fault_type": "latency",
            "novelty_score": 0.7,
            "times_run": 2,
        }
        update_library(library, "cart", "latency", found_new_issue=False)
        assert library[0]["novelty_score"] == 0.49


class TestBlastRadiusBeforeInjection:
    GRAPH = {"db": ["api"], "api": ["web", "mobile"], "web": [], "mobile": []}
    TRAFFIC = {"api": 2.0, "web": 3.0, "mobile": 1.5}

    def test_it_walks_callers_transitively_and_blocks_when_too_much_is_exposed(self):
        r = predict_blast_radius("db", self.GRAPH, self.TRAFFIC, max_allowed_pct=5.0)
        assert r.directly_affected == ["api"]
        assert r.transitively_affected == ["api", "mobile", "web"]
        assert r.estimated_traffic_pct == 6.5 and r.blocked and r.reason.startswith("Blocked")

    def test_a_leaf_service_is_cleared(self):
        r = predict_blast_radius("web", self.GRAPH, self.TRAFFIC)
        assert not r.blocked and r.estimated_traffic_pct == 0 and r.reason.startswith("Cleared")

    def test_a_dependency_cycle_terminates(self):
        graph = {"a": ["b"], "b": ["a"]}
        assert predict_blast_radius("a", graph, {"a": 1, "b": 1}).transitively_affected == [
            "a",
            "b",
        ]


def test_the_fis_experiment_template_has_stop_conditions_and_bounded_selection():
    from pathlib import Path

    template = json.loads(
        (Path(__file__).parents[2] / "infra/policies/fis-ecs-stop-task.json").read_text()
    )
    assert template["stopConditions"], "an experiment without a stop condition cannot be aborted"
    assert template["targets"]["checkout-tasks"]["selectionMode"] == "PERCENT(25)"
