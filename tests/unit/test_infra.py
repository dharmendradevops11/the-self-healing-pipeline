"""The CDK stacks, synthesized offline and checked as templates. No AWS account, no deploy."""

import json
import os

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

os.environ.setdefault("JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION", "1")

from infra.config import DeployConfig  # noqa: E402
from infra.pipeline_stack import PipelineStack  # noqa: E402
from infra.state_stack import REPOSITORY_NAME, StateStack  # noqa: E402

ENV = cdk.Environment(account="111122223333", region="us-east-1")
GH = "arn:aws:secretsmanager:us-east-1:111122223333:secret:gh-AbCdEf"
WH = "arn:aws:secretsmanager:us-east-1:111122223333:secret:wh-AbCdEf"
SLACK = "arn:aws:secretsmanager:us-east-1:111122223333:secret:slack-AbCdEf"


def synth(**overrides):
    cfg = DeployConfig(
        **{
            "github_repo_url": "https://github.com/acme/api",
            "github_secret_arn": GH,
            "webhook_secret_arn": WH,
            **overrides,
        }
    )
    app = cdk.App()
    state = StateStack(app, "State", cfg, env=ENV)
    pipeline = PipelineStack(app, "Pipeline", cfg, state, env=ENV)
    return Template.from_stack(state), Template.from_stack(pipeline), pipeline


@pytest.fixture(scope="module")
def stacks():
    return synth()


def definition(template: Template) -> dict:
    """The state machine's ASL, with CDK tokens replaced by placeholders so it parses."""
    machine = next(iter(template.find_resources("AWS::StepFunctions::StateMachine").values()))
    parts = machine["Properties"]["DefinitionString"]["Fn::Join"][1]
    return json.loads("".join(p if isinstance(p, str) else "TOKEN" for p in parts))


# ------------------------------------------------------------------------ state stack


class TestState:
    def test_the_audit_bucket_is_private_encrypted_versioned_and_tls_only(self, stacks):
        state, _, _ = stacks
        state.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "VersioningConfiguration": {"Status": "Enabled"},
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
                "BucketEncryption": Match.any_value(),
            },
        )
        state.has_resource_properties(
            "AWS::S3::BucketPolicy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Effect": "Deny",
                                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_the_book_s_tables_exist_with_the_keys_the_code_uses(self, stacks):
        state, _, _ = stacks
        tables = {
            t["Properties"]["KeySchema"][0]["AttributeName"]: t
            for t in state.find_resources("AWS::DynamoDB::Table").values()
        }
        assert set(tables) == {"service", "pk", "execution_id", "incident_id"}
        rate = next(
            t
            for t in state.find_resources("AWS::DynamoDB::Table").values()
            if t["Properties"]["KeySchema"][0]["AttributeName"] == "service"
        )
        assert [k["AttributeName"] for k in rate["Properties"]["KeySchema"]] == ["service", "hour"]
        state.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": [{"AttributeName": "execution_id", "KeyType": "HASH"}],
                "GlobalSecondaryIndexes": [
                    Match.object_like({"IndexName": "category-timestamp-index"})
                ],
                "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
                "BillingMode": "PAY_PER_REQUEST",
            },
        )
        state.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": [{"AttributeName": "incident_id", "KeyType": "HASH"}],
                "GlobalSecondaryIndexes": [
                    Match.object_like({"IndexName": "service-created-index"})
                ],
            },
        )

    def test_the_container_registry_has_the_name_chapter_17_uses(self, stacks):
        state, _, _ = stacks
        assert REPOSITORY_NAME == "self-healing-pipeline/healer-agent"
        state.has_resource_properties(
            "AWS::ECR::Repository",
            {"RepositoryName": REPOSITORY_NAME, "ImageScanningConfiguration": {"ScanOnPush": True}},
        )

    def test_by_default_everything_can_be_torn_down_with_cdk_destroy(self, stacks):
        state, _, _ = stacks
        for kind in ("AWS::S3::Bucket", "AWS::DynamoDB::Table", "AWS::ECR::Repository"):
            for r in state.find_resources(kind).values():
                assert r["DeletionPolicy"] == "Delete", kind

    def test_object_lock_makes_the_audit_trail_append_only_and_retains_it(self):
        state, _, _ = synth(audit_object_lock=True, audit_retention_days=400)
        state.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "ObjectLockEnabled": True,
                "ObjectLockConfiguration": {
                    "ObjectLockEnabled": "Enabled",
                    "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 400}},
                },
            },
        )
        buckets = state.find_resources("AWS::S3::Bucket")
        audit = next(r for k, r in buckets.items() if k.startswith("AuditBucket"))
        assert audit["DeletionPolicy"] == "Retain"  # a locked audit bucket must not be torn down
        state_bucket = next(r for k, r in buckets.items() if k.startswith("StateBucket"))
        assert state_bucket["DeletionPolicy"] == "Delete"  # the disposable one still tears down
        assert "ObjectLockEnabled" not in state_bucket["Properties"]

    def test_audit_and_state_live_in_two_buckets_as_chapter_17_names_them(self, stacks):
        state, _, _ = stacks
        names = [
            "".join(
                p if isinstance(p, str) else "<account>"
                for p in r["Properties"]["BucketName"]["Fn::Join"][1]
            )
            for r in state.find_resources("AWS::S3::Bucket").values()
        ]
        assert sorted(names) == [
            "self-healing-pipeline-audit-logs-<account>",
            "self-healing-pipeline-state-<account>",
        ]

    def test_retain_data_keeps_the_tables(self):
        state, _, _ = synth(retain_data=True)
        assert all(
            r["DeletionPolicy"] == "Retain"
            for r in state.find_resources("AWS::DynamoDB::Table").values()
        )

    def test_an_optional_email_subscribes_to_the_notification_topic(self):
        state, _, _ = synth(notification_email="oncall@example.com")
        state.has_resource_properties(
            "AWS::SNS::Subscription", {"Protocol": "email", "Endpoint": "oncall@example.com"}
        )
        plain, _, _ = synth()
        plain.resource_count_is("AWS::SNS::Subscription", 0)


