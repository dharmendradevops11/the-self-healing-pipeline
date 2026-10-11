# The healer agent: INVESTIGATE, FIX and TEST run from this one image (Chapter 17,
# "Building and Shipping the Containers"). Build it for linux/amd64, which is what Fargate runs:
#   docker build --platform linux/amd64 -t self-healing-pipeline/healer-agent:latest -f docker/healer-agent/Dockerfile .
FROM python:3.11-slim

# git clones the repository under repair. ca-certificates lets it reach GitHub over TLS.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/healer-agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY healer/ ./healer/

# Run as an unprivileged user: this container executes code a model wrote.
RUN useradd --create-home --uid 10001 healer
USER healer
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# The state machine passes the stage as the command: investigate | fix | test
ENTRYPOINT ["python", "-m", "healer.tasks"]
