docker build \
  --platform linux/amd64 \
  -t self-healing-pipeline/webhook-receiver:latest \
  -f docker/webhook-receiver/Dockerfile .
