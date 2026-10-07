# Reactive: Alert when memory exceeds threshold
def check_redis_memory(current_memory_pct):
    THRESHOLD = 85
    if current_memory_pct > THRESHOLD:
        send_alert(
            severity="critical",
            message=f"Redis memory at {current_memory_pct}%"
        )
        return True
    return False

# This fires when you're already in trouble
check_redis_memory(87)  # Alert fires, team scrambles
