"""Chapter 7: when to pull the plug automatically."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from healer.guardrails.allowlist import validate_fix_paths
from healer.guardrails.remediation_limiter import check_rate_limit, create_table
from healer.library.remediation import (
    VALID_REMEDIATIONS,
    RemediationBlockedError,
    RemediationCircuitBreaker,
    RemediationResult,
    RunbookHandler,
    TransientError,
    check_circuit_breaker,
    choose_remediation,
    count_consecutive_failures,
    extract_service_from_alarm,
    load_policies,
    remediate_disk_exhaustion,
    remediate_failed_deployment,
    remediate_memory_leak,
    remediate_pool_exhaustion,
    remediate_unresponsive,
    remediate_with_confirmation,
    retry_with_backoff,
)
from healer.library.remediation.patterns import disk_cleanup_commands

# ------------------------------------------------------------------- the allowlist


class TestValidateFixPaths:
    def test_safe_paths_pass(self):
        assert validate_fix_paths(["src/a.py", "server/b.py", "api/c.py"]) is True

    @pytest.mark.parametrize(
        "path",
        [".husky/pre-commit", "infrastructure/x.tf", "src/Dockerfile", "src/a.yml", "src/run.sh"],
    )
    def test_forbidden_paths_are_named(self, path):
        with pytest.raises(RemediationBlockedError, match="forbidden path"):
            validate_fix_paths(["src/ok.py", path])

    def test_paths_outside_the_allowlist_are_blocked(self):
        with pytest.raises(RemediationBlockedError, match="outside allowlist"):
            validate_fix_paths(["docs/readme.md"])


# ----------------------------------------------------------------- selection and retry


class TestChooseRemediation:
    @pytest.mark.parametrize(
        ("sig", "flag", "expected"),
        [
            ("5xx_spike_post_deploy", True, "rollback_feature_flag"),
            ("5xx_spike_post_deploy", False, "rollback_git"),
            ("connection_timeout", False, "retry_with_backoff"),
            ("process_unresponsive", False, "restart"),
            ("oom_killed", False, "restart_with_heap_dump"),
            ("something_new", False, "escalate_to_human"),
        ],
    )
    def test_signatures(self, sig, flag, expected):
        assert choose_remediation(sig, 90, flag) == expected
        assert expected in VALID_REMEDIATIONS

    def test_low_and_invalid_confidence_escalate(self):
        assert choose_remediation("oom_killed", 39) == "escalate_to_human"
        assert choose_remediation("oom_killed", 40) == "restart_with_heap_dump"
        assert choose_remediation("oom_killed", 101) == "escalate_to_human"
        assert choose_remediation("oom_killed", -1) == "escalate_to_human"


class TestRetryWithBackoff:
    def test_returns_on_success_without_sleeping(self):
        sleeps = []
        assert retry_with_backoff(lambda: "ok", sleep=sleeps.append) == "ok"
        assert sleeps == []

    def test_retries_transient_errors_with_exponential_delays(self):
        calls, sleeps = [], []

        def flaky():
            calls.append(1)
            if len(calls) < 4:
                raise TransientError("brief")
            return "done"

        out = retry_with_backoff(
            flaky, base_delay=1, sleep=sleeps.append, jitter_source=lambda lo, hi: 0
        )
        assert out == "done" and sleeps == [1, 2, 4]

    def test_delay_is_capped_and_jitter_is_added(self):
        sleeps, calls = [], []

        def always():
            calls.append(1)
            raise TransientError

        with pytest.raises(TransientError):
            retry_with_backoff(
                always,
                max_attempts=4,
                base_delay=10,
                max_delay=15,
                sleep=sleeps.append,
                jitter_source=lambda lo, hi: hi,
            )
        assert len(calls) == 4 and sleeps == [10 + 3.0, 15 + 4.5, 15 + 4.5]

    def test_other_errors_are_not_retried(self):
        calls = []

        def bug():
            calls.append(1)
            raise KeyError("real bug")

        with pytest.raises(KeyError):
            retry_with_backoff(bug, sleep=lambda s: None)
        assert len(calls) == 1


# -------------------------------------------------------------------- circuit breakers


class TestCircuitBreaker:
    def test_opens_after_three_attempts(self):
        t = [1000.0]
        cb = RemediationCircuitBreaker(clock=lambda: t[0])
        for _ in range(3):
            assert cb.can_attempt("a")[0]
            cb.record_attempt()
        ok, reason = cb.can_attempt("a")
        assert ok is False and "Circuit open" in reason

    def test_as_printed_it_reopens_after_the_window_not_the_cooldown(self):
        # Attempts are forgotten once they are older than the 5-minute window, which is shorter than
        # the 10-minute cooldown, so the cooldown never takes effect: the circuit closes at 300s.
        t = [1000.0]
        cb = RemediationCircuitBreaker(clock=lambda: t[0])
        for _ in range(3):
            cb.record_attempt()
        t[0] += 299
        assert cb.can_attempt()[0] is False
        t[0] += 2
        assert cb.can_attempt() == (True, None)

    def test_a_cooldown_shorter_than_the_window_is_honored(self):
        t = [0.0]
        cb = RemediationCircuitBreaker(window=600, cooldown=100, clock=lambda: t[0])
        for _ in range(3):
            cb.record_attempt()
        t[0] = 50
        assert cb.can_attempt()[0] is False
        t[0] = 150
        assert cb.can_attempt()[0] is True

    def test_attempts_outside_the_window_do_not_count(self):
        t = [0.0]
        cb = RemediationCircuitBreaker(clock=lambda: t[0])
        cb.record_attempt()
        cb.record_attempt()
        t[0] = 400
        cb.record_attempt()
        assert cb.can_attempt()[0] is True

    def test_consecutive_failures_reset_on_success(self):
        history = [{"success": False}, {"success": True}, {"success": False}, {"success": False}]
        assert count_consecutive_failures(history) == 2
        assert count_consecutive_failures([]) == 0

    def test_check_circuit_breaker_opens_and_escalates_after_three_failures(self):
        history = lambda name, window_minutes: [{"success": False}] * 3  # noqa: E731
        opened, escalated = MagicMock(), MagicMock()
        assert check_circuit_breaker("svc", history, opened, escalated) is False
        opened.assert_called_once_with("svc")
        assert "3 consecutive" in escalated.call_args.kwargs["reason"]

    def test_check_circuit_breaker_lets_a_healthy_service_continue(self):
        history = lambda name, window_minutes: [{"success": False}, {"success": True}]  # noqa: E731
        opened = MagicMock()
        assert check_circuit_breaker("svc", history, opened, MagicMock()) is True
        opened.assert_not_called()


# ---------------------------------------------------------------------- the runbook


class TestRunbook:
    safe = {
        "checkout-api": {"cluster": "prod", "min_healthy_pct": 50},
        "auth-service": {"cluster": "prod"},
    }

    def test_extracts_the_longest_matching_service(self):
        known = {"checkout", "checkout-api"}
        assert extract_service_from_alarm("checkout-api-high-5xx", known) == "checkout-api"
        assert extract_service_from_alarm("checkout-latency", known) == "checkout"
        assert extract_service_from_alarm("billing-cpu", known) == ""
        assert extract_service_from_alarm("checkout-apix-cpu", {"checkout-api"}) == ""

    def handler(self):
        ecs, notify, log = MagicMock(), MagicMock(), MagicMock()
        return RunbookHandler(ecs, self.safe, notify, log, clock=lambda: 42.0), ecs, notify, log

    def test_restarts_an_allowed_service_and_records_it(self):
        h, ecs, _, log = self.handler()
        out = h.handler({"detail": {"alarmName": "checkout-api-high-5xx"}})
        assert out == {"action": "restarted", "service": "checkout-api"}
        assert ecs.update_service.call_args.kwargs == {
            "cluster": "prod",
            "service": "checkout-api",
            "forceNewDeployment": True,
        }
        assert (
            log.call_args.kwargs["timestamp"] == 42.0
            and log.call_args.kwargs["action"] == "force_new_deployment"
        )

    def test_escalates_a_service_it_has_no_automation_for(self):
        h, ecs, notify, _ = self.handler()
        out = h.handler({"detail": {"alarmName": "billing-cpu-high"}})
        assert out == {"action": "escalated", "reason": "not_in_allowlist"}
        ecs.update_service.assert_not_called()
        notify.assert_called_once()


# ------------------------------------------------------------- confirm before execute


class FakeChannel:
    def __init__(self, answer):
        self.answer, self.escalated = answer, False

    async def ask(self, action):
        return "n1"

    async def wait_for_interaction(self, notification, timeout):
        return self.answer

    async def escalate(self, action):
        self.escalated = True


class TestConfirmation:
    action = SimpleNamespace(id="a1", description="restart checkout")

    def run(self, answer):
        executed = []

        async def execute(action):
            executed.append(action.id)
            return RemediationResult.SUCCESS

        channel = FakeChannel(answer)
        result = asyncio.run(remediate_with_confirmation(self.action, channel, execute))
        return result, executed, channel

    def test_proceed_executes(self):
        result, executed, channel = self.run("PROCEED NOW")
        assert result is RemediationResult.SUCCESS and executed == ["a1"] and not channel.escalated

    def test_stop_blocks_without_escalating(self):
        result, executed, channel = self.run("STOP")
        assert result is RemediationResult.BLOCKED and executed == [] and not channel.escalated

    def test_silence_means_no_execution_and_an_escalation(self):
        result, executed, channel = self.run(None)
        assert result is RemediationResult.BLOCKED and executed == [] and channel.escalated


# ------------------------------------------------------------------------- patterns


class TestPatterns:
    def test_restart_on_ecs_forces_a_new_deployment(self):
        ecs, ec2, log = MagicMock(), MagicMock(), MagicMock()
        remediate_unresponsive(
            "api",
            "ecs",
            ecs=ecs,
            ec2=ec2,
            service_clusters={"api": "c1"},
            get_instance_id=lambda s: "i-1",
            log_remediation=log,
        )
        assert ecs.update_service.call_args.kwargs["cluster"] == "c1"
        ec2.reboot_instances.assert_not_called()
        log.assert_called_once_with("api", "restart", "ecs")

    def test_restart_on_ec2_reboots_the_instance(self):
        ecs, ec2 = MagicMock(), MagicMock()
        remediate_unresponsive(
            "api",
            "ec2",
            ecs=ecs,
            ec2=ec2,
            service_clusters={},
            get_instance_id=lambda s: "i-9",
            log_remediation=MagicMock(),
        )
        ec2.reboot_instances.assert_called_once_with(InstanceIds=["i-9"])
        ecs.update_service.assert_not_called()

    def test_disk_cleanup_is_skipped_when_the_disk_is_fine(self):
        ssm = MagicMock()
        out = remediate_disk_exhaustion(
            "i-1", ssm=ssm, get_disk_usage=lambda i: 40, log_remediation=MagicMock()
        )
        assert out is RemediationResult.SKIPPED
        ssm.send_command.assert_not_called()

    def test_disk_cleanup_dry_run_only_lists_and_a_real_run_deletes(self):
        dry = disk_cleanup_commands(dry_run=True)
        real = disk_cleanup_commands(dry_run=False)
        assert not any("-delete" in c for c in dry) and "[dry-run]" in dry[2]
        assert real[0].endswith("-delete") and "docker system prune -f" in real[2]
        assert "-not -path '/tmp/systemd*'" in real[1]

    def test_disk_cleanup_defaults_to_a_dry_run(self):
        ssm = MagicMock()
        remediate_disk_exhaustion(
            "i-1", ssm=ssm, get_disk_usage=lambda i: 95, log_remediation=MagicMock()
        )
        commands = ssm.send_command.call_args.kwargs["Parameters"]["commands"]
        assert not any("-delete" in c for c in commands)

    def test_memory_leak_dumps_uploads_then_deletes_the_pod_in_order(self):
        order = []
        mk = lambda name: lambda *a, **k: order.append(name)  # noqa: E731
        path = remediate_memory_leak(
            "api",
            "pod-1",
            kubectl_exec=mk("exec"),
            wait_for_heapsnapshot_file=mk("wait"),
            upload_heap_dump=mk("upload"),
            kubectl_delete_pod=mk("delete"),
            log_remediation=mk("log"),
            clock=lambda: 1234,
        )
        assert order == ["exec", "wait", "upload", "delete", "log"]
        assert path == "s3://heap-dumps/api/pod-1-1234.heapsnapshot"

    def test_failed_deployment_prefers_the_feature_flag(self):
        ecs, toggle = MagicMock(), MagicMock()
        remediate_failed_deployment(
            "api",
            ecs=ecs,
            service_clusters={"api": "c"},
            get_last_known_good_version=lambda s: SimpleNamespace(
                task_def_arn="td:1", version="v1"
            ),
            service_has_feature_flag=lambda s: True,
            toggle_flag=toggle,
            log_remediation=MagicMock(),
        )
        toggle.assert_called_once_with("api", enabled=False)
        ecs.update_service.assert_not_called()

    def test_failed_deployment_without_a_flag_redeploys_the_last_good_version(self):
        ecs, log = MagicMock(), MagicMock()
        remediate_failed_deployment(
            "api",
            ecs=ecs,
            service_clusters={"api": "c"},
            get_last_known_good_version=lambda s: SimpleNamespace(
                task_def_arn="td:1", version="v1"
            ),
            service_has_feature_flag=lambda s: False,
            toggle_flag=MagicMock(),
            log_remediation=log,
        )
        assert ecs.update_service.call_args.kwargs["taskDefinition"] == "td:1"
        log.assert_called_once_with("api", "rollback", "v1")


class FakePool:
    def __init__(self, size=20, ceiling=50, recently=False, healthy=True):
        self.size, self.ceiling, self._recent, self._healthy = (
            size,
            {"api": ceiling},
            recently,
            healthy,
        )
        self.history = []

    def was_resized_in_last_30_minutes(self, s):
        return self._recent

    def get_pool_config(self, s):
        return {"max_connections": self.size}

    def reset_connection_pool(self, s):
        self.history.append("reset")

    def resize_pool(self, s, new_max):
        self.history.append(("resize", new_max))
        self.size = new_max

    def verify_database_health(self, s):
        return self._healthy


class TestPoolExhaustion:
    def test_dry_run_changes_nothing(self):
        pool = FakePool()
        assert remediate_pool_exhaustion("api", pool, MagicMock()) is RemediationResult.SKIPPED
        assert pool.history == []

    def test_a_recent_resize_is_skipped(self):
        pool = FakePool(recently=True)
        assert (
            remediate_pool_exhaustion("api", pool, MagicMock(), dry_run=False)
            is RemediationResult.SKIPPED
        )
        assert pool.history == []

    def test_a_healthy_resize_succeeds_and_is_logged(self):
        pool, log = FakePool(), MagicMock()
        assert (
            remediate_pool_exhaustion("api", pool, log, dry_run=False) is RemediationResult.SUCCESS
        )
        assert pool.history == ["reset", ("resize", 30)]
        log.assert_called_once_with("api", "pool_reset_and_resize", 20)

    def test_an_unhealthy_database_rolls_the_size_back(self):
        pool = FakePool(healthy=False)
        assert (
            remediate_pool_exhaustion("api", pool, MagicMock(), dry_run=False)
            is RemediationResult.FAILED
        )
        assert pool.history == ["reset", ("resize", 30), ("resize", 20)] and pool.size == 20

    def test_at_the_ceiling_it_resets_without_growing(self):
        pool = FakePool(size=50, ceiling=50)
        assert (
            remediate_pool_exhaustion("api", pool, MagicMock(), dry_run=False)
            is RemediationResult.SUCCESS
        )
        assert pool.history == ["reset"]


# ------------------------------------------------------------- the rate limiter


class TestRemediationRateLimit:
    @pytest.fixture
    def ddb(self):
        with mock_aws():
            client = boto3.client("dynamodb")
            create_table(client)
            yield client

    def test_three_then_blocked(self, ddb):
        assert [check_rate_limit(ddb, "checkout-api", now=0) for _ in range(5)] == [
            True,
            True,
            True,
            False,
            False,
        ]

    def test_real_service_names_are_accepted_and_junk_is_rejected(self, ddb):
        assert check_rate_limit(ddb, "cart.v2") and check_rate_limit(ddb, "payment_service")
        for bad in ["", "a b", "x;rm", "a" * 65, None, 5]:
            assert check_rate_limit(ddb, bad) is False

    def test_it_fails_closed_when_dynamodb_errors(self):
        client = MagicMock()
        from botocore.exceptions import ClientError

        client.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError"}}, "UpdateItem"
        )
        assert check_rate_limit(client, "svc") is False


# --------------------------------------------------------------------- policies


POLICY = """
remediations:
  service_restart:
    trigger: {metric: health_check_failures, threshold: 3, window: 5m}
    action: {type: restart, max_attempts: 2, backoff: exponential}
    safety: {blast_radius: single_instance, reversible: true, approval: none}
  db_failover:
    trigger: {metric: replication_lag, threshold: 60, window: 5m}
    action: {type: failover}
    safety: {blast_radius: cluster, reversible: false, approval: required}
"""


class TestPolicies:
    def test_loads_the_books_example(self):
        p = load_policies(POLICY)["service_restart"]
        assert p.action["type"] == "restart" and p.trigger["threshold"] == 3
        assert p.zero_touch_eligible and not p.needs_approval

    def test_a_risky_policy_is_not_zero_touch(self):
        p = load_policies(POLICY)["db_failover"]
        assert p.needs_approval and not p.zero_touch_eligible

    def test_a_policy_without_a_safety_section_is_rejected(self):
        with pytest.raises(ValueError, match="safety"):
            load_policies("remediations:\n  x:\n    trigger: {}\n    action: {}\n")

    def test_empty_documents_are_fine(self):
        assert load_policies("") == {}
