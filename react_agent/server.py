"""Express-like proxy server for AgentCore Runtime (Python + Flask)"""
import os, json, boto3
from flask import Flask, request, Response

app = Flask(__name__)

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
AGENT_ARN = os.getenv("AGENT_ARN", "")


def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    prompt = data.get("prompt", "")
    session_id = data.get("sessionId", "default")

    if not AGENT_ARN:
        return Response("data: {\"error\": \"AGENT_ARN not set\"}\n\n", content_type="text/event-stream")

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
                    yield f"data: {text}\n\n"
            else:
                raw = resp["response"].read()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                yield f"data: {raw}\n\n"
        except Exception as e:
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

    return Response(generate(), content_type="text/event-stream")


@app.route("/api/health")
def health():
    return {"status": "ok", "region": REGION, "agentArn": "set" if AGENT_ARN else "missing"}


if __name__ == "__main__":
    print(f"API server running on http://0.0.0.0:3001")
    print(f"AGENT_ARN: {AGENT_ARN or '(not set)'}")
    print(f"REGION: {REGION}")
    app.run(host="0.0.0.0", port=3001)
