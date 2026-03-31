#!/bin/bash
# Usage: ./allow_ip.sh <IP_ADDRESS>
# Example: ./allow_ip.sh 203.0.113.50

if [ -z "$1" ]; then
  echo "Usage: $0 <IP_ADDRESS>" >&2
  exit 1
fi

SG_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=*CodeEditor*" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].SecurityGroups[0].GroupId" --output text)
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"

for PORT in 8501 3000; do
  aws ec2 authorize-security-group-ingress --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp --port "$PORT" \
    --cidr "$1/32" 2>/dev/null && echo "Allowed $1 on port $PORT" || echo "Port $PORT already open for $1"
done
