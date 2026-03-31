"""
FHIR Medical AI Agent — Streamlit Chat UI (AgentCore Runtime SSE Streaming)
Run: streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"

import streamlit as st
import json, time, re, uuid, boto3
from pathlib import Path

st.set_page_config(page_title="Medical AI Agent", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

# ── Styles ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Global */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Header */
.med-header {
    background: linear-gradient(135deg, #0f2b46 0%, #1a5276 50%, #2980b9 100%);
    padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.2rem;
    color: white; display: flex; align-items: center; gap: 1.2rem;
    box-shadow: 0 4px 15px rgba(15,43,70,0.3);
}
.med-header-icon { font-size: 2.8rem; }
.med-header h1 { margin: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }
.med-header p { margin: 0.2rem 0 0 0; font-size: 0.82rem; opacity: 0.8; font-weight: 400; }

/* Status bar */
.status-bar {
    display: flex; gap: 1.5rem; padding: 0.6rem 1rem;
    background: #f0f4f8; border-radius: 8px; margin-bottom: 1rem;
    font-size: 0.78rem; color: #4a5568; align-items: center;
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 5px; }
.status-dot.on { background: #38a169; }
.status-dot.off { background: #e53e3e; }

/* Scenario cards */
.scenario-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.8rem; }
.scenario-card {
    background: linear-gradient(135deg, #f7fafc, #edf2f7); border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 0.7rem 0.8rem; cursor: pointer; transition: all 0.2s;
    font-size: 0.78rem; text-align: center;
}
.scenario-card:hover { border-color: #2980b9; background: linear-gradient(135deg, #ebf8ff, #dbeafe); transform: translateY(-1px); }
.scenario-icon { font-size: 1.4rem; display: block; margin-bottom: 0.3rem; }
.scenario-label { font-weight: 600; color: #2d3748; font-size: 0.72rem; }

/* Tool timeline */
.tool-step {
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.4rem 0.8rem; margin: 0.3rem 0;
    background: #edf2f7; border-left: 3px solid #2980b9;
    border-radius: 0 6px 6px 0; font-size: 0.8rem;
    color: #2d3748;
}
.tool-step.done { border-left-color: #38a169; }
.tool-step.error { border-left-color: #e53e3e; }
.tool-step-name { font-weight: 600; color: #1a202c; }
.tool-step-time { color: #718096; font-size: 0.7rem; margin-left: auto; }

/* Chat */
.stChatMessage { border-radius: 10px !important; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #f0f4f8; }
section[data-testid="stSidebar"] * { color: #1a202c !important; }
section[data-testid="stSidebar"] .stMarkdown h3 { color: #1a5276 !important; font-size: 0.95rem; }
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stMarkdown label { color: #2d3748 !important; }
section[data-testid="stSidebar"] button { color: #2d3748 !important; }
section[data-testid="stSidebar"] .stExpander summary span { color: #1a202c !important; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ── Configuration ────────────────────────────────────────────
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
AGENT_ARN = os.getenv("AGENT_ARN", "")
SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"

SCENARIO_ICONS = {"1": "🩺", "2": "🏥", "3": "💉", "4": "💰", "5": "📊", "6": "📚"}


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
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_prompt_with_history(prompt, messages):
    history = messages[:-1]
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
if "tool_steps" not in st.session_state:
    st.session_state.tool_steps = []

# ── Header (안 4) ────────────────────────────────────────────
st.markdown("""
<div class="med-header">
    <div class="med-header-icon">⚕️</div>
    <div>
        <h1>Medical AI Agent</h1>
        <p>FHIR Data Lake 기반 의료 AI 에이전트 — 환자 조회 · 임상 분석 · Text-to-SQL · PubMed 검색</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Status bar (안 4)
connected = bool(AGENT_ARN)
dot_class = "on" if connected else "off"
status_text = "Runtime 연결됨" if connected else "AGENT_ARN 미설정"
st.markdown(f"""
<div class="status-bar">
    <span><span class="status-dot {dot_class}"></span> {status_text}</span>
    <span>🌐 {REGION}</span>
    <span>💬 대화 {len(st.session_state.messages) // 2}회</span>
    <span>🔑 세션 ...{st.session_state.session_id[-8:]}</span>
</div>
""", unsafe_allow_html=True)

