#!/usr/bin/env python3
"""The CDK app. `cdk deploy --all -c healer:github_repo_url=https://github.com/you/repo ...`"""

import aws_cdk as cdk

from infra.config import DeployConfig
from infra.pipeline_stack import PipelineStack
from infra.state_stack import StateStack

app = cdk.App()
cfg = DeployConfig.from_context(app.node.try_get_context)
cfg.validate()

state = StateStack(app, "SelfHealingState", cfg)
PipelineStack(app, "SelfHealingPipeline", cfg, state)

app.synth()
