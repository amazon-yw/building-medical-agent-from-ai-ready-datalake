"""Proxy server for AgentCore Runtime"""
import os, json, re, boto3
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
AGENT_ARN = os.getenv("AGENT_ARN", "")


def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


def _parse_chunk(text):
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


def _send(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    prompt = data.get("prompt", "")
    session_id = data.get("sessionId", "default")

    if not AGENT_ARN:
        return Response(_send({"type": "error", "content": "AGENT_ARN not set"}), content_type="text/event-stream")

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
                for line in resp["response"].iter_lines(chunk_size=1):
                    if not line:
                        continue
                    text = line.decode("utf-8") if isinstance(line, bytes) else line
                    parsed = _parse_chunk(text)
                    if not parsed:
                        continue

                    if parsed.startswith("🔧"):
                        name = parsed.replace("🔧", "").strip().split("\n")[0].strip("* ")
                        yield _send({"type": "tool_call", "name": name})
                    elif parsed.startswith("📥"):
                        inp = parsed.replace("📥", "").strip().lstrip(" Input:").strip("`")
                        yield _send({"type": "tool_input", "input": inp})
                    elif "Result:" in parsed:
                        is_error = parsed.startswith("❌")
                        result = parsed.split("Result:", 1)[-1].strip()
                        yield _send({"type": "tool_result", "result": result, "isError": is_error})
                    else:
                        # Send each text chunk individually for streaming
                        yield _send({"type": "text", "content": parsed})
            else:
                raw = resp["response"].read()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                yield _send({"type": "text", "content": raw})

            yield _send({"type": "done"})
        except Exception as e:
            yield _send({"type": "error", "content": str(e)})

    return Response(generate(), content_type="text/event-stream")


@app.route("/api/health")
def health():
    return {"status": "ok", "region": REGION, "agentArn": "set" if AGENT_ARN else "missing"}


if __name__ == "__main__":
    print(f"API server on http://0.0.0.0:3001 | REGION={REGION} | AGENT_ARN={'set' if AGENT_ARN else 'missing'}")
    app.run(host="0.0.0.0", port=3001)
