#!/usr/bin/env bash
# Deploy in the order Chapter 17 describes: storage and the registry, then the image, then the pipeline.
#
#   AWS_PROFILE=... AWS_REGION=us-east-1 ./scripts/deploy.sh \
#     -c healer:github_repo_url=https://github.com/you/repo \
#     -c healer:github_secret_arn=arn:aws:secretsmanager:... \
#     -c healer:webhook_secret_arn=arn:aws:secretsmanager:...
#
# Any `-c key=value` arguments are passed straight to cdk. See docs/deploy.md.
set -euo pipefail

CDK="${CDK:-npx --yes aws-cdk@2}"
# cdk.json runs `python app.py`: use the project's virtual environment when there is one.
[ -d .venv/bin ] && export PATH="$PWD/.venv/bin:$PATH"
export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1

echo "== 1. State stack: bucket, tables, container registry, notification topic"
${CDK} deploy SelfHealingState --require-approval never "$@"

echo "== 2. Build and push the healer-agent image"
./scripts/build-and-push.sh "$(python3 -c "import sys; print(next((a.split('=',1)[1] for a in sys.argv[1:] if a.startswith('healer:image_tag=')), 'latest'))" "$@")"

echo "== 3. Pipeline stack: VPC, Fargate tasks, Lambdas, queue, pipe, state machine"
${CDK} deploy SelfHealingPipeline --require-approval never "$@"
