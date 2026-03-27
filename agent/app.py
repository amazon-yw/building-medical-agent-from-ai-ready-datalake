"""
Medical AI Agent — Streamlit Chat UI (AgentCore Runtime SSE Streaming)
Run: python3.12 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"

import streamlit as st
import json, time, re, uuid, boto3
from pathlib import Path

st.set_page_config(page_title="Medical AI Agent", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header { background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%); padding: 1.2rem 1.5rem; border-radius: 10px; margin-bottom: 1rem; color: white; }
    .main-header h1 { margin: 0; font-size: 1.5rem; }
    .main-header p { margin: 0.3rem 0 0 0; font-size: 0.85rem; opacity: 0.85; }
</style>
""", unsafe_allow_html=True)

# ── Configuration ────────────────────────────────────────────
REGION = os.getenv("AWS_REGION", "us-west-2")
AGENT_ARN = os.getenv("AGENT_ARN", "")
SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"


@st.cache_resource
def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


@st.cache_data
def load_scenarios():
    if SCENARIOS_PATH.exists():
        return json.loads(SCENARIOS_PATH.read_text())
    return []


# ── SSE Streaming ────────────────────────────────────────────
def _parse_chunk(chunk):
    """Extract text from a streaming chunk (plain text or JSON)."""
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


# Tool marker patterns for filtering
_TOOL_MARKERS = {"🔧", "📥"}
_RESULT_MARKER = "Result:"


def invoke_agent_streaming(prompt, session_id, show_tools=True, show_tool_result=True):
    """Invoke agent runtime and yield streaming text chunks."""
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
            if not parsed.strip():
                continue
            # Filter based on display settings
            if not show_tools and any(parsed.startswith(m) for m in _TOOL_MARKERS):
                continue
            if not show_tool_result and _RESULT_MARKER in parsed:
                continue
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
    """Clean up response text formatting."""
    if not text:
        return text
    text = re.sub(r'"\s*"', "", text)
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_prompt_with_history(prompt, messages):
    """Prepend conversation history to prompt for context continuity."""
    history = messages[:-1]  # exclude current message
    if not history:
        return prompt
    lines = []
    for m in history:
        role = "User" if m["role"] == "user" else "Assistant"
        content = m["content"][:500] if m["role"] == "assistant" else m["content"]
        lines.append(f"[{role}]: {content}")
    return "<conversation_history>\n" + "\n".join(lines) + "\n</conversation_history>\n\n" + prompt


# ── Session State ────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏥 Medical Agent")
    if AGENT_ARN:
        st.success("● Runtime 연결됨", icon="✅")
        with st.expander("Agent ARN"):
            st.code(AGENT_ARN[-60:])
    else:
        st.error("● AGENT_ARN 환경변수 필요")

    st.divider()
    st.markdown("### ⚙️ 표시 옵션")
    show_tools = st.checkbox("🔧 도구 호출 표시", value=True)
    show_tool_result = st.checkbox("📋 도구 응답 표시", value=True)

    st.divider()
    st.markdown("### 💡 예시 질문")
    for scenario in load_scenarios():
        with st.expander(scenario["label"]):
            for btn_label, q_text in scenario["questions"]:
                if st.button(btn_label, key=f"ex_{scenario['label']}_{btn_label}"):
                    st.session_state.pending_query = q_text

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10
            st.rerun()
    with col2:
        if st.button("🔄 새 세션", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10
            st.rerun()

# ── Main ─────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🏥 Medical AI Agent</h1>
    <p>메디컬 데이터 레이크 기반 의료 AI 에이전트 — AgentCore Runtime + Gateway MCP + S3 Tables</p>
</div>
""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

prompt = st.chat_input("의료 데이터에 대해 질문하세요...")
if "pending_query" in st.session_state:
    prompt = st.session_state.pop("pending_query")

# ── Process ──────────────────────────────────────────────────
if prompt and AGENT_ARN:
    st.session_state.messages.append({"role": "user", "content": prompt})
    full_prompt = build_prompt_with_history(prompt, st.session_state.messages)

    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        placeholder = st.empty()
        buf = ""

        try:
            for chunk in invoke_agent_streaming(full_prompt, st.session_state.session_id, show_tools, show_tool_result):
                buf += str(chunk)
                if len(buf) % 3 == 0 or chunk.endswith((" ", "\n")):
                    placeholder.markdown(clean_response(buf) + " ▌")
                    time.sleep(0.01)

            full_response = clean_response(buf)
            placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"❌ 오류: {str(e)}"
            placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

elif prompt and not AGENT_ARN:
    st.warning("⚠️ AGENT_ARN 환경변수를 설정하세요.")
