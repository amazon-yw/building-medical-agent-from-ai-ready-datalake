#!/bin/bash
# deploy_react_app.sh — Build React app and deploy to EC2 (run on EC2)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/react_agent"
DIST_DIR="$APP_DIR/dist"
REGION="${AWS_REGION:-$(curl -sf -H "X-aws-ec2-metadata-token: $(curl -sf -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600')" http://169.254.169.254/latest/meta-data/placement/region || echo us-west-2)}"

# ── 1. Generate .env ──────────────────────────────────────────────────────────
echo ">>> Generating .env from AWS resources..."

AGENT_ARN=$(aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" \
  --query "agentRuntimes[?status=='READY' && !contains(agentRuntimeName,'legacy')].agentRuntimeArn | [0]" \
  --output text 2>/dev/null || true)

LEGACY_AGENT_ARN=$(aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" \
  --query "agentRuntimes[?contains(agentRuntimeName,'legacy') && status=='READY'].agentRuntimeArn | [0]" \
  --output text 2>/dev/null || true)

# Cognito from CloudFormation outputs
get_output() {
  aws cloudformation describe-stacks --stack-name FhirDataStack --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

CF_DOMAIN=$(aws cloudfront list-distributions --region us-east-1 \
  --query "DistributionList.Items[?Origins.Items[0].DomainName!=null] | [0].DomainName" \
  --output text 2>/dev/null || true)
# Fallback: get from CFN output
if [ -z "$CF_DOMAIN" ] || [ "$CF_DOMAIN" = "None" ]; then
  REACT_APP_URL=$(get_output "ReactAppURL")
  CF_DOMAIN=$(echo "$REACT_APP_URL" | sed 's|https://||' | cut -d'/' -f1)
fi

USER_POOL_ID=$(get_output "CognitoUserPoolId")
CLIENT_ID=$(get_output "CognitoClientId")
COGNITO_DOMAIN=$(get_output "CognitoDomain")

# Validate
for var in AGENT_ARN LEGACY_AGENT_ARN USER_POOL_ID CLIENT_ID COGNITO_DOMAIN CF_DOMAIN; do
  val="${!var}"
  if [ -z "$val" ] || [ "$val" = "None" ]; then
    echo "ERROR: Could not resolve $var. Check that FhirDataStack is deployed and agent runtimes are READY."
    exit 1
  fi
done

cat > "$APP_DIR/.env" << EOF
AWS_REGION=${REGION}
AGENT_ARN=${AGENT_ARN}
LEGACY_AGENT_ARN=${LEGACY_AGENT_ARN}
VITE_COGNITO_USER_POOL_ID=${USER_POOL_ID}
VITE_COGNITO_CLIENT_ID=${CLIENT_ID}
VITE_COGNITO_DOMAIN=${COGNITO_DOMAIN}
VITE_COGNITO_REDIRECT_URI=https://${CF_DOMAIN}/app
EOF

echo ">>> .env written:"
cat "$APP_DIR/.env"

# ── 2. Install Python deps ────────────────────────────────────────────────────
echo ">>> Installing Python dependencies..."
pip3 install -q flask flask-cors boto3 gunicorn PyJWT cryptography

# ── 3. Install Node deps & build ─────────────────────────────────────────────
echo ">>> Building React app (main)..."
cd "$APP_DIR"
set -a; source .env; set +a
npm install --silent
npm run build

echo ">>> Building React app (legacy)..."
VITE_APP_MODE=legacy \
VITE_COGNITO_REDIRECT_URI="https://${CF_DOMAIN}/app-legacy" \
npm run build

echo ">>> Build output: $DIST_DIR (main) + ${DIST_DIR}-legacy (legacy)"

# ── 4. Install nginx config ───────────────────────────────────────────────────
echo ">>> Installing nginx config..."
sudo cp "$APP_DIR/nginx-medical-agent.conf" /etc/nginx/conf.d/medical-agent.conf
sudo rm -f /etc/nginx/conf.d/code-editor.conf 2>/dev/null || true
sudo nginx -t
sudo systemctl reload nginx

# ── 5. Install & start systemd service ───────────────────────────────────────
echo ">>> Installing systemd service..."
GUNICORN_BIN=$(which gunicorn 2>/dev/null || echo "/home/participant/.local/bin/gunicorn")
sed -e "s|__APP_DIR__|${APP_DIR}|g" \
    -e "s|__GUNICORN__|${GUNICORN_BIN}|g" \
    "$APP_DIR/medical-agent-api.service" \
    | sudo tee /etc/systemd/system/medical-agent-api.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable medical-agent-api
sudo systemctl restart medical-agent-api

sleep 2
if systemctl is-active --quiet medical-agent-api; then
  echo ">>> API service is running"
else
  echo "ERROR: API service failed to start"
  sudo journalctl -u medical-agent-api -n 20 --no-pager
  exit 1
fi

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "✅ Deployment complete!"
echo "   Main App  : https://${CF_DOMAIN}/app"
echo "   Legacy App: https://${CF_DOMAIN}/app-legacy"
echo "   API Health: https://${CF_DOMAIN}/api/health"
