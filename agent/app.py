"""
FHIR Medical AI Agent — Streamlit Chat UI
Run: streamlit run app.py --server.port 8501 --server.address 0.0.0.0
"""
import os
os.environ["OTEL_SDK_DISABLED"] = "true"

import streamlit as st
import json, time, re, uuid, boto3
from pathlib import Path

st.set_page_config(page_title="Medical AI Agent", page_icon="⚕️", layout="centered", initial_sidebar_state="collapsed")

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
AGENT_ARN = os.getenv("AGENT_ARN", "")
SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"

# ── Styles ───────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
p, span, label, div, li, td, th, summary, button, a, code { color: #1a1a1a !important; }

/* Header — compact, mobile-friendly */
.med-hdr { background: linear-gradient(135deg,#0f2b46,#1a5276,#2980b9); padding:1rem 1.2rem; border-radius:10px; margin-bottom:0.8rem; display:flex; align-items:center; gap:0.8rem; box-shadow:0 3px 12px rgba(15,43,70,.25); }
.med-hdr * { color:#fff !important; }
.med-hdr-icon { font-size:2rem; }
.med-hdr h1 { margin:0; font-size:1.2rem; font-weight:700; }
.med-hdr p { margin:0.1rem 0 0; font-size:0.72rem; opacity:.8; }

/* Status pill */
.status-pill { display:inline-flex; align-items:center; gap:4px; background:#e8edf2; padding:3px 10px; border-radius:20px; font-size:0.7rem; margin-bottom:0.6rem; }
.status-pill * { color:#333 !important; }
.dot { width:7px; height:7px; border-radius:50%; display:inline-block; }
.dot.on { background:#38a169; } .dot.off { background:#e53e3e; }

/* Chat bubbles — Sendbird style */
.stChatMessage { border-radius:16px !important; margin-bottom:0.4rem !important; box-shadow:0 1px 3px rgba(0,0,0,.08) !important; }
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) { background:#e3f2fd !important; border-radius:16px 16px 4px 16px !important; }
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) { background:#f5f5f5 !important; border-radius:16px 16px 16px 4px !important; }

/* Tool steps */
.tstep { display:flex; align-items:center; gap:0.5rem; padding:0.35rem 0.7rem; margin:0.2rem 0; background:#e8edf2; border-left:3px solid #2980b9; border-radius:0 6px 6px 0; font-size:0.78rem; }
.tstep * { color:#1a1a1a !important; }
.tstep.ok { border-left-color:#38a169; } .tstep.err { border-left-color:#e53e3e; }
.tstep b { font-weight:600; } .tstep .tm { margin-left:auto; opacity:.6; font-size:.68rem; }

/* Sidebar */
section[data-testid="stSidebar"] { background:#f4f6f9; max-width:280px; }
section[data-testid="stSidebar"] * { color:#1a1a1a !important; }
section[data-testid="stSidebar"] button { background:#fff !important; border:1px solid #d0d5dd !important; color:#1a1a1a !important; }
section[data-testid="stSidebar"] button:hover { background:#f0f7ff !important; border-color:#2980b9 !important; }

/* Mobile responsive */
@media (max-width:768px) {
  .med-hdr { padding:0.7rem 0.8rem; gap:0.5rem; }
  .med-hdr-icon { font-size:1.5rem; }
  .med-hdr h1 { font-size:1rem; }
  .med-hdr p { font-size:0.65rem; }
  .stChatMessage { font-size:0.9rem !important; }
  section[data-testid="stSidebar"] { max-width:240px; }
  .tstep { font-size:0.72rem; padding:0.25rem 0.5rem; }
}
</style>""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────
@st.cache_resource
def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)

@st.cache_data
def load_scenarios():
    return json.loads(SCENARIOS_PATH.read_text()) if SCENARIOS_PATH.exists() else []

def _parse_chunk(chunk):
    try:
        if chunk.strip().startswith("{"):
            data = json.loads(chunk)
            for k in ("content", "response", "text"):
                if k in data:
                    v = data[k]
                    if k == "content" and isinstance(v, list) and v:
                        item = v[0]
                        return item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    return str(v)
            return str(data)
    except json.JSONDecodeError:
        pass
    return chunk

def invoke_agent_streaming(prompt, sid):
    resp = get_client().invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN, payload=json.dumps({"prompt": prompt}).encode(),
        runtimeSessionId=sid, contentType="application/json", accept="application/json")
    ct = resp.get("contentType", "")
    if "text/event-stream" in ct:
        for line in resp["response"].iter_lines(chunk_size=1):
            if not line: continue
            t = line.decode("utf-8") if isinstance(line, bytes) else line
            if t.startswith("data: "): t = t[6:]
            p = _parse_chunk(t)
            if p.strip(): yield p
    else:
        raw = resp["response"].read()
        if isinstance(raw, bytes): raw = raw.decode("utf-8")
        try: yield json.loads(raw).get("response", raw)
        except json.JSONDecodeError: yield raw

def clean(text):
    if not text: return text
    text = re.sub(r'"\s*"', "", text).replace("\\n", "\n").replace("\\t", "\t")
    return re.sub(r"\n{3,}", "\n\n", text).strip()

def with_history(prompt, msgs):
    h = msgs[:-1]
    if not h: return prompt
    lines = [f"[{'User' if m['role']=='user' else 'Assistant'}]: {m['content'][:500]}" for m in h]
    return "<conversation_history>\n" + "\n".join(lines) + "\n</conversation_history>\n\n" + prompt


# ── State ────────────────────────────────────────────────────
if "messages" not in st.session_state: st.session_state.messages = []
if "session_id" not in st.session_state: st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10

# ── Header ───────────────────────────────────────────────────
st.markdown("""<div class="med-hdr"><div class="med-hdr-icon">⚕️</div><div>
<h1>Medical AI Agent</h1><p>FHIR Data Lake · 환자 조회 · 임상 분석 · Text-to-SQL · PubMed</p>
</div></div>""", unsafe_allow_html=True)

ok = bool(AGENT_ARN)
st.markdown(f'<div class="status-pill"><span class="dot {"on" if ok else "off"}"></span>{"연결됨" if ok else "AGENT_ARN 미설정"} · {REGION}</div>', unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚕️ 데모 시나리오")
    for i, sc in enumerate(load_scenarios()):
        with st.expander(sc["label"], expanded=False):
            for bl, qt in sc["questions"]:
                if st.button(bl, key=f"s{i}_{bl}", use_container_width=True):
                    st.session_state.pending_query = qt
    st.markdown("---")
    show_tools = st.toggle("🔧 도구 호출 표시", value=True)
    show_result = st.toggle("📋 도구 결과 표시", value=True)
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.messages = []; st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10; st.rerun()
    with c2:
        if st.button("🔄 새 세션", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4()) + "-" + "a" * 10; st.rerun()

# ── Chat ─────────────────────────────────────────────────────
for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="👤" if m["role"] == "user" else "⚕️"):
        st.markdown(m["content"])

prompt = st.chat_input("의료 데이터에 대해 질문하세요...")
if "pending_query" in st.session_state: prompt = st.session_state.pop("pending_query")

if prompt and AGENT_ARN:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="⚕️"):
        tc = st.container()
        rp = st.empty()
        buf = ""
        t0 = None
        try:
            for chunk in invoke_agent_streaming(with_history(prompt, st.session_state.messages), st.session_state.session_id):
                s = str(chunk)
                if s.startswith("🔧"):
                    name = s.replace("🔧", "").strip().split("\n")[0].strip("* ")
                    t0 = time.time()
                    if show_tools:
                        with tc: st.markdown(f'<div class="tstep"><span>⏳</span><b>{name}</b><span class="tm">실행 중...</span></div>', unsafe_allow_html=True)
                    continue
                if s.startswith("📥") and show_tools:
                    with tc: st.code(s.replace("📥", "").strip().lstrip(" Input:").strip("`"), language="json")
                    continue
                if "Result:" in s:
                    el = f"{time.time()-t0:.1f}s" if t0 else ""
                    err = s.startswith("❌")
                    if show_result:
                        with tc:
                            cls = "err" if err else "ok"
                            ico = "❌" if err else "✅"
                            rt = s.split("Result:",1)[-1].strip()
                            st.markdown(f'<div class="tstep {cls}"><span>{ico}</span><span>{rt}</span><span class="tm">{el}</span></div>', unsafe_allow_html=True)
                    t0 = None; continue
                buf += s
                if len(buf) % 3 == 0 or s.endswith((" ", "\n")):
                    rp.markdown(clean(buf) + " ▌"); time.sleep(0.01)
            rp.markdown(clean(buf))
        except Exception as e:
            buf = f"❌ 오류: {e}"; rp.markdown(buf)
        st.session_state.messages.append({"role": "assistant", "content": clean(buf)})
elif prompt and not AGENT_ARN:
    st.warning("⚠️ AGENT_ARN 환경변수를 설정하세요.")
