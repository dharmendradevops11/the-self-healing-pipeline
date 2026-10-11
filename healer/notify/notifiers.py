"""Notify, by escalation tier (Chapter 9).

Informational goes to Slack. A warning goes to Slack plus a ticket and pages in business hours.
Critical pages the on-call, always. Only critical issues should ever wake anyone.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from healer.gate.decision import Decision

TIER_LABEL = {"informational": "INFO", "warning": "WARNING", "critical": "CRITICAL"}


def build_message(
    *,
    decision: Decision,
    service: str,
    title: str,
    root_cause: str,
    confidence: int,
    pr_url: str | None = None,
    escalated: bool = False,
    packet: str | None = None,
    review_flags: list[str] | None = None,
) -> tuple[str, str]:
    """Returns (subject, body)."""
    heading = (
        "Needs a human, no fix attempted"
        if escalated
        else ("Fix ready" if pr_url else "Investigation report")
    )
    subject = f"[{TIER_LABEL[decision.tier]}] [Healer] {service}: {heading} ({confidence}/100)"
    lines = [
        f"Self-Healer: {heading}",
        f"Escalation: {TIER_LABEL[decision.tier]} -> {decision.recipient} via {decision.channel}"
        f" (page: {'no' if decision.page is False else decision.page})",
        f"Routing: {decision.band} confidence x {decision.blast_radius['tier']} blast radius"
        f" -> {decision.fix_action}",
        f"Service: {service}",
        f"Issue: {title}",
        f"Root cause: {root_cause[:300]}",
        f"Confidence: {confidence}/100",
    ]
    lines += [f"Human review required: {flag}" for flag in review_flags or []]
    if pr_url:
        lines.append(f"PR: {pr_url}")
    if escalated and packet:
        lines += ["", packet[:3000]]
    return subject, "\n".join(lines)


class Notifier(Protocol):
    def send(self, subject: str, body: str, decision: Decision) -> None: ...


class ConsoleNotifier:
    """Prints the notification. The default for offline runs."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, subject: str, body: str, decision: Decision) -> None:
        self.sent.append((subject, body))
        print(f"\n--- notification ({decision.channel}) ---\n{subject}\n{body}\n")


class SlackNotifier:
    """Posts to a Slack incoming webhook. Fails soft: a Slack outage must not stop the pipeline."""

    def __init__(self, webhook_url: str | Callable[[], str], session: Any = None):
        """`webhook_url` is the URL, or a function that fetches it when a message is sent.

        A function keeps the secret out of every stage that never notifies (Chapter 11: fetched at
        use, not held). Found on real AWS: reading it when the services were built made every
        Lambda and task need permission for a secret only NOTIFY uses.
        """
        from healer.pr.hosts import UrllibSession  # the Lambda runtime has no `requests`

        self._source = webhook_url
        self._url: str | None = None
        self.session = session or UrllibSession()
        if isinstance(webhook_url, str):
            self._url = self._checked(webhook_url)

    @staticmethod
    def _checked(url: str) -> str:
        if not url.startswith("https://hooks.slack.com/"):
            raise ValueError("not a Slack incoming-webhook URL")
        return url

    @property
    def url(self) -> str:
        if self._url is None:
            assert callable(self._source)
            self._url = self._checked(self._source())
        return self._url

    def send(self, subject: str, body: str, decision: Decision) -> None:
        import json

        try:
            response = self.session.post(self.url, json={"text": f"*{subject}*\n{body}"}, timeout=5)
            response.raise_for_status()
            # Evidence for this hop, like every other one. The webhook URL itself is never logged.
            print(
                json.dumps(
                    {
                        "hop": "notify->slack",
                        "status": response.status_code,
                        "subject": subject[:100],
                    }
                ),
                flush=True,
            )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("Slack delivery failed")


class SNSNotifier:
    """Publishes to an SNS topic with attributes subscribers can filter on (page = always)."""

    def __init__(self, sns_client: Any, topic_arn: str):
        self.sns, self.topic_arn = sns_client, topic_arn

    def send(self, subject: str, body: str, decision: Decision) -> None:
        attributes = {
            "escalationTier": {"DataType": "String", "StringValue": decision.tier},
            "page": {"DataType": "String", "StringValue": str(decision.page)},
            "channel": {"DataType": "String", "StringValue": decision.channel},
            "fixAction": {"DataType": "String", "StringValue": decision.fix_action},
        }
        published = self.sns.publish(
            TopicArn=self.topic_arn,
            Subject=subject[:100],
            Message=body,
            MessageAttributes=attributes,
        )
        # What was sent and where, so a notification can be traced like every other hop.
        import json

        print(
            json.dumps(
                {
                    "hop": "notify->sns",
                    "sns_message_id": published.get("MessageId")
                    if isinstance(published, dict)
                    else None,
                    "topic": self.topic_arn,
                    "subject": subject[:100],
                    "attributes": {k: v["StringValue"] for k, v in attributes.items()},
                    "message": body[:1200],
                }
            ),
            flush=True,
        )


class MultiNotifier:
    def __init__(self, *notifiers: Notifier):
        self.notifiers = notifiers

    def send(self, subject: str, body: str, decision: Decision) -> None:
        for n in self.notifiers:
            n.send(subject, body, decision)
