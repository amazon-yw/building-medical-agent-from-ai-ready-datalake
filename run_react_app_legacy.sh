#!/bin/bash
# export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_REGION="${AWS_REGION:-$(curl -s -H "X-aws-ec2-metadata-token: $(curl -s -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600')" http://169.254.169.254/latest/meta-data/placement/region)}"
export VITE_APP_MODE="legacy"

export AGENT_ARN=$(aws bedrock-agentcore-control list-agent-runtimes --region "$AWS_REGION" \
  --query "agentRuntimes[?contains(agentRuntimeName,'legacy') && status=='READY'].agentRuntimeArn | [0]" --output text)

if [ "$AGENT_ARN" = "None" ] || [ -z "$AGENT_ARN" ]; then
  echo "ERROR: No READY legacy agent runtime found." >&2
  exit 1
fi
echo "AGENT_ARN: $AGENT_ARN"
echo "UI: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo localhost):6100"

cd "$(dirname "$0")/react_agent"
pip install -q flask flask-cors boto3 2>/dev/null
npm install --silent 2>/dev/null
npx concurrently "vite --port=4000 --host=0.0.0.0" "python3 server.py"
