"""Chapter 17: start local, stay local until you can't."""

import base64
import datetime
import hashlib
import hmac
import json
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from healer.gate import decide
from healer.guardrails.patch_policy import PatchPolicy, glob_to_regex
from healer.guardrails.phases import (
    ActionPlan,
    AutonomyLimits,
    ChangeFacts,
    Phase,
    PhaseController,
    PRThrottle,
    ShadowRecord,
    create_throttle_table,
    merge_rate,
    merge_rate_health,
    record_shadow,
)
from healer.ingest.webhook import MAX_PAYLOAD_BYTES, validate_signature

REGISTRY = {"api": {"estimated_users": 100, "owner": "team", "oncall": "oncall"}}


def authorized():
    return decide("api", 90, REGISTRY)


def unauthorized():
    return decide("api", 40, REGISTRY)


# ------------------------------------------------------------------ the daily PR cap


class TestPRThrottle:
    @pytest.fixture
    def table(self):
        with mock_aws():
            yield create_throttle_table(boto3.resource("dynamodb"))

    DAY = datetime.date(2026, 10, 9)

    def test_three_prs_a_day_then_the_cap_holds(self, table):
        throttle = PRThrottle(table)
        assert [throttle.try_open_pr(self.DAY) for _ in range(5)] == [
            True,
            True,
            True,
            False,
            False,
        ]

    def test_the_cap_resets_the_next_day(self, table):
        throttle = PRThrottle(table)
        for _ in range(3):
            throttle.try_open_pr(self.DAY)
        assert not throttle.try_open_pr(self.DAY)
        assert throttle.try_open_pr(self.DAY + datetime.timedelta(days=1))

    def test_the_cap_survives_a_cold_start(self, table):
        # The bug the chapter describes: an in-memory counter resets on every cold start.
        # A brand new throttle object (a new Lambda container) must still see today's count.
        for _ in range(3):
            PRThrottle(table).try_open_pr(self.DAY)
        assert PRThrottle(table).try_open_pr(self.DAY) is False

    def test_a_custom_cap_and_unrelated_errors(self, table):
        assert [PRThrottle(table, 1).try_open_pr(self.DAY) for _ in range(2)] == [True, False]
        broken = MagicMock()
        broken.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError"}}, "UpdateItem"
        )
        with pytest.raises(ClientError):
            PRThrottle(broken).try_open_pr()


# ------------------------------------------------------------------- the three phases


class TestPhases:
    def throttle(self, allow=True):
        t = MagicMock()
        t.try_open_pr.return_value = allow
        return t

    def test_shadow_mode_acts_on_nothing_and_never_touches_the_cap(self):
        throttle = self.throttle()
        plan = PhaseController(Phase.SHADOW, throttle).plan(authorized())
        assert plan.action == "record_only"
        throttle.try_open_pr.assert_not_called()

    def test_every_phase_escalates_what_the_matrix_does_not_authorize(self):
        for phase in Phase:
            assert PhaseController(phase, self.throttle()).plan(unauthorized()).action == "escalate"

    def test_supervised_opens_a_pr_for_human_review_until_the_cap_is_hit(self):
        assert (
            PhaseController(Phase.SUPERVISED, self.throttle()).plan(authorized()).action
            == "open_pr"
        )
        capped = PhaseController(Phase.SUPERVISED, self.throttle(allow=False)).plan(authorized())
        assert capped.action == "cap_reached"

    def test_autonomous_needs_every_limit_to_hold(self):
        ctl = PhaseController(Phase.AUTONOMOUS, self.throttle())
        good = ChangeFacts(
            files_changed=2, diff_lines=120, tests_passed=True, stable_for_an_hour=True
        )
        assert ctl.plan(authorized(), good) == ActionPlan(
            "open_pr_autonomous", "within the autonomous limits"
        )

    @pytest.mark.parametrize(
        ("facts", "fragment"),
        [
            (ChangeFacts(5, 100, True, True), "5 files"),
            (ChangeFacts(2, 1000, True, True), "1000 lines"),
            (ChangeFacts(2, 100, False, True), "tests"),
            (ChangeFacts(2, 100, True, False), "stable"),
        ],
    )
    def test_breaking_any_autonomy_limit_falls_back_to_a_reviewed_pr(self, facts, fragment):
        plan = PhaseController(Phase.AUTONOMOUS, self.throttle()).plan(authorized(), facts)
        assert plan.action == "open_pr" and fragment in plan.reason

    def test_autonomous_with_no_facts_is_treated_as_unproven(self):
        assert (
            PhaseController(Phase.AUTONOMOUS, self.throttle()).plan(authorized()).action
            == "open_pr"
        )

    def test_limits_are_strictly_below_the_numbers(self):
        limits = AutonomyLimits()
        assert limits.violations(4, 999, True, True) == []
        assert len(limits.violations(5, 1000, False, False)) == 4


class TestShadowRecords:
    def test_a_shadow_decision_is_stored_for_the_postmortem(self):
        with mock_aws():
            s3 = boto3.client("s3")
            s3.create_bucket(Bucket="audit")
            rec = ShadowRecord(
                "inc-1",
                "api",
                "open_pr",
                "profile is None",
                83,
                "low",
                ["src/auth.py"],
                recorded_at="2026-10-09T12:00:00+00:00",
            )
            key = record_shadow(s3, "audit", rec)
            assert key == "shadow/2026-10-09/inc-1.json"
            stored = json.loads(s3.get_object(Bucket="audit", Key=key)["Body"].read())
            assert stored["would_have"] == "open_pr" and stored["proposed_files"] == ["src/auth.py"]