# ------------------------------------------------------------------------ the pipeline


class TestWorkflow:
    def test_it_is_figure_2_1_as_a_state_machine(self, stacks):
        _, pipeline, _ = stacks
        asl = definition(pipeline)
        states = asl["States"]
        assert asl["StartAt"] == "InputShape"
        shape = states["InputShape"]  # the pipe delivers an array; a direct start gives an object
        assert (
            shape["Choices"][0]["Variable"] == "$[0]"
            and shape["Choices"][0]["Next"] == "UnwrapBatch"
        )
        assert shape["Default"] == "Ingest" and states["UnwrapBatch"]["Next"] == "Ingest"
        assert {
            "Ingest",
            "Accepted",
            "Investigate",
            "Route",
            "Gate",
            "Escalate",
            "Fix",
            "RouteAfterFix",
            "FixOutcome",
            "Test",
            "OpenPr",
            "Notify",
            "Dropped",
            "Escalated",
            "FixEnded",
            "PullRequestOpened",
        } <= set(states)
        assert states["Ingest"]["Next"] == "Accepted"
        assert states["Investigate"]["Next"] == "Route"

    def test_the_gate_sends_what_the_matrix_refuses_to_a_human_and_everything_else_to_fix(
        self, stacks
    ):
        _, pipeline, _ = stacks
        gate = definition(pipeline)["States"]["Gate"]
        assert gate["Type"] == "Choice"
        assert gate["Choices"] == [
            {
                "Variable": "$.route.fixAction",
                "StringEquals": "investigation_only",
                "Next": "Escalate",
            }
        ]
        assert gate["Default"] == "Fix"
        assert definition(pipeline)["States"]["Escalate"]["Next"] == "Escalated"

    def test_a_dropped_or_ended_run_stops_before_the_expensive_stages(self, stacks):
        _, pipeline, _ = stacks
        s = definition(pipeline)["States"]
        assert (
            s["Accepted"]["Choices"][0]["Next"] == "Investigate"
            and s["Accepted"]["Default"] == "Dropped"
        )
        assert (
            s["FixOutcome"]["Choices"][0]["Next"] == "Test"
            and s["FixOutcome"]["Default"] == "FixEnded"
        )
        assert (
            s["Test"]["Next"] == "OpenPr"
            and s["OpenPr"]["Next"] == "Notify"
            and s["Notify"]["Next"] == "PullRequestOpened"
        )

    def test_investigate_fix_and_test_are_fargate_tasks_that_wait_for_completion(self, stacks):
        _, pipeline, _ = stacks
        s = definition(pipeline)["States"]
        for name in ("Investigate", "Fix", "Test"):
            assert s[name]["Resource"].endswith(":states:::ecs:runTask.sync")
            env = s[name]["Parameters"]["Overrides"]["ContainerOverrides"][0]["Environment"]
            assert env == [{"Name": "EXECUTION_ID", "Value.$": "$.executionId"}]
            assert (
                s[name]["Parameters"]["NetworkConfiguration"]["AwsvpcConfiguration"][
                    "AssignPublicIp"
                ]
                == "ENABLED"
            )

    def test_every_working_stage_reports_a_crash_to_a_human_instead_of_dying_silently(self, stacks):
        _, pipeline, _ = stacks
        s = definition(pipeline)["States"]
        for name in (
            "Ingest",
            "Investigate",
            "Route",
            "Fix",
            "RouteAfterFix",
            "Test",
            "OpenPr",
            "Notify",
            "Escalate",
        ):
            catch = s[name]["Catch"][0]
            assert (
                catch["ErrorEquals"] == ["States.ALL"] and catch["Next"] == f"NotifyFailure{name}"
            )
            assert (
                s[catch["Next"]]["Next"] == f"Failed{name}" and s[f"Failed{name}"]["Type"] == "Fail"
            )

    def test_fargate_output_is_never_read_the_state_travels_through_s3(self, stacks):
        _, pipeline, _ = stacks
        s = definition(pipeline)["States"]
        for name in ("Investigate", "Fix", "Test"):
            assert (
                s[name]["ResultPath"] is None
            )  # Step Functions cannot read a Fargate task's output


