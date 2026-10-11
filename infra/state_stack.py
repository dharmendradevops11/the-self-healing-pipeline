"""Storage and the container registry (Chapter 17, "Building and Shipping the Containers")."""

from __future__ import annotations

from typing import Any

from aws_cdk import Aws, CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from constructs import Construct

from infra.config import DeployConfig

REPOSITORY_NAME = "self-healing-pipeline/healer-agent"


class StateStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, cfg: DeployConfig, **kwargs: Any):
        super().__init__(scope, construct_id, **kwargs)
        removal = RemovalPolicy.RETAIN if cfg.retain_data else RemovalPolicy.DESTROY
        locked = cfg.audit_object_lock

        # Audit bucket: versioned, private, encrypted, TLS only. With Object Lock the audit trail
        # cannot be deleted until retention expires (Chapters 8, 11, 17).
        self.audit_bucket = s3.Bucket(
            self,
            "AuditBucket",
            # Chapter 17 names it self-healing-pipeline-audit-logs; S3 names are global, so the
            # account id keeps it unique.
            bucket_name=f"self-healing-pipeline-audit-logs-{Aws.ACCOUNT_ID}",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            object_lock_enabled=locked,
            object_lock_default_retention=s3.ObjectLockRetention.governance(
                Duration.days(cfg.audit_retention_days)
            )
            if locked
            else None,
            removal_policy=RemovalPolicy.RETAIN if (locked or cfg.retain_data) else removal,
            auto_delete_objects=not (locked or cfg.retain_data),
            # Appendix H: after the retention window, lifecycle policies permanently prune records.
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="prune-audit-records",
                    expiration=Duration.days(cfg.audit_retention_days),
                    noncurrent_version_expiration=Duration.days(cfg.audit_retention_days),
                )
            ],
        )

        # State bucket (Chapter 8's state bus): disposable, tears down normally (Chapter 17).
        self.state_bucket = s3.Bucket(
            self,
            "StateBucket",
            bucket_name=f"self-healing-pipeline-state-{Aws.ACCOUNT_ID}",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=removal,
            auto_delete_objects=not cfg.retain_data,
            lifecycle_rules=[
                s3.LifecycleRule(
                    prefix="pipeline-state/",
                    expiration=Duration.days(30),
                    noncurrent_version_expiration=Duration.days(1),
                    id="expire-pipeline-state",
                ),
                # Appendix H: staging heap dumps are cleared after 7 days.
                s3.LifecycleRule(
                    prefix="heap-dumps/", expiration=Duration.days(7), id="expire-heap-dumps"
                ),
            ],
        )

        def table(name: str, pk: str, sk: str | None = None) -> dynamodb.Table:
            return dynamodb.Table(
                self,
                name,
                partition_key=dynamodb.Attribute(name=pk, type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name=sk, type=dynamodb.AttributeType.STRING)
                if sk
                else None,
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                removal_policy=removal,
                point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=True
                ),
            )

        # Chapter 2: the investigation limiter, 3 per service per hour.
        self.rate_table = table("RateLimitTable", "service", "hour")
        # Sentry issue markers (ingest dedupe) carry `expires_at` and are removed a day later.
        self.rate_table.node.default_child.add_property_override(  # type: ignore[union-attr]
            "TimeToLiveSpecification", {"AttributeName": "expires_at", "Enabled": True}
        )
        # Chapter 17: the daily PR cap, one item per day.
        self.throttle_table = table("ThrottleTable", "pk")
        # Chapter 9: the trust ledger, with the category index the composite score reads.
        self.ledger_table = table("TrustLedger", "execution_id")
        self.ledger_table.add_global_secondary_index(
            index_name="category-timestamp-index",
            partition_key=dynamodb.Attribute(name="category", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="timestamp", type=dynamodb.AttributeType.STRING),
        )
        # Chapter 2, Stage 4: what was done and what the human decided.
        self.history_table = table("RemediationHistory", "incident_id")
        self.history_table.add_global_secondary_index(
            index_name="service-created-index",
            partition_key=dynamodb.Attribute(name="service", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="created_at", type=dynamodb.AttributeType.STRING),
        )

        self.repository = ecr.Repository(
            self,
            "HealerAgentRepository",
            repository_name=REPOSITORY_NAME,
            image_scan_on_push=True,
            removal_policy=removal,
            empty_on_delete=not cfg.retain_data,
        )

        # Results and escalations. Informational goes to Slack, only critical pages (Chapter 9).
        self.notification_topic = sns.Topic(self, "NotificationTopic")
        if cfg.notification_email:
            self.notification_topic.add_subscription(subs.EmailSubscription(cfg.notification_email))

        if cfg.billing_alarm_usd > 0:
            # Billing metrics exist only in us-east-1 and only after "Receive Billing Alerts" is on.
            alarm = cloudwatch.Alarm(
                self,
                "BillingAlarm",
                metric=cloudwatch.Metric(
                    namespace="AWS/Billing",
                    metric_name="EstimatedCharges",
                    dimensions_map={"Currency": "USD"},
                    statistic="Maximum",
                    period=Duration.hours(6),
                ),
                threshold=cfg.billing_alarm_usd,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                alarm_description="Self-healing pipeline account spend (Chapter 17)",
            )
            alarm.add_alarm_action(cw_actions.SnsAction(self.notification_topic))

        CfnOutput(self, "RepositoryUri", value=self.repository.repository_uri)
        CfnOutput(self, "AuditBucketName", value=self.audit_bucket.bucket_name)
        CfnOutput(self, "StateBucketName", value=self.state_bucket.bucket_name)
        CfnOutput(self, "NotificationTopicArn", value=self.notification_topic.topic_arn)
