"""Chapter 10: validating the healer with chaos.

Hypotheses from incident history, scenarios proposed by a model from your postmortems, a library
that learns which experiments still find something, and a blast-radius check that runs before any
fault is injected. The printed listing creates its own Anthropic client; here the model is the
same `LLMProvider` the rest of the pipeline uses, so it runs offline with a replay model.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from healer.llm.base import LLMProvider


@dataclass
class ChaosHypothesis:
    target_service: str
    fault_type: str
    hypothesis: str
    pass_criterion: str
    confidence: float  # how strongly incident history supports this scenario


def generate_hypotheses(
    incidents: list[dict[str, Any]] | str, top_n: int = 5
) -> list[ChaosHypothesis]:
    """`incidents` is the list itself, or the path to a JSON file holding it (as printed)."""
    records: list[dict[str, Any]]
    if isinstance(incidents, str):
        with open(incidents) as f:
            records = json.load(f)
    else:
        records = incidents
    # Cluster by (root_cause_category, implicated_service)
    pattern_counts = Counter((inc["root_cause_category"], inc["service"]) for inc in records)
    total = sum(pattern_counts.values())

    hypotheses = []
    for (category, service), count in pattern_counts.most_common(top_n):
        confidence = round(count / total, 2)
        if category == "downstream_timeout":
            hypothesis = (
                f"{service} will fail over to its fallback path within its "
                f"configured timeout when its primary dependency stalls."
            )
            pass_criterion = "p99 latency stays under SLO; no cascading 5xx to callers."
        elif category == "resource_exhaustion":
            hypothesis = (
                f"{service} will shed load or autoscale before memory exhaustion "
                f"causes an OOM kill."
            )
            pass_criterion = "No OOMKilled events; autoscaler adds capacity within 90s."
        else:
            hypothesis = f"{service} degrades gracefully under a {category} fault."
            pass_criterion = "Error budget consumption stays under 2% during the experiment."

        hypotheses.append(
            ChaosHypothesis(
                target_service=service,
                fault_type=category,
                hypothesis=hypothesis,
                pass_criterion=pass_criterion,
                confidence=confidence,
            )
        )
    return hypotheses


SCENARIO_PROMPT = """You are analyzing incident postmortems to propose chaos engineering
experiments. Given the incident summaries and the current experiment library with past
"novelty scores" (higher = found something new), propose 3 chaos experiments that are
likely to reveal *unknown* weaknesses, not confirm known ones.

For each proposal return: target_service, fault_type, hypothesis, pass_criterion,
and a one-line rationale citing which incident(s) motivated it.

Incidents:
{incidents}

Experiment library (service, fault_type, novelty_score, times_run):
{library}

Respond as a JSON array only.
"""


def propose_scenarios(
    llm: LLMProvider, incidents: list[dict[str, Any]], library: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prompt = SCENARIO_PROMPT.format(
        incidents=json.dumps(incidents[-30:], indent=2),  # recent window
        library=json.dumps(library, indent=2),
    )
    text = llm.invoke(prompt, max_tokens=2000).strip()
    if text.startswith("```"):  # tolerate a fenced reply, as the rest of the pipeline does
        text = text.strip("`").removeprefix("json").strip()
    proposals = json.loads(text)
    if not isinstance(proposals, list):
        raise ValueError("the model must answer with a JSON array of proposals")
    return proposals


def update_library(
    library: list[dict[str, Any]], service: str, fault_type: str, found_new_issue: bool
) -> list[dict[str, Any]]:
    for entry in library:
        if entry["service"] == service and entry["fault_type"] == fault_type:
            entry["times_run"] += 1
            # exponential decay toward 0 if boring, toward 1 if novel
            target = 1.0 if found_new_issue else 0.0
            entry["novelty_score"] = round(entry["novelty_score"] * 0.7 + target * 0.3, 2)
            break
    else:
        library.append(
            {
                "service": service,
                "fault_type": fault_type,
                "novelty_score": 1.0 if found_new_issue else 0.3,
                "times_run": 1,
            }
        )
    return library


@dataclass
class BlastRadiusResult:
    directly_affected: list[str]
    transitively_affected: list[str]
    estimated_traffic_pct: float
    blocked: bool
    reason: str


def predict_blast_radius(
    target_service: str,
    dependency_graph: dict[str, list[str]],  # service -> [services that call it]
    traffic_share: dict[str, float],  # service -> % of total user traffic
    max_allowed_pct: float = 5.0,
) -> BlastRadiusResult:
    """Walk the callers of the target and refuse the experiment if too much traffic is exposed."""
    directly_affected = dependency_graph.get(target_service, [])

    transitively_affected: set[str] = set()
    frontier = list(directly_affected)
    while frontier:
        svc = frontier.pop()
        if svc in transitively_affected:
            continue
        transitively_affected.add(svc)
        frontier.extend(dependency_graph.get(svc, []))

    all_affected = set(directly_affected) | transitively_affected
    estimated_pct = sum(traffic_share.get(s, 0.0) for s in all_affected)

    blocked = estimated_pct > max_allowed_pct
    reason = (
        f"Blocked: predicted {estimated_pct:.1f}% traffic impact exceeds "
        f"{max_allowed_pct}% ceiling."
        if blocked
        else f"Cleared: predicted {estimated_pct:.1f}% traffic impact within ceiling."
    )

    return BlastRadiusResult(
        directly_affected=directly_affected,
        transitively_affected=sorted(transitively_affected),
        estimated_traffic_pct=round(estimated_pct, 2),
        blocked=blocked,
        reason=reason,
    )
