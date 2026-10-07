aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

docker tag self-healing-pipeline/webhook-receiver:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/self-healing-pipeline/webhook-receiver:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/self-healing-pipeline/webhook-receiver:latest
