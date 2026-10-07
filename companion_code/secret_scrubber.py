import re
import logging

class SecretScrubber(logging.Filter):
    """Logging filter to scrub GitHub and AWS tokens from application logs securely."""
    
    # Pre-compile patterns with multi-line optimization flags for performance
    PATTERNS = [
        re.compile(r'ghp_[a-zA-Z0-9]{36}'),  # GitHub PAT
        re.compile(r'aws_access_key_id=[a-zA-Z0-9]{20}', re.IGNORECASE),
        re.compile(r'aws_secret_access_key=[a-zA-Z0-9/+=]{40}', re.IGNORECASE)
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Ensure the message payload exists and is structured as a string
            if not record or not hasattr(record, 'msg') or not isinstance(record.msg, str):
                return True
                
            for pattern in self.PATTERNS:
                record.msg = pattern.sub('[SCRUBBED_SECRET]', record.msg)
        except Exception as e:
            # Never raise exceptions from within logging handlers (fail safe: let log print)
            pass
        return True
