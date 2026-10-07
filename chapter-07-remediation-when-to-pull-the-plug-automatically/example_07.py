async def remediate_with_confirmation(action, timeout=60):
    """Execute after human confirmation. Block and escalate on timeout."""

    notification = await slack.send(
        channel="#incidents",
        text=f":rotating_light: Planning to {action.description}",
        blocks=[
            action_block(action),
            button_block("STOP", style="danger"),
            button_block("PROCEED NOW", style="primary")
        ]
    )

    response = await wait_for_interaction(notification, timeout)

    if response == "STOP":
        logger.info(f"Remediation blocked by reviewer: {action.id}")
        return RemediationResult.BLOCKED

    if response == "PROCEED NOW":
        return await execute_remediation(action)

    # Silence means NO execution. Escalate.
    logger.warning(f"Timeout ({timeout}s) reached without response for action {action.id}. Escalating.")
    await trigger_secondary_escalation(action)
    return RemediationResult.BLOCKED
