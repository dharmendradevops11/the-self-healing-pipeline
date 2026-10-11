# Chapter 17, "Building and Shipping the Containers":
#   docker build --platform linux/amd64 -t self-healing-pipeline/webhook-receiver:latest \
#     -f docker/webhook-receiver/Dockerfile .
# The CDK stack deploys the receiver as a zip Lambda (see docs/deploy.md); this image runs the
# same handler as a Lambda container image, for readers who prefer the container route.
FROM public.ecr.aws/lambda/python:3.11

COPY docker/webhook-receiver/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt
COPY healer/ ${LAMBDA_TASK_ROOT}/healer/

CMD ["healer.handlers.webhook_handler"]
