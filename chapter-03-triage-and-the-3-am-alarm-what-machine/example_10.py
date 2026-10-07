class IncidentValidator:
    """Because LLMs lie with confidence."""

    def validate_incident(self, llm_analysis):
        claimed_errors = llm_analysis.get('error_count', 0)
        actual_errors = self.metrics_client.query(
            'sum(rate(errors[5m]))', llm_analysis['time_range']
        )
        if claimed_errors > actual_errors * 2:
            return {'valid': False, 'reason': 'Claimed error count implausible'}

        for service in llm_analysis.get('affected_services', []):
            if not self.service_registry.exists(service):
                return {'valid': False, 'reason': f'Nonexistent service mentioned: {service}'}

        if llm_analysis.get('customer_impact'):
            recent_tickets = self.support_api.get_recent(minutes=30)
            if len(recent_tickets) == 0:
                return {'valid': False, 'reason': 'Claims customer impact but support queue empty'}

        return {'valid': True}
