"""Remediation library (Chapter 7): when to pull the plug automatically."""

from healer.library.remediation.circuit_breaker import (
    RemediationCircuitBreaker,
    check_circuit_breaker,
    count_consecutive_failures,
)
from healer.library.remediation.confirm import remediate_with_confirmation
from healer.library.remediation.patterns import (
    remediate_disk_exhaustion,
    remediate_failed_deployment,
    remediate_memory_leak,
    remediate_pool_exhaustion,
    remediate_unresponsive,
)
from healer.library.remediation.policy import RemediationPolicy, load_policies
from healer.library.remediation.retry import retry_with_backoff
from healer.library.remediation.runbook import RunbookHandler, extract_service_from_alarm
from healer.library.remediation.selection import VALID_REMEDIATIONS, choose_remediation
from healer.library.remediation.types import (
    InvalidRemediationError,
    RemediationBlockedError,
    RemediationResult,
    TransientError,
)

__all__ = [
    "VALID_REMEDIATIONS",
    "InvalidRemediationError",
    "RemediationBlockedError",
    "RemediationCircuitBreaker",
    "RemediationPolicy",
    "RemediationResult",
    "RunbookHandler",
    "TransientError",
    "check_circuit_breaker",
    "choose_remediation",
    "count_consecutive_failures",
    "extract_service_from_alarm",
    "load_policies",
    "remediate_disk_exhaustion",
    "remediate_failed_deployment",
    "remediate_memory_leak",
    "remediate_pool_exhaustion",
    "remediate_unresponsive",
    "remediate_with_confirmation",
    "retry_with_backoff",
]
