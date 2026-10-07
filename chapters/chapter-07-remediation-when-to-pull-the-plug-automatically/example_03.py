import random
import time

def retry_with_backoff(fn, max_attempts=5, base_delay=0.5, max_delay=30):
    for attempt in range(max_attempts):
        try:
            return fn()
        except TransientError as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2 ** attempt))
            jitter = random.uniform(0, delay * 0.3)
            time.sleep(delay + jitter)
    raise RuntimeError("unreachable")
