import time
from collections import deque

class RemediationCircuitBreaker:
    """Prevent remediation storms."""

    def __init__(self, max_attempts=3, window=300, cooldown=600):
        self.max_attempts = max_attempts      # 3 tries
        self.window = window                  # within 5 minutes
        self.cooldown = cooldown              # then wait 10 minutes
        self.attempts = deque()

    def can_attempt(self, action_id):
        """Check if remediation is allowed."""
        now = time.time()

        # Clear old attempts outside window
        while self.attempts and self.attempts[0] < now - self.window:
            self.attempts.popleft()

        # Too many recent attempts?
        if len(self.attempts) >= self.max_attempts:
            last_attempt = self.attempts[-1]
            if now - last_attempt < self.cooldown:
                return False, f"Circuit open. Cooldown until {last_attempt + self.cooldown}"

        return True, None

    def record_attempt(self):
        """Track this remediation attempt."""
        self.attempts.append(time.time())
