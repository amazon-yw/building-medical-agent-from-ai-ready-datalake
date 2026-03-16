"""
FHIR Medical AI Agent — Streamlit Chat UI (AgentCore Runtime SSE Streaming)
Run: python3.12 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"

import streamlit as st
import json, time, re, uuid, boto3

st.set_page_config(page_title="FHIR Medical AI Agent", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

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

@st.cache_resource
def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


def invoke_agent_streaming(prompt, agent_arn, session_id, show_tools=True, show_tool_result=True):
    """Invoke agent and yield streaming chunks with tool trace markers."""
    client = get_client()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        payload=json.dumps({"prompt": prompt}).encode(),
        runtimeSessionId=session_id,
        contentType="application/json",
        accept="application/json",
    )

    content_type = resp.get("contentType", "")

    if "text/event-stream" in content_type:
        for line in resp["response"].iter_lines(chunk_size=1):
            if line:
                text = line.decode("utf-8") if isinstance(line, bytes) else line
                if text.startswith("data: "):
                    text = text[6:]
                parsed = _parse_chunk(text)
                if parsed.strip():
                    # Filter tool markers based on settings
                    if "🔧 Using tool:" in parsed and not show_tools:
                        continue
                    if "📥 Input:" in parsed and not show_tools:
                        continue
                    if "Tool result:" in parsed and not show_tool_result:
                        continue
                    yield parsed
    else:
        # Non-streaming fallback
        raw = resp["response"].read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            body = json.loads(raw)
            yield body.get("response", str(body))
        except json.JSONDecodeError:
            yield raw


def _parse_chunk(chunk):
    """Parse a streaming chunk, extract text from JSON if needed."""
    try:
        if chunk.strip().startswith("{"):
            data = json.loads(chunk)
            if "role" in data and "content" in data:
                content = data["content"]
                if isinstance(content, list) and content:
                    if isinstance(content[0], dict) and "text" in content[0]:
                        return content[0]["text"]
                    return str(content[0])
                return str(content)
            if "response" in data:
                return str(data["response"])
            if "text" in data:
                return str(data["text"])
            return str(data)
        return chunk
    except json.JSONDecodeError:
        return chunk


def clean_response(text):
    """Clean up response text formatting."""
    if not text:
        return text
    text = re.sub(r'"\s*"', "", text)
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Session State ────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏥 FHIR Medical Agent")
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
    examples = {
        "📋 테이블 목록": "데이터 레이크에 어떤 테이블들이 있는지 알려줘",
        "🔍 당뇨 환자 검색": "당뇨병(diabetes) 환자를 검색해줘",
        "👤 환자 요약": "환자 한 명을 검색해서 종합 요약 정보를 보여줘",
        "💊 처방 이력": "아무 환자 한 명의 처방 이력을 조회해줘",
        "📊 인구 건강 분석": "60-69세 연령대의 당뇨병 환자 인구 건강 지표를 분석해줘",
        "🩺 케어 갭 탐지": "환자 한 명을 찾아서 케어 갭을 분석해줘",
        "📈 커스텀 쿼리": "condition 테이블에서 가장 많은 진단명 상위 10개를 조회해줘",
    }
    for label, q_text in examples.items():
        if st.button(label, key=f"ex_{label}"):
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
    <h1>🏥 FHIR Medical AI Agent</h1>
    <p>FHIR 데이터 레이크 기반 의료 AI 에이전트 — AgentCore Runtime + Gateway MCP + S3 Tables</p>
</div>
""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    avatar = "🧑‍⚕️" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

if "pending_query" in st.session_state:
    prompt = st.session_state.pop("pending_query")
else:
    prompt = st.chat_input("의료 데이터에 대해 질문하세요...")

# ── Process ──────────────────────────────────────────────────
if prompt and AGENT_ARN:
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Build prompt with conversation history for context continuity
    history = st.session_state.messages[:-1]  # exclude current message
    if history:
        hist_lines = []
        for m in history:
            role = "User" if m["role"] == "user" else "Assistant"
            # Truncate long assistant responses to keep prompt manageable
            content = m["content"][:500] if m["role"] == "assistant" else m["content"]
            hist_lines.append(f"[{role}]: {content}")
        full_prompt = "<conversation_history>\n" + "\n".join(hist_lines) + "\n</conversation_history>\n\n" + prompt
    else:
        full_prompt = prompt
    with st.chat_message("user", avatar="🧑‍⚕️"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        chunk_buffer = ""

        try:
            for chunk in invoke_agent_streaming(
                full_prompt, AGENT_ARN, st.session_state.session_id,
                show_tools, show_tool_result,
            ):
                if not isinstance(chunk, str):
                    chunk = str(chunk)
                chunk_buffer += chunk
                # Update display periodically
                if len(chunk_buffer) % 3 == 0 or chunk.endswith((" ", "\n")):
                    message_placeholder.markdown(clean_response(chunk_buffer) + " ▌")
                    time.sleep(0.01)

            full_response = clean_response(chunk_buffer)
            message_placeholder.markdown(full_response)

        except Exception as e:
            full_response = f"❌ 오류: {str(e)}"
            message_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

elif prompt and not AGENT_ARN:
    st.warning("⚠️ AGENT_ARN 환경변수를 설정하세요.")
