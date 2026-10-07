import anthropic
import json

client = anthropic.Anthropic()

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

def propose_scenarios(incidents: list[dict], library: list[dict]) -> list[dict]:
    prompt = SCENARIO_PROMPT.format(
        incidents=json.dumps(incidents[-30:], indent=2),  # recent window
        library=json.dumps(library, indent=2),
    )
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.content[0].text)

def update_library(library: list[dict], service: str, fault_type: str,
                   found_new_issue: bool) -> list[dict]:
    for entry in library:
        if entry["service"] == service and entry["fault_type"] == fault_type:
            entry["times_run"] += 1
            # exponential decay toward 0 if boring, toward 1 if novel
            target = 1.0 if found_new_issue else 0.0
            entry["novelty_score"] = round(
                entry["novelty_score"] * 0.7 + target * 0.3, 2
            )
            break
    else:
        library.append({
            "service": service, "fault_type": fault_type,
            "novelty_score": 1.0 if found_new_issue else 0.3,
            "times_run": 1,
        })
    return library