class TestCompute:
    def test_six_python_lambdas_with_the_handlers_the_package_exports(self, stacks):
        _, pipeline, _ = stacks
        fns = pipeline.find_resources("AWS::Lambda::Function")
        handlers = sorted(
            f["Properties"]["Handler"] for f in fns.values() if f["Properties"].get("Runtime")
        )
        assert handlers == sorted(
            [
                "healer.handlers.github_webhook_handler",
                "healer.handlers.webhook_handler",
                "healer.handlers.ingest_handler",
                "healer.handlers.route_handler",
                "healer.handlers.pr_handler",
                "healer.handlers.notify_handler",
            ]
        )
        assert all(
            f["Properties"]["Runtime"] == "python3.11"
            for f in fns.values()
            if f["Properties"].get("Runtime")
        )

    def test_the_handlers_named_in_the_stack_exist(self):
        from healer import handlers

        for name in (
            "webhook_handler",
            "ingest_handler",
            "route_handler",
            "pr_handler",
            "notify_handler",
        ):
            assert callable(getattr(handlers, name))

    def test_three_fargate_task_definitions_run_the_book_s_image_with_the_right_command(
        self, stacks
    ):
        _, pipeline, _ = stacks
        defs = pipeline.find_resources("AWS::ECS::TaskDefinition").values()
        commands = sorted(d["Properties"]["ContainerDefinitions"][0]["Command"][0] for d in defs)
        assert commands == ["fix", "investigate", "test"]
        for d in defs:
            assert d["Properties"]["RequiresCompatibilities"] == ["FARGATE"]
            assert d["Properties"]["RuntimePlatform"]["CpuArchitecture"] == "X86_64"

    def test_there_is_no_nat_gateway(self, stacks):
        _, pipeline, _ = stacks
        pipeline.resource_count_is("AWS::EC2::NatGateway", 0)

    def test_the_front_door_is_one_post_route_with_a_dead_letter_queue_behind_it(self, stacks):
        _, pipeline, _ = stacks
        pipeline.has_resource_properties(
            "AWS::ApiGateway::Method", {"HttpMethod": "POST", "AuthorizationType": "NONE"}
        )
        pipeline.has_resource_properties(
            "AWS::SQS::Queue",
            {"RedrivePolicy": {"maxReceiveCount": 3, "deadLetterTargetArn": Match.any_value()}},
        )
        pipeline.has_resource_properties(
            "AWS::SNS::Subscription", {"Protocol": "sqs", "RawMessageDelivery": True}
        )

    def test_the_pipe_starts_the_state_machine_from_the_queue(self, stacks):
        _, pipeline, _ = stacks
        pipeline.has_resource_properties(
            "AWS::Pipes::Pipe",
            {
                "TargetParameters": {
                    "StepFunctionStateMachineParameters": {"InvocationType": "FIRE_AND_FORGET"},
                    "InputTemplate": Match.string_like_regexp("executionId.*incident"),
                }
            },
        )


