"""
FHIR Medical AI Agent — Chainlit Chat UI (AgentCore Runtime SSE Streaming)
Run: chainlit run app_v2.py --port 8501 --host 0.0.0.0
"""
import os
os.environ["OTEL_SDK_DISABLED"] = "true"

import json, time, re, uuid, boto3
import chainlit as cl
from pathlib import Path

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
AGENT_ARN = os.getenv("AGENT_ARN", "")
SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"

_client = None
def get_client():
    global _client
    if not _client:
        _client = boto3.client("bedrock-agentcore", region_name=REGION)
    return _client


# ── SSE Streaming ────────────────────────────────────────────
def _parse_chunk(chunk):
    try:
        if chunk.strip().startswith("{"):
            data = json.loads(chunk)
            for key in ["content", "response", "text"]:
                if key in data:
                    val = data[key]
                    if key == "content" and isinstance(val, list) and val:
                        item = val[0]
                        return item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    return str(val)
            return str(data)
    except json.JSONDecodeError:
        pass
    return chunk


def invoke_agent_streaming(prompt, session_id):
    resp = get_client().invoke_agent_runtime(
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
            if text.startswith("data: "):
                text = text[6:]
            parsed = _parse_chunk(text)
            if parsed.strip():
                yield parsed
    else:
        raw = resp["response"].read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            yield json.loads(raw).get("response", raw)
        except json.JSONDecodeError:
            yield raw


def clean_response(text):
    if not text:
        return text
    text = re.sub(r'"\s*"', "", text)
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ── Chainlit Handlers ────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    session_id = str(uuid.uuid4()) + "-" + "a" * 10
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("history", [])

    # Starter messages (scenario suggestions)
    if SCENARIOS_PATH.exists():
        scenarios = json.loads(SCENARIOS_PATH.read_text())
        starters = []
        for sc in scenarios[:4]:
            label = sc["label"]
            first_q = sc["questions"][0][1] if sc["questions"] else ""
            if first_q:
                starters.append(first_q)
        if starters:
            await cl.Message(
                content="안녕하세요! 🏥 **Medical AI Agent**입니다.\n\nFHIR 데이터 레이크 기반으로 환자 조회, 임상 분석, Text-to-SQL, PubMed 검색을 수행할 수 있습니다.\n\n아래 예시 질문을 참고하세요:\n"
                + "\n".join(f"- {s}" for s in starters)
            ).send()
    else:
        await cl.Message(content="안녕하세요! 🏥 **Medical AI Agent**입니다. 의료 데이터에 대해 질문하세요.").send()


@cl.on_message
async def on_message(message: cl.Message):
    if not AGENT_ARN:
        await cl.Message(content="⚠️ AGENT_ARN 환경변수가 설정되지 않았습니다.").send()
        return

    session_id = cl.user_session.get("session_id")
    history = cl.user_session.get("history", [])

    # Build prompt with history
    prompt = message.content
    if history:
        lines = []
        for m in history:
            role = "User" if m["role"] == "user" else "Assistant"
            content = m["content"][:500] if m["role"] == "assistant" else m["content"]
            lines.append(f"[{role}]: {content}")
        prompt = "<conversation_history>\n" + "\n".join(lines) + "\n</conversation_history>\n\n" + prompt

    history.append({"role": "user", "content": message.content})

    # Response message with streaming
    msg = cl.Message(content="")
    await msg.send()

    buf = ""
    current_step = None
    tool_start = None

    try:
        for chunk in invoke_agent_streaming(prompt, session_id):
            chunk_str = str(chunk)

            # Tool call start
            if chunk_str.startswith("🔧"):
                tool_name = chunk_str.replace("🔧", "").strip().split("\n")[0].strip("* ")
                tool_start = time.time()
                current_step = cl.Step(name=tool_name, type="tool")
                current_step.start = time.time()
                await current_step.send()
                continue

            # Tool input
            if chunk_str.startswith("📥"):
                if current_step:
                    inp = chunk_str.replace("📥", "").strip().lstrip(" Input:").strip("`")
                    current_step.input = inp
                    await current_step.update()
                continue

            # Tool result
            if "Result:" in chunk_str:
                if current_step:
                    elapsed = time.time() - tool_start if tool_start else 0
                    is_error = chunk_str.startswith("❌")
                    result_text = chunk_str.split("Result:", 1)[-1].strip()
                    current_step.output = result_text
                    current_step.end = time.time()
                    if is_error:
                        current_step.is_error = True
                    await current_step.update()
                    current_step = None
                    tool_start = None
                continue

            # Regular response text
            buf += chunk_str
            msg.content = clean_response(buf)
            await msg.update()

    except Exception as e:
        msg.content = f"❌ 오류: {str(e)}"
        await msg.update()

    history.append({"role": "assistant", "content": clean_response(buf)})
    cl.user_session.set("history", history)
