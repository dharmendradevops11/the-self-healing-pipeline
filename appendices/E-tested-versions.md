# Appendix E: Tested-version matrix

| Component | Book | This repository |
|---|---|---|
| Python | 3.11.x | 3.11 (virtual environment, Lambda runtime, Docker image) |
| Node.js | 20.x LTS | needed only for the CDK CLI. Newer Node prints a jsii "untested" warning; `JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1` silences it |
| boto3 | 1.34.x | `requirements.txt` |
| AWS CDK | 2.138.0+ | `aws-cdk-lib>=2.138` (`requirements-dev.txt`) |
| Amazon Bedrock | runtime API, `bedrock-2023-05-31` | `healer/llm/bedrock.py` |
| Claude model | `anthropic.claude-sonnet-4-20250514-v1:0`, now legacy | **configuration, not code**: `BEDROCK_MODEL_ID` / `healer:bedrock_model_id`. Pick a supported model and revalidate |
| LocalStack | 3.4.0+ | `localstack/localstack:3.4.0` in `docker-compose.yml` |
| Docker | 24.0.7+ | |
| statsmodels / scikit-learn / Prophet | 0.14.1 / 1.4.x / 1.1.5 | pinned; Prophet is optional (`requirements-analytics.txt`) |

Model identifiers, Bedrock quotas and prices change on AWS's schedule. The architecture does not change with a model swap; only
the identifier moves.
