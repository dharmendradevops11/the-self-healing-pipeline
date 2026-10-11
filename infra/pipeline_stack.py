"""The pipeline itself: Figure 2.1 as infrastructure.

Webhook -> API Gateway -> receiver Lambda -> SNS -> SQS -> EventBridge Pipe -> Step Functions:

    INGEST (Lambda) -> INVESTIGATE (Fargate) -> route (Lambda) -> Choice
        -> escalate (Lambda)                                  [score or blast radius says no]
        -> FIX (Fargate) -> route (Lambda) -> TEST (Fargate) -> PR (Lambda) -> NOTIFY (Lambda)

Fargate output cannot be read by Step Functions, so every stage shares one state object in S3 and
Step Functions carries only the execution id.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_pipes as pipes
from aws_cdk import aws_secretsmanager as sm
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from infra.config import DeployConfig
from infra.state_stack import StateStack

ROOT = Path(__file__).resolve().parent.parent


class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cfg: DeployConfig,
        state: StateStack,
        **kwargs: Any,
    ):
        super().__init__(scope, construct_id, **kwargs)
        self.cfg, self.state = cfg, state
        retain = RemovalPolicy.RETAIN if cfg.retain_data else RemovalPolicy.DESTROY

        github = self._secret("GitHubSecret", cfg.github_secret_arn)
        slack = self._secret("SlackSecret", cfg.slack_secret_arn)
        webhook_secret = self._secret("WebhookSecret", cfg.webhook_secret_arn)
        previous_secret = self._secret("PreviousWebhookSecret", cfg.previous_webhook_secret_arn)
        gh_hook_secret = self._secret("GitHubWebhookSecret", cfg.github_webhook_secret_arn)

        # ---------------------------------------------------------------- shared configuration
        env = {
            "HEALER_AUDIT_BUCKET": state.audit_bucket.bucket_name,
            "HEALER_STATE_BUCKET": state.state_bucket.bucket_name,
            "HEALER_RATE_TABLE": state.rate_table.table_name,
            "HEALER_TRUST_LEDGER_TABLE": state.ledger_table.table_name,
            "HEALER_HISTORY_TABLE": state.history_table.table_name,
            "HEALER_THROTTLE_TABLE": state.throttle_table.table_name,
            "HEALER_NOTIFICATION_TOPIC_ARN": state.notification_topic.topic_arn,
            "GITHUB_REPO_URL": cfg.github_repo_url,
            "GITHUB_BASE_BRANCH": cfg.base_branch,
            "BEDROCK_MODEL_ID": cfg.bedrock_model_id,
            "BEDROCK_REGION": self.region,
            "BEDROCK_REGIONS": cfg.bedrock_regions,
            "BEDROCK_FALLBACK_MODEL_ID": cfg.bedrock_fallback_model_id,
            "BEDROCK_QUICK_MODEL_ID": cfg.bedrock_quick_model_id,
            "HEALER_PHASE": cfg.phase,
            "HEALER_SERVICE_REGISTRY": cfg.service_registry,
            "HEALER_UNKNOWN_SERVICE_TIER": cfg.unknown_service_tier,
            "HEALER_MAX_DAILY_PRS": str(cfg.max_daily_prs),
            "HEALER_CONFIDENCE_THRESHOLD": str(cfg.confidence_threshold),
            "HEALER_LOG_LINES": str(cfg.log_lines),
        }
        # Only the ARNs of secrets are configuration. The values are fetched at the moment of use
        # (Chapter 11, "Never in Environment Variables").
        if github:
            env["GITHUB_TOKEN_SECRET_ARN"] = github.secret_arn
        if slack:
            env["SLACK_WEBHOOK_SECRET_ARN"] = slack.secret_arn

        bedrock = iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/anthropic.*",
                f"arn:aws:bedrock:*:{self.account}:inference-profile/*anthropic*",
            ],
        )

        # ---------------------------------------------------------------- Lambdas
        code = lam.Code.from_asset(
            str(ROOT),
            exclude=["*", "!healer", "!healer/**", "**/__pycache__", "**/*.pyc"],
        )

        def function(
            name: str,
            handler: str,
            seconds: int = 60,
            memory: int = 256,
            extra_env: dict[str, str] | None = None,
            role_name: str | None = None,
        ) -> lam.Function:
            role = (
                iam.Role(
                    self,
                    f"{name}Role",
                    role_name=role_name,
                    assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                    managed_policies=[
                        iam.ManagedPolicy.from_aws_managed_policy_name(
                            "service-role/AWSLambdaBasicExecutionRole"
                        )
                    ],
                )
                if role_name
                else None
            )
            return lam.Function(
                self,
                name,
                runtime=lam.Runtime.PYTHON_3_11,
                handler=handler,
                code=code,
                timeout=Duration.seconds(seconds),
                memory_size=memory,
                environment={**env, **(extra_env or {})},
                role=role,
                log_group=logs.LogGroup(
                    self,
                    f"{name}Logs",
                    retention=logs.RetentionDays.ONE_MONTH,
                    removal_policy=retain,
                ),
            )

        self.trigger_topic = sns.Topic(self, "TriggerTopic")
        receiver_env = {"HEALER_TRIGGER_TOPIC_ARN": self.trigger_topic.topic_arn}
        if webhook_secret:
            receiver_env["SENTRY_WEBHOOK_SECRET_ARN"] = webhook_secret.secret_arn
        if previous_secret:
            receiver_env["SENTRY_WEBHOOK_PREVIOUS_SECRET_ARN"] = previous_secret.secret_arn

        self.webhook_fn = function(
            "WebhookReceiver", "healer.handlers.webhook_handler", 15, 256, receiver_env
        )
        # GitHub pull_request events: records what the reviewer decided (Chapter 9, the ledger).
        feedback_env = (
            {"GITHUB_WEBHOOK_SECRET_ARN": gh_hook_secret.secret_arn} if gh_hook_secret else {}
        )
        self.feedback_fn = function(
            "GitHubWebhook", "healer.handlers.github_webhook_handler", 15, 256, feedback_env
        )
        state.ledger_table.grant_read_write_data(self.feedback_fn)
        state.history_table.grant_read_write_data(self.feedback_fn)
        if gh_hook_secret:
            gh_hook_secret.grant_read(self.feedback_fn)
        self.ingest_fn = function(
            "Ingest", "healer.handlers.ingest_handler", 120, 512, role_name="Healer-Ingest-Role"
        )
        self.route_fn = function("Route", "healer.handlers.route_handler", 30)
        self.pr_fn = function("OpenPr", "healer.handlers.pr_handler", 120, 512)
        self.notify_fn = function("Notify", "healer.handlers.notify_handler", 60)

        # Least privilege, per function: each gets only what its stage does.
        self.trigger_topic.grant_publish(self.webhook_fn)
        for secret in (webhook_secret, previous_secret):
            if secret:
                secret.grant_read(self.webhook_fn)

        for fn in (self.ingest_fn, self.route_fn, self.pr_fn, self.notify_fn):
            state.audit_bucket.grant_read_write(fn)
            state.state_bucket.grant_read_write(fn)  # the S3 state bus
        state.rate_table.grant_read_write_data(self.ingest_fn)
        self.ingest_fn.add_to_role_policy(bedrock)  # the guardrail classifier
        self.ingest_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["logs:FilterLogEvents"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/ecs/*:*"],
            )
        )
        for fn in (self.pr_fn, self.notify_fn):
            state.ledger_table.grant_read_write_data(fn)
        state.history_table.grant_read_write_data(self.pr_fn)
        state.notification_topic.grant_publish(self.notify_fn)
        if github:
            github.grant_read(self.pr_fn)
            github.grant_read(self.notify_fn)  # Escalate opens the report-only PR
        if slack:
            slack.grant_read(self.notify_fn)

        # ---------------------------------------------------------------- Fargate
        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,  # public subnets only: no NAT gateway to pay for
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                )
            ],
        )
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)
        security_group = ec2.SecurityGroup(
            self, "AgentSecurityGroup", vpc=vpc, allow_all_outbound=True
        )

        # Appendix F names the Investigate role. FIX and TEST get their own, so TEST never holds
        # a Bedrock permission and no task can delete an audit record.
        def task_role(name: str, role_name: str, model: bool, throttle: bool) -> iam.Role:
            role = iam.Role(
                self,
                name,
                role_name=role_name,
                assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            )
            if model:
                role.add_to_policy(bedrock)
            state.audit_bucket.grant_read_write(role)
            state.state_bucket.grant_read_write(role)
            state.ledger_table.grant_read_write_data(role)
            if model:
                # Chapter 8 reads recent CPU and memory history. CloudWatch has no resource ARNs
                # for metric reads, so this is the one place a wildcard resource is unavoidable.
                role.add_to_policy(
                    iam.PolicyStatement(
                        actions=["cloudwatch:ListMetrics", "cloudwatch:GetMetricStatistics"],
                        resources=["*"],
                    )
                )
            if model:  # the stages that reason read earlier incidents (Chapter 14 flags)
                state.history_table.grant_read_data(role)
            if model:  # a stage that decides can also need to tell a human (escalate)
                state.notification_topic.grant_publish(role)
            if throttle:
                state.throttle_table.grant_read_write_data(role)
            if github:
                github.grant_read(role)
            return role

        # Appendix F: the role that may restart things. It may act only on resources tagged
        # healer-eligible=true (a different tag from chaos-eligible). No task assumes it yet; it
        # exists so a restart-class remediation has somewhere safe to run (healer.remediate).
        self.remediate_role = iam.Role(
            self,
            "RemediateRole",
            role_name="Healer-Remediate-Role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        eligible = {"StringEquals": {"aws:ResourceTag/healer-eligible": "true"}}
        self.remediate_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecs:UpdateService", "ssm:SendCommand"],
                resources=["*"],  # scoped by the tag condition, the only scoping these support
                conditions=eligible,
            )
        )
        self.remediate_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecs:DescribeServices", "ecs:ListTagsForResource"],
                resources=[f"arn:aws:ecs:{self.region}:{self.account}:service/*"],
            )
        )
        investigate_role = task_role("InvestigateRole", "Healer-Investigate-Role", True, False)
        fix_role = task_role("FixRole", "Healer-Fix-Role", True, True)
        test_role = task_role("TestRole", "Healer-Test-Role", False, False)

        # The audit trail is append-only to everything we deploy (Appendix F, Healer-Audit-Logger).
        def no_audit_delete() -> iam.PolicyStatement:
            return iam.PolicyStatement(
                effect=iam.Effect.DENY,
                actions=["s3:DeleteObject", "s3:DeleteObjectVersion"],
                resources=[state.audit_bucket.arn_for_objects("*")],
            )

        def hard_limits() -> iam.PolicyStatement:
            """Chapter 11: certain actions are never automated, whatever any other policy grants.

            IAM allows are additive, a Deny always wins. It sits on "*" on purpose: a Deny that
            gets broader as it gets stricter is a guardrail, not a risk. Nothing here can delete
            a table or database, touch IAM or billing, or assume another role.
            """
            return iam.PolicyStatement(
                effect=iam.Effect.DENY,
                actions=[
                    "dynamodb:DeleteTable",
                    "rds:DeleteDBInstance",
                    "rds:DeleteDBCluster",
                    "iam:*",
                    "aws-portal:*",
                    "billing:*",
                    "sts:AssumeRole",
                ],
                resources=["*"],
            )

        for fn in (self.webhook_fn, self.feedback_fn, self.ingest_fn, self.route_fn):
            fn.add_to_role_policy(hard_limits())
        for fn in (self.pr_fn, self.notify_fn):
            fn.add_to_role_policy(hard_limits())
        for fn in (self.ingest_fn, self.route_fn, self.pr_fn, self.notify_fn):
            fn.add_to_role_policy(no_audit_delete())
        for role in (investigate_role, fix_role, test_role, self.remediate_role):
            role.add_to_policy(hard_limits())
            role.add_to_policy(no_audit_delete())

        agent_logs = logs.LogGroup(
            self, "AgentLogs", retention=logs.RetentionDays.ONE_MONTH, removal_policy=retain
        )
        image = ecs.ContainerImage.from_ecr_repository(state.repository, cfg.image_tag)

        def agent(
            name: str, command: str, cpu: int, memory: int, role: iam.Role
        ) -> tuple[ecs.FargateTaskDefinition, ecs.ContainerDefinition]:
            definition = ecs.FargateTaskDefinition(
                self,
                f"{name}Task",
                cpu=cpu,
                memory_limit_mib=memory,
                task_role=role,
                runtime_platform=ecs.RuntimePlatform(
                    cpu_architecture=ecs.CpuArchitecture.X86_64,
                    operating_system_family=ecs.OperatingSystemFamily.LINUX,
                ),
            )
            container = definition.add_container(
                f"healer-{command}",
                image=image,
                command=[command],
                environment=env,
                logging=ecs.LogDrivers.aws_logs(stream_prefix=command, log_group=agent_logs),
            )
            return definition, container

        investigate_def, investigate_c = agent(
            "Investigate", "investigate", 1024, 2048, investigate_role
        )
        fix_def, fix_c = agent("Fix", "fix", 1024, 2048, fix_role)
        test_def, test_c = agent("Test", "test", 2048, 4096, test_role)

        # ---------------------------------------------------------------- the state machine
        def lambda_step(
            name: str,
            fn: lam.Function,
            payload: dict[str, object] | None = None,
            result_path: str | None = None,
        ) -> tasks.LambdaInvoke:
            return tasks.LambdaInvoke(
                self,
                f"{name}State",
                state_name=name,
                lambda_function=fn,
                # Step Functions treats `"Parameters": "$"` as a literal string, so name the fields.
                payload=sfn.TaskInput.from_object(
                    payload
                    or {
                        "executionId": sfn.JsonPath.string_at("$.executionId"),
                        "incident": sfn.JsonPath.object_at("$.incident"),
                    }
                ),
                payload_response_only=True,
                result_path=result_path if result_path else sfn.JsonPath.DISCARD,
                retry_on_service_exceptions=True,
            )

        def agent_step(
            name: str, definition: ecs.FargateTaskDefinition, container: ecs.ContainerDefinition
        ) -> tasks.EcsRunTask:
            return tasks.EcsRunTask(
                self,
                f"{name}State",
                state_name=name,
                integration_pattern=sfn.IntegrationPattern.RUN_JOB,
                cluster=cluster,
                task_definition=definition,
                launch_target=tasks.EcsFargateLaunchTarget(
                    platform_version=ecs.FargatePlatformVersion.LATEST
                ),
                assign_public_ip=True,
                subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                security_groups=[security_group],
                container_overrides=[
                    tasks.ContainerOverride(
                        container_definition=container,
                        environment=[
                            tasks.TaskEnvironmentVariable(
                                name="EXECUTION_ID", value=sfn.JsonPath.string_at("$.executionId")
                            )
                        ],
                    )
                ],
                result_path=sfn.JsonPath.DISCARD,
                task_timeout=sfn.Timeout.duration(Duration.minutes(20)),
            )

        exec_id: dict[str, object] = {"executionId": sfn.JsonPath.string_at("$.executionId")}

        def on_failure(stage: str) -> sfn.IChainable:
            """A crashed stage tells a human, then fails the execution so it is visible."""
            notify = lambda_step(
                f"NotifyFailure{stage}",
                self.notify_fn,
                {
                    **exec_id,
                    "mode": "failure",
                    "stage": stage.lower(),
                    "incident": sfn.JsonPath.object_at("$.incident"),
                    "error": sfn.JsonPath.object_at("$.error"),
                },
            )
            return notify.next(
                sfn.Fail(self, f"Failed{stage}", error="PipelineError", cause=f"{stage} failed")
            )

        ingest = lambda_step("Ingest", self.ingest_fn, None, "$.ingest")
        investigate = agent_step("Investigate", investigate_def, investigate_c)
        route = lambda_step("Route", self.route_fn, exec_id, "$.route")
        fix = agent_step("Fix", fix_def, fix_c)
        route_after_fix = lambda_step("RouteAfterFix", self.route_fn, exec_id, "$.route")
        test = agent_step("Test", test_def, test_c)
        open_pr = lambda_step("OpenPr", self.pr_fn, exec_id)
        notify = lambda_step("Notify", self.notify_fn, {**exec_id, "mode": "result"})
        escalate = lambda_step(
            "Escalate",
            self.notify_fn,
            {
                **exec_id,
                "mode": "escalate",
                "reason": "the escalation matrix does not authorize a fix",
            },
        )

        working_stages = {
            "Ingest": ingest,
            "Investigate": investigate,
            "Route": route,
            "Fix": fix,
            "RouteAfterFix": route_after_fix,
            "Test": test,
            "OpenPr": open_pr,
            "Notify": notify,
            "Escalate": escalate,
        }
        for stage_name, step in working_stages.items():
            step.add_catch(on_failure(stage_name), errors=["States.ALL"], result_path="$.error")

        dropped = sfn.Succeed(
            self, "Dropped", comment="rate limited, or blocked by the guardrail classifier"
        )
        escalated = sfn.Succeed(self, "Escalated", comment="a human has the whole analysis")
        fix_ended = sfn.Succeed(
            self, "FixEnded", comment="shadow mode, daily cap, or the fix was refused"
        )
        opened = sfn.Succeed(self, "PullRequestOpened")

        after_fix = (
            sfn.Choice(self, "FixOutcome")
            .when(
                sfn.Condition.string_equals("$.route.status", "running"),
                test.next(open_pr).next(notify).next(opened),
            )
            .otherwise(fix_ended)
        )
        gate = (
            sfn.Choice(
                self,
                "Gate",
                comment="Figure 2.1: may the pipeline write a fix, or must it escalate?",
            )
            .when(
                sfn.Condition.string_equals("$.route.fixAction", "investigation_only"),
                escalate.next(escalated),
            )
            .otherwise(fix.next(route_after_fix).next(after_fix))
        )
        accepted = (
            sfn.Choice(self, "Accepted")
            .when(
                sfn.Condition.string_equals("$.ingest.status", "running"),
                investigate.next(route).next(gate),
            )
            .otherwise(dropped)
        )
        # EventBridge Pipes hands a Step Functions target a one-item ARRAY (found on real AWS),
        # while a direct start-execution passes an object. Accept both.
        unwrap = sfn.Pass(
            self,
            "UnwrapBatchState",
            state_name="UnwrapBatch",
            parameters={
                "executionId": sfn.JsonPath.string_at("$[0].executionId"),
                "incident": sfn.JsonPath.object_at("$[0].incident"),
            },
        )
        definition = (
            sfn.Choice(self, "InputShapeState", state_name="InputShape")
            .when(sfn.Condition.is_present("$[0]"), unwrap.next(ingest))
            .otherwise(ingest)
        )
        ingest.next(accepted)

        state_logs = logs.LogGroup(
            self, "StateMachineLogs", retention=logs.RetentionDays.ONE_MONTH, removal_policy=retain
        )
        self.state_machine = sfn.StateMachine(
            self,
            "StateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.hours(1),
            # ALL with execution data: every state's input and output is in the log, which is how a
            # run is traced hop by hop (scripts/trace.py). Inputs hold incident text and no secrets.
            logs=sfn.LogOptions(
                destination=state_logs, level=sfn.LogLevel.ALL, include_execution_data=True
            ),
        )

        # ------------------------- SNS -> SQS -> EventBridge Pipe -> Step Functions
        dead_letters = sqs.Queue(
            self, "TriggerDeadLetters", encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True
        )
        queue = sqs.Queue(
            self,
            "TriggerQueue",
            visibility_timeout=Duration.minutes(5),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dead_letters),
        )
        self.trigger_topic.add_subscription(subs.SqsSubscription(queue, raw_message_delivery=True))

        pipe_role = iam.Role(
            self, "PipeRole", assumed_by=iam.ServicePrincipal("pipes.amazonaws.com")
        )
        queue.grant_consume_messages(pipe_role)
        self.state_machine.grant_start_execution(pipe_role)
        pipe_logs = logs.LogGroup(
            self, "PipeLogs", retention=logs.RetentionDays.ONE_MONTH, removal_policy=retain
        )
        pipe_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[pipe_logs.log_group_arn, f"{pipe_logs.log_group_arn}:*"],
            )
        )
        pipes.CfnPipe(
            self,
            "TriggerPipe",
            role_arn=pipe_role.role_arn,
            source=queue.queue_arn,
            source_parameters=pipes.CfnPipe.PipeSourceParametersProperty(
                sqs_queue_parameters=pipes.CfnPipe.PipeSourceSqsQueueParametersProperty(
                    batch_size=1
                )
            ),
            target=self.state_machine.state_machine_arn,
            # What the pipe read from the queue and what it started, for every message.
            log_configuration=pipes.CfnPipe.PipeLogConfigurationProperty(
                level="INFO",
                include_execution_data=["ALL"],
                cloudwatch_logs_log_destination=pipes.CfnPipe.CloudwatchLogsLogDestinationProperty(
                    log_group_arn=pipe_logs.log_group_arn
                ),
            ),
            target_parameters=pipes.CfnPipe.PipeTargetParametersProperty(
                step_function_state_machine_parameters=pipes.CfnPipe.PipeTargetStateMachineParametersProperty(
                    invocation_type="FIRE_AND_FORGET"
                ),
                input_template=(
                    '{"executionId": <$.body.executionId>, "incident": <$.body.incident>}'
                ),
            ),
        )

        # ------------------------------------------------- the front door
        api = apigw.RestApi(
            self,
            "WebhookApi",
            endpoint_types=[apigw.EndpointType.REGIONAL],
            deploy_options=apigw.StageOptions(
                stage_name="prod", throttling_rate_limit=10, throttling_burst_limit=20
            ),
        )
        api.root.add_resource("github").add_method(
            "POST", apigw.LambdaIntegration(self.feedback_fn)
        )
        api.root.add_resource("webhook").add_method(
            "POST", apigw.LambdaIntegration(self.webhook_fn)
        )

        CfnOutput(
            self,
            "GitHubWebhookUrl",
            value=f"{api.url}github",
            description="Configure this on the repository (pull_request events)",
        )
        CfnOutput(
            self, "WebhookUrl", value=f"{api.url}webhook", description="Configure this in Sentry"
        )
        CfnOutput(self, "StateMachineArn", value=self.state_machine.state_machine_arn)
        CfnOutput(self, "TriggerQueueUrl", value=queue.queue_url)
        CfnOutput(self, "TriggerTopicArn", value=self.trigger_topic.topic_arn)
        CfnOutput(self, "PipeLogGroup", value=pipe_logs.log_group_name)
        CfnOutput(self, "AgentLogGroup", value=agent_logs.log_group_name)

    def _secret(self, construct_id: str, arn: str) -> sm.ISecret | None:
        """A reference to a secret you created. No secret value is created or read here."""
        return sm.Secret.from_secret_complete_arn(self, construct_id, arn) if arn else None