class TestMergeRate:
    def test_merged_and_edited_count_and_pending_does_not(self):
        outcomes = ["merged", "edited_then_merged", "rejected", "pending"]
        assert merge_rate(outcomes) == pytest.approx(2 / 3)
        assert merge_rate([]) is None and merge_rate(["pending"]) is None

    def test_below_thirty_percent_means_something_is_broken(self):
        assert (
            merge_rate_health(["merged"] * 3 + ["rejected"] * 7) == "healthy"
        )  # exactly 30% is not below it
        assert merge_rate_health(["merged"] + ["rejected"] * 3).startswith("broken")  # 25%
        assert merge_rate_health([]) == "no data yet"


# ------------------------------------------------------------------- the YAML allowlist


class TestPatchPolicy:
    policy = PatchPolicy.from_yaml()

    @pytest.mark.parametrize(
        "path",
        [
            "src/auth.py",
            "src/deep/er/x.py",
            "tests/test_a.py",
            "tests/x/y/z.txt",
            "requirements.txt",
        ],
    )
    def test_allowed(self, path):
        assert self.policy.path_allowed(path)

    @pytest.mark.parametrize(
        "path",
        [
            ".env",
            "src/.env.local",
            "config/secrets.yaml",
            "infrastructure/main.tf",
            "infrastructure/a/b.tf",
            "src/database/migrations/001.sql",
            "Dockerfile",
            "src/app.js",
            "README.md",
            "src/../Dockerfile",
            "/etc/passwd",
        ],
    )
    def test_denied_or_not_allowed(self, path):
        assert not self.policy.path_allowed(path)

    def test_denied_beats_allowed(self):
        policy = PatchPolicy.from_yaml(
            "file_patterns:\n  allowed: ['**/*']\n  denied: ['**/secret*']\n"
        )
        assert policy.path_allowed("a/b.py") and not policy.path_allowed("a/secrets.py")

    def test_a_small_tested_patch_passes(self):
        assert self.policy.check_patch(
            {"src/a.py": 40, "tests/test_a.py": 30}, includes_tests=True
        ).ok

    def test_every_problem_is_reported(self):
        files = {f"src/f{i}.py": 600 for i in range(6)} | {"infrastructure/x.tf": 1}
        result = self.policy.check_patch(files, includes_tests=False)
        text = " | ".join(result.problems)
        assert not result.ok
        assert (
            "infrastructure/x.tf" in text
            and "7 files" in text
            and "600 lines" in text
            and "tests" in text
        )

    def test_tests_can_be_made_optional(self):
        policy = PatchPolicy.from_yaml(
            "file_patterns: {allowed: ['src/**/*.py']}\nvalidation: {require_tests: false}\n"
        )
        assert policy.check_patch({"src/a.py": 1}, includes_tests=False).ok

    def test_glob_semantics(self):
        assert glob_to_regex("src/**/*.py").match("src/a/b/c.py") and glob_to_regex(
            "src/**/*.py"
        ).match("src/c.py")
        assert not glob_to_regex("src/*.py").match("src/a/c.py")
        assert glob_to_regex("**/.env*").match(".env") and glob_to_regex("**/.env*").match(
            "a/b/.env.prod"
        )
        assert not glob_to_regex("a?c").match("a/c")


# ----------------------------------------------------------- the GitHub webhook listing


class TestGitHubSignature:
    secret = b"s3cret"

    def sig(self, body):
        return (
            "sha256="
            + hmac.new(
                self.secret, body.encode() if isinstance(body, str) else body, hashlib.sha256
            ).hexdigest()
        )

    def test_status_codes(self):
        body = '{"zen": "keep it logically awesome"}'
        assert validate_signature({"body": body}, self.secret, self.sig(body))["statusCode"] == 200
        assert (
            validate_signature({"body": body}, self.secret, self.sig("other"))["statusCode"] == 401
        )
        assert validate_signature({"body": body}, self.secret, "no-prefix")["statusCode"] == 401
        assert validate_signature({"body": body}, self.secret, "")["statusCode"] == 401
        assert validate_signature({}, self.secret, "x")["statusCode"] == 400
        assert (
            validate_signature({"body": "!!", "isBase64Encoded": True}, self.secret, "x")[
                "statusCode"
            ]
            == 400
        )

    def test_base64_bodies(self):
        body = '{"a": 1}'
        event = {"body": base64.b64encode(body.encode()).decode(), "isBase64Encoded": True}
        assert validate_signature(event, self.secret, self.sig(body))["statusCode"] == 200

    def test_the_size_limit_applies_to_decoded_bytes(self):
        big = "a" * (MAX_PAYLOAD_BYTES + 1)
        assert validate_signature({"body": big}, self.secret, self.sig(big))["statusCode"] == 413
        # base64 text of a body just under the limit is longer than the limit but decodes below it
        near = b"a" * (MAX_PAYLOAD_BYTES - 10)
        event = {"body": base64.b64encode(near).decode(), "isBase64Encoded": True}
        assert validate_signature(event, self.secret, self.sig(near))["statusCode"] == 200