# ── Sidebar (안 2 — 카드형 시나리오) ─────────────────────────
with st.sidebar:
    st.markdown("### ⚕️ Medical AI Agent")
    st.caption("FHIR 데이터 레이크 기반 의료 AI")

    st.markdown("---")
    st.markdown("### 💡 데모 시나리오")

    scenarios = load_scenarios()
    for i, scenario in enumerate(scenarios):
        icon = SCENARIO_ICONS.get(str(i + 1), "📋")
        label = scenario["label"].split(":", 1)[-1].strip() if ":" in scenario["label"] else scenario["label"]

        with st.expander(f"{icon} {label}", expanded=False):
            for btn_label, q_text in scenario["questions"]:
                if st.button(f"  {btn_label}", key=f"s{i}_{btn_label}", use_container_width=True):
                    st.session_state.pending_query = q_text

    st.markdown("---")
    st.markdown("### ⚙️ 설정")

    show_tools = st.toggle("🔧 도구 호출 표시", value=True)
    show_tool_result = st.toggle("📋 도구 결과 표시", value=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.messages = []
            st.session_state.tool_steps = []
            st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10
            st.rerun()
    with col2:
        if st.button("🔄 새 세션", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10
            st.rerun()

# ── Chat History ─────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "⚕️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Input ────────────────────────────────────────────────────
prompt = st.chat_input("의료 데이터에 대해 질문하세요...")
if "pending_query" in st.session_state:
    prompt = st.session_state.pop("pending_query")

# ── Process (안 1 + 안 3 — expander + timeline) ─────────────
if prompt and AGENT_ARN:
    st.session_state.messages.append({"role": "user", "content": prompt})
    full_prompt = build_prompt_with_history(prompt, st.session_state.messages)

    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="⚕️"):
        # Tool timeline container
        tool_container = st.container()
        response_placeholder = st.empty()

        buf = ""
        tool_steps = []
        current_tool_start = None

        try:
            for chunk in invoke_agent_streaming(full_prompt, st.session_state.session_id):
                chunk_str = str(chunk)

                # Detect tool call markers
                if chunk_str.startswith("🔧"):
                    tool_name = chunk_str.replace("🔧", "").strip().split("\n")[0].strip("* ")
                    current_tool_start = time.time()
                    tool_steps.append({"name": tool_name, "status": "running", "time": None, "input": "", "result": ""})

                    if show_tools:
                        with tool_container:
                            step_num = len(tool_steps)
                            st.markdown(f"""<div class="tool-step">
                                <span>⏳</span>
                                <span class="tool-step-name">Step {step_num}: {tool_name}</span>
                                <span class="tool-step-time">실행 중...</span>
                            </div>""", unsafe_allow_html=True)
                    continue

                if chunk_str.startswith("📥") and show_tools:
                    if tool_steps:
                        tool_steps[-1]["input"] = chunk_str.replace("📥", "").strip()
                        with tool_container:
                            inp = tool_steps[-1]["input"].strip("` Input:")
                            st.code(inp, language="json")
                    continue

                if "Result:" in chunk_str:
                    elapsed = f"{time.time() - current_tool_start:.1f}s" if current_tool_start else ""
                    is_error = chunk_str.startswith("❌")
                    if tool_steps:
                        tool_steps[-1]["status"] = "error" if is_error else "done"
                        tool_steps[-1]["time"] = elapsed
                        tool_steps[-1]["result"] = chunk_str

                    if show_tool_result:
                        with tool_container:
                            status_icon = "❌" if is_error else "✅"
                            css_class = "error" if is_error else "done"
                            result_text = chunk_str.split("Result:", 1)[-1].strip()
                            st.markdown(f"""<div class="tool-step {css_class}">
                                <span>{status_icon}</span>
                                <span>{result_text}</span>
                                <span class="tool-step-time">{elapsed}</span>
                            </div>""", unsafe_allow_html=True)
                    current_tool_start = None
                    continue

                # Regular response text
                buf += chunk_str
                if len(buf) % 3 == 0 or chunk_str.endswith((" ", "\n")):
                    response_placeholder.markdown(clean_response(buf) + " ▌")
                    time.sleep(0.01)

            full_response = clean_response(buf)
            response_placeholder.markdown(full_response)

        except Exception as e:
            full_response = f"❌ 오류: {str(e)}"
            response_placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.session_state.tool_steps = tool_steps

elif prompt and not AGENT_ARN:
    st.warning("⚠️ AGENT_ARN 환경변수를 설정하세요.")
