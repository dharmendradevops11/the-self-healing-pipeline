import re
import logging

class SecretScrubber(logging.Filter):
    """Logging filter to scrub GitHub and AWS tokens from application logs."""
    PATTERNS = [
        re.compile(r'ghp_[a-zA-Z0-9]{36}'),  # GitHub PAT
        re.compile(r'aws_access_key_id=[a-zA-Z0-9]{20}', re.IGNORECASE),
        re.compile(r'aws_secret_access_key=[a-zA-Z0-9/+=]{40}', re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                for pattern in self.PATTERNS:
                    record.msg = pattern.sub('[SCRUBBED_SECRET]', record.msg)
            return True
        except Exception:
            # Fail closed: never emit a record we could not scrub.
            record.msg = '[LOG REDACTED: secret scrubbing failed]'
            record.args = ()
            logging.getLogger('secret_scrubber').error(
                'SecretScrubber failed on a log record; record was redacted'
            )
            return True
