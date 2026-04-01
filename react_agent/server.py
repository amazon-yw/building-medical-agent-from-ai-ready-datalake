"""Proxy server for AgentCore Runtime"""
import os, json, re, boto3
from flask import Flask, request, Response

app = Flask(__name__)

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
AGENT_ARN = os.getenv("AGENT_ARN", "")


def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


def _parse_chunk(text):
    """Extract text from a streaming chunk."""
    text = text.strip()
    if text.startswith("data: "):
        text = text[6:]
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


def _clean(text):
    if not text:
        return text
    text = re.sub(r'"\s*"', "", text)
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    prompt = data.get("prompt", "")
    session_id = data.get("sessionId", "default")

    if not AGENT_ARN:
        return Response('data: {"error": "AGENT_ARN not set"}\n\n', content_type="text/event-stream")

    def generate():
        try:
            client = get_client()
            resp = client.invoke_agent_runtime(
                agentRuntimeArn=AGENT_ARN,
                payload=json.dumps({"prompt": prompt}).encode(),
                runtimeSessionId=session_id,
                contentType="application/json",
                accept="application/json",
            )
            content_type = resp.get("contentType", "")

            if "text/event-stream" in content_type:
                buf = ""
                for line in resp["response"].iter_lines(chunk_size=1):
                    if not line:
                        continue
                    text = line.decode("utf-8") if isinstance(line, bytes) else line
                    parsed = _parse_chunk(text)
                    if not parsed:
                        continue

                    # Tool markers — send as separate events
                    if parsed.startswith("🔧") or parsed.startswith("📥") or "Result:" in parsed:
                        if buf:
                            yield f"data: {json.dumps({'type': 'text', 'content': _clean(buf)})}\n\n"
                            buf = ""
                        if parsed.startswith("🔧"):
                            name = parsed.replace("🔧", "").strip().split("\n")[0].strip("* ")
                            yield f"data: {json.dumps({'type': 'tool_call', 'name': name})}\n\n"
                        elif parsed.startswith("📥"):
                            inp = parsed.replace("📥", "").strip().lstrip(" Input:").strip("`")
                            yield f"data: {json.dumps({'type': 'tool_input', 'input': inp})}\n\n"
                        elif "Result:" in parsed:
                            is_error = parsed.startswith("❌")
                            result = parsed.split("Result:", 1)[-1].strip()
                            yield f"data: {json.dumps({'type': 'tool_result', 'result': result, 'isError': is_error})}\n\n"
                        continue

                    buf += parsed

                if buf:
                    yield f"data: {json.dumps({'type': 'text', 'content': _clean(buf)})}\n\n"
            else:
                raw = resp["response"].read()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                yield f"data: {json.dumps({'type': 'text', 'content': raw})}\n\n"

            yield "data: {\"type\": \"done\"}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(generate(), content_type="text/event-stream")


@app.route("/api/health")
def health():
    return {"status": "ok", "region": REGION, "agentArn": "set" if AGENT_ARN else "missing"}


if __name__ == "__main__":
    print(f"API server on http://0.0.0.0:3001 | REGION={REGION} | AGENT_ARN={'set' if AGENT_ARN else 'missing'}")
    app.run(host="0.0.0.0", port=3001)
