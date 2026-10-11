"""Tier 2: confirm before execute (Chapter 7).

A human gets a STOP and a PROCEED button. Silence means no execution, and escalation.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from healer.library.remediation.types import RemediationResult

logger = logging.getLogger(__name__)


class ConfirmationChannel(Protocol):
    """Where the question is asked: Slack, a pager, a console prompt."""

    async def ask(self, action: Any) -> Any: ...

    async def wait_for_interaction(self, notification: Any, timeout: float) -> str | None: ...

    async def escalate(self, action: Any) -> None: ...


async def remediate_with_confirmation(
    action: Any, channel: ConfirmationChannel, execute_remediation: Any, timeout: float = 60
) -> Any:
    """Execute after human confirmation. Block and escalate on timeout."""
    notification = await channel.ask(action)
    response = await channel.wait_for_interaction(notification, timeout)

    if response == "STOP":
        logger.info("Remediation blocked by reviewer: %s", action.id)
        return RemediationResult.BLOCKED

    if response == "PROCEED NOW":
        return await execute_remediation(action)

    # Silence means NO execution. Escalate.
    logger.warning(
        "Timeout (%ss) reached without response for action %s. Escalating.", timeout, action.id
    )
    await channel.escalate(action)
    return RemediationResult.BLOCKED