class TestSecurity:
    def policies(self, template):
        for policy in template.find_resources("AWS::IAM::Policy").values():
            yield from policy["Properties"]["PolicyDocument"]["Statement"]

    @staticmethod
    def actions(statement):
        a = statement["Action"]
        return a if isinstance(a, list) else [a]

    def test_no_secret_value_or_token_is_ever_an_environment_variable(self, stacks):
        _, pipeline, _ = stacks
        envs = [
            f["Properties"].get("Environment", {}).get("Variables", {})
            for f in pipeline.find_resources("AWS::Lambda::Function").values()
        ]
        envs += [
            {
                e["Name"]: e.get("Value")
                for e in d["Properties"]["ContainerDefinitions"][0]["Environment"]
            }
            for d in pipeline.find_resources("AWS::ECS::TaskDefinition").values()
        ]
        for env in envs:
            for key in env:
                assert key.endswith("_ARN") or not any(
                    w in key for w in ("TOKEN", "SECRET", "PASSWORD", "KEY")
                ), key
        assert any("GITHUB_TOKEN_SECRET_ARN" in env for env in envs)

    def test_our_own_roles_never_use_wildcard_actions_or_resources(self, stacks):
        state, pipeline, _ = stacks
        # CloudWatch metric reads cannot be scoped to a resource: the service has no resource ARNs.
        allowed_wildcards = {
            ("ecr:GetAuthorizationToken",),
            ("ecs:StopTask", "ecs:DescribeTasks"),
            ("cloudwatch:ListMetrics", "cloudwatch:GetMetricStatistics"),
        }
        for template in (state, pipeline):
            for st in self.policies(template):
                if st["Effect"] == "Deny":
                    continue  # Chapter 11: a Deny on "*" is a guardrail, not a risk
                acts = self.actions(st)
                assert "*" not in acts and not any(a.endswith(":*") for a in acts), acts
                if st["Resource"] == "*" or (
                    isinstance(st["Resource"], list) and "*" in st["Resource"]
                ):
                    is_log_delivery = all(a.startswith("logs:") for a in acts)
                    tag_scoped = (
                        st.get("Condition", {})
                        .get("StringEquals", {})
                        .get("aws:ResourceTag/healer-eligible")
                        == "true"
                    )  # Appendix F: scoped by the healer-eligible tag, the only scoping available
                    assert tuple(acts) in allowed_wildcards or is_log_delivery or tag_scoped, acts

    def test_bedrock_is_limited_to_anthropic_models(self, stacks):
        _, pipeline, _ = stacks
        statements = [
            s for s in self.policies(pipeline) if "bedrock:InvokeModel" in self.actions(s)
        ]
        assert statements
        for s in statements:
            resources = s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
            flat = json.dumps(resources)
            assert "anthropic" in flat and '"*"' not in flat

    def test_each_secret_is_readable_only_by_the_stages_that_need_it(self, stacks):
        _, pipeline, _ = stacks

        def readers(arn: str) -> set[str]:
            found = set()
            for name, policy in pipeline.find_resources("AWS::IAM::Policy").items():
                for st in policy["Properties"]["PolicyDocument"]["Statement"]:
                    if "secretsmanager:GetSecretValue" in self.actions(st) and arn in json.dumps(
                        st["Resource"]
                    ):
                        found.add(name.rsplit("DefaultPolicy", 1)[0].rstrip("0123456789ABCDEF"))
            return found

        github = readers(GH)
        assert (
            len(github) == 5
            and any("OpenPr" in n for n in github)
            and any("Notify" in n for n in github)
            and all(any(r in n for n in github) for r in ("InvestigateRole", "FixRole", "TestRole"))
        )
        webhook = readers(WH)
        assert len(webhook) == 1 and any("WebhookReceiver" in n for n in webhook)

    def test_the_webhook_receiver_cannot_touch_the_data_stores(self, stacks):
        _, pipeline, _ = stacks
        for name, policy in pipeline.find_resources("AWS::IAM::Policy").items():
            if "WebhookReceiver" in name:
                allows = [
                    st
                    for st in policy["Properties"]["PolicyDocument"]["Statement"]
                    if st["Effect"] == "Allow"
                ]
                flat = json.dumps(allows)
                assert "dynamodb" not in flat and "s3:" not in flat and "bedrock" not in flat

    def test_the_task_role_cannot_publish_notifications_or_open_pull_requests_through_other_services(
        self, stacks
    ):
        _, pipeline, _ = stacks
        for name, policy in pipeline.find_resources("AWS::IAM::Policy").items():
            if "AgentTaskRole" in name:
                flat = json.dumps(policy["Properties"]["PolicyDocument"])
                assert (
                    "sns:Publish" not in flat
                    and "ecs:RunTask" not in flat
                    and "lambda:" not in flat
                )


