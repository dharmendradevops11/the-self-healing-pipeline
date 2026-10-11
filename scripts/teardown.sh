#!/usr/bin/env bash
# Tear everything down (Chapter 17, "Teardown and Cleanup"). Deploying infrastructure bills you,
# so this leaves nothing running.
#
#   AWS_PROFILE=... AWS_REGION=us-east-1 ./scripts/teardown.sh
set -uo pipefail

CDK="${CDK:-npx --yes aws-cdk@2}"
# cdk.json runs `python app.py`: use the project's virtual environment when there is one.
[ -d .venv/bin ] && export PATH="$PWD/.venv/bin:$PATH"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
REPO="self-healing-pipeline/healer-agent"

# Know where you are before deleting anything: fail if there are no usable credentials.
IDENTITY="$(aws sts get-caller-identity --query '[Account,Arn]' --output text 2>&1)" || {
  echo "ERROR: cannot identify the AWS account (${IDENTITY}). Nothing was deleted." >&2
  exit 1
}
echo "Tearing down in account ${IDENTITY%%$'\t'*}, region ${REGION}"
if [ -n "${EXPECTED_ACCOUNT:-}" ] && [ "${IDENTITY%%$'\t'*}" != "${EXPECTED_ACCOUNT}" ]; then
  echo "ERROR: signed in to ${IDENTITY%%$'\t'*} but EXPECTED_ACCOUNT is ${EXPECTED_ACCOUNT}. Nothing was deleted." >&2
  exit 1
fi
FAILED=0

echo "== 1. Destroy the CDK stacks (Lambdas, Fargate tasks, Step Functions, queues, tables)"
${CDK} destroy --all -f || { echo "ERROR: cdk destroy failed; stacks may remain" >&2; FAILED=1; }

echo "== 2. Empty and delete the container repository"
# batch-delete-image fails on a repository with no images, so ignore that error.
IMAGES="$(aws ecr list-images --repository-name "${REPO}" --region "${REGION}" --query 'imageIds[*]' --output json 2>/dev/null || echo '[]')"
if [ "${IMAGES}" != "[]" ] && [ -n "${IMAGES}" ]; then
  aws ecr batch-delete-image --repository-name "${REPO}" --region "${REGION}" --image-ids "${IMAGES}" >/dev/null || true
fi
aws ecr delete-repository --repository-name "${REPO}" --region "${REGION}" --force 2>/dev/null || true

echo "== 2b. Log groups the stack's own cleanup functions leave behind (they are created at run time, so the stack does not own them)"
for g in $(aws logs describe-log-groups --region "${REGION}" --log-group-name-prefix /aws/lambda/SelfHealingState-CustomS3AutoDelete --query 'logGroups[].logGroupName' --output text 2>/dev/null); do
  aws logs delete-log-group --region "${REGION}" --log-group-name "$g" 2>/dev/null && echo "deleted $g"
done

echo "== 3. State bucket (disposable) and audit bucket (check Object Lock first)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
STATE="self-healing-pipeline-state-${ACCOUNT}"
# `cdk destroy` already empties and deletes it; this only catches a stack that never finished.
aws s3 rm "s3://${STATE}/" --recursive 2>/dev/null && aws s3api delete-bucket --bucket "${STATE}" 2>/dev/null || true
echo "If you deployed with healer:audit_object_lock=true, the audit bucket is under Object Lock and was"
echo "kept on purpose. Objects under an unexpired retention date cannot be deleted. Wait for expiry"
echo "instead of weakening the control. Check it with:"
echo "  aws s3api list-buckets --query 'Buckets[?contains(Name, \`audit\`)].Name'"
echo "  aws s3api get-object-lock-configuration --bucket <name>"

echo "== 4. Secrets"
echo "The pipeline reads your GitHub token and webhook secrets but never created them. Delete them yourself if"
echo "you no longer need them (and revoke the GitHub token, and remove the repository webhook):"
echo "  aws secretsmanager delete-secret --secret-id <arn> --recovery-window-in-days 7"

echo "== 5. What is left (anything listed here still exists and may bill you)"
LEFT="$(aws cloudformation list-stacks --region "${REGION}" \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE ROLLBACK_COMPLETE DELETE_FAILED UPDATE_ROLLBACK_COMPLETE \
  --query 'StackSummaries[?starts_with(StackName, `SelfHealing`)].[StackName,StackStatus]' --output text 2>&1)" || FAILED=1
[ -n "${LEFT}" ] && { echo "stacks: ${LEFT}"; FAILED=1; } || echo "stacks: none"
aws ecr describe-repositories --region "${REGION}" --repository-names "${REPO}" >/dev/null 2>&1 \
  && { echo "ecr: ${REPO} still exists"; FAILED=1; } || echo "ecr: none"
aws s3api list-buckets --query 'Buckets[?starts_with(Name, `self-healing-pipeline-`)].Name' --output text
echo "(buckets above: the audit bucket is kept on purpose while Object Lock retention runs)"
exit "${FAILED}"
