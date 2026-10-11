"""The pipeline against LocalStack (`make local-up`, then `make local-test`).

Skipped automatically when LocalStack is not running, so `make test` never needs Docker.
"""

import os
import urllib.request

import pytest

from healer.demo import local_services
from healer.pipeline import run_pipeline

ENDPOINT = os.environ.get("LOCALSTACK_ENDPOINT", "http://localhost:4566")

pytestmark = pytest.mark.integration


def _up() -> bool:
    try:
        urllib.request.urlopen(f"{ENDPOINT}/_localstack/health", timeout=2)
        return True
    except OSError:
        return False


@pytest.fixture(autouse=True)
def _require_localstack(monkeypatch):
    if not _up():
        pytest.skip("LocalStack is not running (make local-up)")
    yield
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)


INCIDENT = {
    "title": "TypeError: Cannot read properties of undefined (reading 'name')",
    "type": "error",
    "affectedService": "profile-service",
    "stackTrace": "TypeError: 'NoneType' object has no attribute 'name'\n"
    '  File "src/app/profile.py", line 6, in display_name',
    "cloudwatchLogs": ["ERROR profile lookup returned None for user 42"],
}


def test_happy_path_opens_a_pull_request_on_localstack():
    import json

    from healer.demo import SCENARIOS

    incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
    with local_services(localstack=ENDPOINT) as (services, handles):
        result = run_pipeline(incident, services)
        assert result.outcome == "pr_opened", result.reason
        audit = services.s3.list_objects_v2(Bucket=services.audit_bucket)["Contents"]
        state = services.s3.list_objects_v2(Bucket=services.state_bucket_name)["Contents"]
        assert any(o["Key"].startswith("audit/") for o in audit)
        assert any(o["Key"].startswith("pipeline-state/") for o in state)


def test_payment_adjacent_service_gets_expedited_review_and_a_page():
    import json

    from healer.demo import SCENARIOS

    incident = json.loads((SCENARIOS / "incidents" / "null-profile.json").read_text())
    registry = json.loads((SCENARIOS / "registry-payments.json").read_text())
    with local_services(localstack=ENDPOINT, registry=registry) as (services, _):
        result = run_pipeline(incident, services)
        assert result.outcome == "pr_opened", result.reason
        assert result.decision.fix_action == "fix_pr_expedited_review"
        assert result.decision.tier == "critical"