class TestOptionalWiring:
    def test_slack_is_wired_only_when_a_secret_is_given(self):
        _, with_slack, _ = synth(slack_secret_arn=SLACK)
        _, without, _ = synth()
        assert "SLACK_WEBHOOK_SECRET_ARN" in json.dumps(with_slack.to_json())
        assert "SLACK_WEBHOOK_SECRET_ARN" not in json.dumps(without.to_json())

    def test_the_registry_and_phase_reach_every_stage(self):
        registry = json.dumps({"api": {"estimated_users": 5, "owner": "t"}})
        _, pipeline, _ = synth(service_registry=registry, phase="shadow", max_daily_prs=1)
        flat = json.dumps(pipeline.to_json())
        assert "HEALER_PHASE" in flat and "shadow" in flat and "estimated_users" in flat


class TestConfig:
    def test_context_overrides_defaults(self):
        values = {
            "healer:phase": "shadow",
            "healer:max_daily_prs": "5",
            "healer:audit_object_lock": "true",
            "healer:service_registry": {"api": {"estimated_users": 1}},
        }
        cfg = DeployConfig.from_context(values.get)
        assert (cfg.phase, cfg.max_daily_prs, cfg.audit_object_lock) == ("shadow", 5, True)
        assert json.loads(cfg.service_registry) == {"api": {"estimated_users": 1}}
        assert DeployConfig.from_context({}.get).phase == "supervised"

    def test_bad_values_are_rejected_before_anything_is_deployed(self):
        with pytest.raises(ValueError, match="phase"):
            DeployConfig(phase="yolo").validate()
        with pytest.raises(ValueError, match="tier"):
            DeployConfig(unknown_service_tier="enormous").validate()
        with pytest.raises(ValueError):
            DeployConfig(service_registry="{not json").validate()


class TestAppendixF:
    """Appendix F names the roles and the one hard rule: nobody deletes an audit record."""

    def test_the_named_roles_exist(self, stacks):
        _, pipeline, _ = stacks
        names = {
            r["Properties"].get("RoleName")
            for r in pipeline.find_resources("AWS::IAM::Role").values()
        }
        assert {"Healer-Ingest-Role", "Healer-Investigate-Role"} <= names

    def test_test_task_has_no_model_access_and_every_role_is_denied_audit_deletes(self, stacks):
        _, pipeline, _ = stacks
        policies = pipeline.find_resources("AWS::IAM::Policy")
        for logical_id, policy in policies.items():
            statements = policy["Properties"]["PolicyDocument"]["Statement"]
            actions = [a for st in statements for a in _as_list(st["Action"])]
            if "TestRole" in logical_id:
                assert not any(a.startswith("bedrock:") for a in actions)
            if any(k in logical_id for k in ("TestRole", "FixRole", "InvestigateRole", "Ingest")):
                assert any(
                    st["Effect"] == "Deny" and "s3:DeleteObject" in _as_list(st["Action"])
                    for st in statements
                ), logical_id


def _as_list(value):
    return value if isinstance(value, list) else [value]


def test_every_task_passes_named_fields_not_a_bare_json_path(stacks):
    """Found on real AWS: `"Parameters": "$"` reaches the Lambda as the literal string "$"."""
    _, pipeline, _ = stacks
    for name, state in definition(pipeline)["States"].items():
        if state.get("Type") == "Task" and "Parameters" in state:
            assert isinstance(state["Parameters"], dict), name


def test_stages_that_read_incident_history_are_allowed_to_query_it(stacks):
    """Found on real AWS: INVESTIGATE queries remediation_history and was denied."""
    _, pipeline, _ = stacks
    for logical_id, policy in pipeline.find_resources("AWS::IAM::Policy").items():
        if "InvestigateRole" in logical_id or "FixRole" in logical_id:
            actions = [
                a
                for st in policy["Properties"]["PolicyDocument"]["Statement"]
                for a in _as_list(st["Action"])
            ]
            assert "dynamodb:Query" in actions, logical_id


