"""Runbook automation: from document to executable code (Chapter 7)."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any


def extract_service_from_alarm(alarm_name: str, known_services: Iterable[str]) -> str:
    """Pick the service an alarm belongs to, by the longest known service name that prefixes it.

    The book calls this helper without defining it. Alarms are named like
    "checkout-api-high-5xx", so the service is the longest registered name the alarm starts with.
    Returns "" if none matches, which the handler treats as "not in the allowlist".
    """
    matches = [s for s in known_services if alarm_name == s or alarm_name.startswith(f"{s}-")]
    return max(matches, key=len) if matches else ""


class RunbookHandler:
    """A Lambda-style handler that restarts only the services it has been told it may restart."""

    def __init__(
        self,
        ecs: Any,
        safe_services: dict[str, dict[str, Any]],
        log_and_notify: Callable[[str], Any],
        log_remediation_event: Callable[..., Any],
        clock: Callable[[], float] = time.time,
    ):
        self.ecs = ecs
        self.safe_services = safe_services
        self.log_and_notify = log_and_notify
        self.log_remediation_event = log_remediation_event
        self.clock = clock

    def handler(self, event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        alarm_name = event["detail"]["alarmName"]
        service_name = extract_service_from_alarm(alarm_name, self.safe_services)

        if service_name not in self.safe_services:
            self.log_and_notify(f"No automation defined for {service_name}, escalating to human")
            return {"action": "escalated", "reason": "not_in_allowlist"}

        cfg = self.safe_services[service_name]

        self.ecs.update_service(
            cluster=cfg["cluster"],
            service=service_name,
            forceNewDeployment=True,
        )

        self.log_remediation_event(
            service=service_name,
            action="force_new_deployment",
            trigger_alarm=alarm_name,
            timestamp=self.clock(),
        )

        return {"action": "restarted", "service": service_name}
