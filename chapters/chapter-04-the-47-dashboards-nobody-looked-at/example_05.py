class StructuredLogger:
    def __init__(self, service_name):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)

    def log(self, level, message, **context):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "level": level,
            "message": message,
            "correlation_id": context.get("correlation_id"),
            "trace_id": context.get("trace_id"),
            "user_id": context.get("user_id"),  # Hashed, not raw
            **context
        }
        self.logger.log(getattr(logging, level), json.dumps(log_entry))