def test_stages_that_can_escalate_may_publish_to_the_notification_topic(stacks):
    """Found on real AWS: FIX escalated and was denied sns:Publish."""
    _, pipeline, _ = stacks
    for logical_id, policy in pipeline.find_resources("AWS::IAM::Policy").items():
        if "FixRole" in logical_id or "InvestigateRole" in logical_id:
            actions = [
                a
                for st in policy["Properties"]["PolicyDocument"]["Statement"]
                for a in _as_list(st["Action"])
            ]
            assert "sns:Publish" in actions, logical_id


class TestVerdictFeedback:
    def test_github_can_post_pull_request_events_and_the_function_can_only_touch_the_ledger(self):
        _, pipeline, _ = synth(
            github_webhook_secret_arn="arn:aws:secretsmanager:us-east-1:1:secret:gh-AbCdEf"
        )
        pipeline.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "github"})
        envs = [
            r["Properties"]["Environment"]["Variables"]
            for r in pipeline.find_resources("AWS::Lambda::Function").values()
            if "Environment" in r["Properties"]
        ]
        assert any("GITHUB_WEBHOOK_SECRET_ARN" in e for e in envs)
        assert all(
            "GITHUB_WEBHOOK_SECRET_ARN" not in e or "SENTRY_WEBHOOK_SECRET_ARN" not in e
            for e in envs
        )  # each receiver reads only its own secret


class TestHardLimits:
    """Chapter 11: explicit Deny statements for what must never be automated."""

    def test_every_role_we_create_is_denied_the_hard_limits(self, stacks):
        _, pipeline, _ = stacks
        denies = {}
        for logical_id, policy in pipeline.find_resources("AWS::IAM::Policy").items():
            for st in policy["Properties"]["PolicyDocument"]["Statement"]:
                if st["Effect"] == "Deny" and "iam:*" in _as_list(st["Action"]):
                    denies[logical_id] = _as_list(st["Action"])
        for name in ("InvestigateRole", "FixRole", "TestRole", "Ingest", "OpenPr", "Notify"):
            assert any(name in k for k in denies), name
        for actions in denies.values():
            assert {"dynamodb:DeleteTable", "rds:DeleteDBInstance", "sts:AssumeRole"} <= set(
                actions
            )


class TestRemediateRole:
    def test_it_exists_by_the_appendix_f_name_and_acts_only_on_tagged_resources(self, stacks):
        _, pipeline, _ = stacks
        names = {
            r["Properties"].get("RoleName")
            for r in pipeline.find_resources("AWS::IAM::Role").values()
        }
        assert "Healer-Remediate-Role" in names
        for logical_id, policy in pipeline.find_resources("AWS::IAM::Policy").items():
            if "RemediateRole" not in logical_id:
                continue
            acting = [
                st
                for st in policy["Properties"]["PolicyDocument"]["Statement"]
                if st["Effect"] == "Allow" and "ecs:UpdateService" in _as_list(st["Action"])
            ]
            assert acting and all(
                st["Condition"]["StringEquals"]["aws:ResourceTag/healer-eligible"] == "true"
                for st in acting
            )


class TestTraceability:
    """Every hop leaves evidence (scripts/trace.py reads it)."""

    def test_the_state_machine_logs_all_states_with_their_data(self, stacks):
        _, pipeline, _ = stacks
        pipeline.has_resource_properties(
            "AWS::StepFunctions::StateMachine",
            {
                "LoggingConfiguration": {
                    "Level": "ALL",
                    "IncludeExecutionData": True,
                    "Destinations": Match.any_value(),
                }
            },
        )

    def test_the_pipe_logs_what_it_read_and_what_it_started(self, stacks):
        _, pipeline, _ = stacks
        pipeline.has_resource_properties(
            "AWS::Pipes::Pipe",
            {
                "LogConfiguration": {
                    "Level": "INFO",
                    "IncludeExecutionData": ["ALL"],
                    "CloudwatchLogsLogDestination": Match.any_value(),
                }
            },
        )

    def test_the_outputs_the_trace_script_needs_exist(self, stacks):
        _, pipeline, _ = stacks
        outputs = pipeline.to_json()["Outputs"]
        assert {"TriggerQueueUrl", "TriggerTopicArn", "PipeLogGroup", "AgentLogGroup"} <= set(
            outputs
        )
