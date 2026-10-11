import json
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from healer.ledger import (
    AgentAuditLogger,
    RollbackStack,
    apply_ecs_scaling,
    historical_success_rate,
    record_outcome,
    success_rate_from_verdicts,
    update_verdict,
)
from healer.ledger.trust_ledger import create_table


@pytest.fixture
def s3():
    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket="audit")
        yield client


@pytest.fixture
def dynamodb():
    with mock_aws():
        resource = boto3.resource("dynamodb")
        create_table(resource)
        yield resource


class TestAuditLogger:
    def test_writes_numbered_steps_under_the_execution(self, s3):
        log = AgentAuditLogger(s3, "audit", "exec-1")
        k1 = log.log_reasoning_step("investigate", {"prompt": "p"}, {"answer": "a"}, confidence=87)
        k2 = log.log_reasoning_step("fix", "in", "out", tool_calls=[{"tool": "git"}])
        assert k1 == "audit/exec-1/step_001_investigate.json"
        assert k2 == "audit/exec-1/step_002_fix.json"
        record = json.loads(s3.get_object(Bucket="audit", Key=k1)["Body"].read())
        assert record["step_number"] == 1
        assert record["confidence_score"] == 87
        assert record["input"] == {"prompt": "p"}

    def test_a_later_stage_resumes_the_numbering(self, s3):
        AgentAuditLogger(s3, "audit", "exec-1").log_reasoning_step("investigate", "i", "o")
        later = AgentAuditLogger.resume(s3, "audit", "exec-1")
        assert later.log_reasoning_step("fix", "i", "o") == "audit/exec-1/step_002_fix.json"

    def test_executions_do_not_share_a_counter(self, s3):
        AgentAuditLogger(s3, "audit", "exec-1").log_reasoning_step("investigate", "i", "o")
        other = AgentAuditLogger.resume(s3, "audit", "exec-2")
        key = other.log_reasoning_step("investigate", "i", "o")
        assert key == "audit/exec-2/step_001_investigate.json"


class TestTrustLedger:
    def test_records_a_pending_outcome_then_a_verdict(self, dynamodb):
        table = dynamodb.Table("agent-trust-ledger")
        record_outcome(dynamodb, "e1", "null deref", 83, "pending", None, "crash:TypeError")
        item = table.get_item(Key={"execution_id": "e1"})["Item"]
        assert item["human_verdict"] == "pending"
        assert (item["confidence_score"], item["fix_worked"]) == (83, None)
        update_verdict(dynamodb, "e1", "approved", fix_worked=True)
        item = table.get_item(Key={"execution_id": "e1"})["Item"]
        assert (item["human_verdict"], item["fix_worked"]) == ("approved", True)

    def test_update_rejects_unknown_verdicts_and_missing_rows(self, dynamodb):
        with pytest.raises(ValueError):
            update_verdict(dynamodb, "e1", "maybe")
        with pytest.raises(Exception):  # noqa: B017 - conditional check on a missing row
            update_verdict(dynamodb, "missing", "approved")

    def test_history_is_none_until_enough_outcomes(self, dynamodb):
        for i in range(3):
            record_outcome(dynamodb, f"e{i}", "h", 70, "approved", True, "crash:TypeError")
        assert historical_success_rate(dynamodb, "crash:TypeError") is None

    def test_rolling_accuracy_per_category(self, dynamodb):
        verdicts = ["approved", "approved", "modified", "rejected", "rejected", "pending"]
        for i, v in enumerate(verdicts):
            record_outcome(dynamodb, f"e{i}", "h", 70, v, None, "crash:TypeError")
        record_outcome(dynamodb, "other", "h", 70, "rejected", None, "infra:Timeout")
        assert historical_success_rate(dynamodb, "crash:TypeError") == pytest.approx(2.5 / 5)

    def test_a_ledger_outage_removes_the_input_instead_of_failing(self):
        broken = MagicMock()
        broken.Table.return_value.query.side_effect = RuntimeError("ledger down")
        assert historical_success_rate(broken, "crash:TypeError") is None

    def test_verdict_scoring(self):
        assert success_rate_from_verdicts(["approved"] * 5) == 1.0
        assert success_rate_from_verdicts(["rejected"] * 5) == 0.0
        assert success_rate_from_verdicts(["approved", "pending"]) is None


class TestRollbacks:
    def test_unwinds_newest_first_and_survives_a_failing_rollback(self):
        order = []
        stack = RollbackStack()
        stack.register("one", lambda: order.append("one"))
        stack.register("two", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        stack.register("three", lambda: order.append("three"))
        result = stack.rollback_all()
        assert order == ["three", "one"]
        assert result[0] == "three" and "FAILED" in result[1] and result[2] == "one"
        assert len(stack) == 0

    def test_ecs_scaling_registers_a_revision_and_can_roll_back(self):
        ecs = MagicMock()
        ecs.describe_task_definition.return_value = {
            "taskDefinition": {
                "taskDefinitionArn": "arn:old:1",
                "family": "svc",
                "containerDefinitions": [],
            }
        }
        ecs.register_task_definition.return_value = {
            "taskDefinition": {"taskDefinitionArn": "arn:new:2"}
        }
        result = apply_ecs_scaling(ecs, "cluster", "svc", 2048)
        assert ecs.register_task_definition.call_args.kwargs["memory"] == "2048"
        assert ecs.update_service.call_args.kwargs["taskDefinition"] == "arn:new:2"
        result["rollback"]()
        assert ecs.update_service.call_args.kwargs["taskDefinition"] == "arn:old:1"
