"""Infrastructure as code (Chapter 17): AWS CDK, in Python.

Two stacks: SelfHealingState (storage, the container registry, the notification topic) and
SelfHealingPipeline (the VPC, Fargate tasks, Lambdas, queue, pipe and the state machine).
Tear everything down with `cdk destroy --all -f`.
"""
