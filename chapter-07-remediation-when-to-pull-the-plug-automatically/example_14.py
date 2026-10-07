def check_circuit_breaker(service_name):
    recent_attempts = get_remediation_history(service_name, window_minutes=10)
    consecutive_failures = count_consecutive_failures(recent_attempts)

    if consecutive_failures >= 3:
        open_circuit(service_name)
        escalate_to_human(
            service_name,
            reason=f"{consecutive_failures} consecutive remediation failures"
        )
        return False
    return True
