import json
from dataclasses import dataclass
from collections import Counter

@dataclass
class ChaosHypothesis:
    target_service: str
    fault_type: str
    hypothesis: str
    pass_criterion: str
    confidence: float  # how strongly incident history supports this scenario

def generate_hypotheses(incident_log_path: str, top_n: int = 5) -> list[ChaosHypothesis]:
    with open(incident_log_path) as f:
        incidents = json.load(f)

    # Cluster by (root_cause_category, implicated_service)
    pattern_counts = Counter(
        (inc["root_cause_category"], inc["service"]) for inc in incidents
    )
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

        hypotheses.append(ChaosHypothesis(
            target_service=service,
            fault_type=category,
            hypothesis=hypothesis,
            pass_criterion=pass_criterion,
            confidence=confidence,
        ))
    return hypotheses
