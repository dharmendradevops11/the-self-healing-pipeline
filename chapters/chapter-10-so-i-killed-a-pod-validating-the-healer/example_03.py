from dataclasses import dataclass

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
    traffic_share: dict[str, float],         # service -> % of total user traffic
    max_allowed_pct: float = 5.0,
) -> BlastRadiusResult:
    directly_affected = dependency_graph.get(target_service, [])

    transitively_affected = set()
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
        if blocked else
        f"Cleared: predicted {estimated_pct:.1f}% traffic impact within ceiling."
    )

    return BlastRadiusResult(
        directly_affected=directly_affected,
        transitively_affected=sorted(transitively_affected),
        estimated_traffic_pct=round(estimated_pct, 2),
        blocked=blocked,
        reason=reason,
    )
