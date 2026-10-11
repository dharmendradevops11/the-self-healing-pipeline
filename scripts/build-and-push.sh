#!/usr/bin/env bash
# Build the healer-agent image and push it to ECR (Chapter 17, "Building and Shipping the Containers").
#
#   AWS_PROFILE=... AWS_REGION=us-east-1 ./scripts/build-and-push.sh [tag]
#
# The SelfHealingState stack must be deployed first: it creates the ECR repository.
set -euo pipefail

TAG="${1:-latest}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REPO="self-healing-pipeline/healer-agent"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REGISTRY}/${REPO}:${TAG}"

aws ecr describe-repositories --repository-names "${REPO}" --region "${REGION}" >/dev/null \
  || { echo "ECR repository ${REPO} not found. Deploy the state stack first: make deploy-state" >&2; exit 1; }

# Fargate runs linux/amd64. Building for it explicitly matters on an Apple Silicon Mac.
docker build --platform linux/amd64 -t "${REPO}:${TAG}" -f docker/healer-agent/Dockerfile .

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

docker tag "${REPO}:${TAG}" "${IMAGE}"
docker push "${IMAGE}"
echo "pushed ${IMAGE}"
