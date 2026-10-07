from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Investigation:
    timestamp: datetime
    confidence: int
    outcome: str  # "merged_clean" | "merged_edited" | "rejected" | "investigation_only"

def compute_slo(investigations, window_days=30, confidence_floor=60):
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    recent = [i for i in investigations if i.timestamp > cutoff]

    high_conf = [i for i in recent if i.confidence >= confidence_floor]
    if not high_conf:
        return None

    correct = sum(1 for i in high_conf if i.outcome in ("merged_clean", "merged_edited"))
    accuracy = correct / len(high_conf)

    error_budget = 0.05  # target: no more than 5% confidently-wrong fixes
    burn_rate = (1 - accuracy) / error_budget

    return {
        "window_accuracy": round(accuracy, 3),
        "sample_size": len(high_conf),
        "burn_rate": round(burn_rate, 2),
        "alert": burn_rate > 2.0,  # burning budget 2x faster than sustainable
    }
