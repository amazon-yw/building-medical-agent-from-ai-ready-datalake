#!/bin/bash
export AWS_REGION="${AWS_REGION:-us-west-2}"
export AGENT_ARN=$(aws bedrock-agentcore-control list-agent-runtimes --region "$AWS_REGION" \
  --query 'agentRuntimes[?status==`READY`].agentRuntimeArn | [0]' --output text)

if [ "$AGENT_ARN" = "None" ] || [ -z "$AGENT_ARN" ]; then
  echo "ERROR: No READY agent runtime found." >&2
  exit 1
fi
echo "AGENT_ARN: $AGENT_ARN"

python3.12 -m streamlit run agent/app.py --server.port 8501 --server.address 0.0.0.0
