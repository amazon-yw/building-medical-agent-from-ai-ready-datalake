"""Proxy server for AgentCore Runtime"""
import os, json, time, urllib.request
import boto3
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
AGENT_ARN = os.getenv("AGENT_ARN", "")
LEGACY_AGENT_ARN = os.getenv("LEGACY_AGENT_ARN", "")
USER_POOL_ID = os.getenv("VITE_COGNITO_USER_POOL_ID", "")
ALLOWED_ORIGIN = os.getenv("VITE_COGNITO_REDIRECT_URI", "")

# CORS: restrict to CloudFront origin in production
CORS(app, origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN else "*", supports_credentials=True)

# ── JWT verification (Cognito) ────────────────────────────────────────────────

_jwks_cache: dict = {}
_jwks_fetched_at: float = 0

def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache and time.time() - _jwks_fetched_at < 3600:
        return _jwks_cache
    url = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
    with urllib.request.urlopen(url, timeout=5) as r:
        _jwks_cache = json.loads(r.read())
        _jwks_fetched_at = time.time()
    return _jwks_cache

def _verify_token(token: str) -> bool:
    """Verify Cognito JWT signature and expiry using PyJWT if available, else basic check."""
    if not USER_POOL_ID:
        return True  # Cognito not configured — allow (dev mode)
    try:
        import jwt as pyjwt
        jwks = _get_jwks()
        header = pyjwt.get_unverified_header(token)
        key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
        if not key:
            return False
        public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        pyjwt.decode(
            token, public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return True
    except Exception:
        return False

def _require_auth() -> "Response | None":
    """Return 401 response if token invalid, else None."""
    if not USER_POOL_ID:
        return None  # dev mode
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return Response(json.dumps({"error": "Unauthorized"}), status=401, mimetype="application/json")
    token = auth[7:]
    if not _verify_token(token):
        return Response(json.dumps({"error": "Invalid token"}), status=401, mimetype="application/json")
    return None

# ── Routes ────────────────────────────────────────────────────────────────────

def get_client():
    from botocore.config import Config
    return boto3.client("bedrock-agentcore", region_name=REGION, config=Config(read_timeout=300))


def _parse_chunk(text):
    text = text.strip()
    if text.startswith("data: "):
        text = text[6:]
    if not text:
        return ""
    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
        except json.JSONDecodeError:
            text = text[1:-1]
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    if not text:
        return ""
    try:
        if text.startswith("{"):
            data = json.loads(text)
            for key in ("content", "response", "text"):
                if key in data:
                    val = data[key]
                    if key == "content" and isinstance(val, list) and val:
                        item = val[0]
                        return item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    return str(val)
            return str(data)
    except json.JSONDecodeError:
        pass
    return text


@app.route("/api/chat", methods=["POST"])
def chat():
    err = _require_auth()
    if err:
        return err

    data = request.json
    prompt = data.get("prompt", "")
    session_id = data.get("sessionId", "default")
    arn = AGENT_ARN

    if not arn:
        return Response("data: [ERROR] AGENT_ARN not set\n\n", content_type="text/event-stream")

    return _stream_response(arn, prompt, session_id)


@app.route("/api/legacy/chat", methods=["POST"])
def legacy_chat():
    err = _require_auth()
    if err:
        return err

    data = request.json
    prompt = data.get("prompt", "")
    session_id = data.get("sessionId", "default")
    arn = LEGACY_AGENT_ARN

    if not arn:
        return Response("data: [ERROR] LEGACY_AGENT_ARN not set\n\n", content_type="text/event-stream")

    return _stream_response(arn, prompt, session_id)


def _stream_response(arn: str, prompt: str, session_id: str):
    def generate():
        try:
            client = get_client()
            resp = client.invoke_agent_runtime(
                agentRuntimeArn=arn,
                payload=json.dumps({"prompt": prompt}).encode(),
                runtimeSessionId=session_id,
                contentType="application/json",
                accept="application/json",
            )
            ct = resp.get("contentType", "")

            if "text/event-stream" in ct:
                for line in resp["response"].iter_lines(chunk_size=1):
                    if not line:
                        continue
                    text = line.decode("utf-8") if isinstance(line, bytes) else line
                    parsed = _parse_chunk(text)
                    if parsed:
                        safe = parsed.replace("\n", "%%NL%%")
                        yield f"data: {safe}\n\n"
            else:
                raw = resp["response"].read()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                yield f"data: {raw}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return Response(generate(), content_type="text/event-stream")


@app.route("/api/health")
def health():
    return {"status": "ok", "region": REGION, "agentArn": "set" if AGENT_ARN else "missing"}


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "3001"))
    print(f"API server on http://0.0.0.0:{port} | REGION={REGION} | AGENT_ARN={'set' if AGENT_ARN else 'missing'}")
    app.run(host="0.0.0.0", port=port)
