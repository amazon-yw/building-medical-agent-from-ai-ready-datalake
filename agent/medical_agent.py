"""
FHIR Medical Data Agent — AgentCore Runtime + Gateway MCP
"""

import os, json, logging, time
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Configuration ────────────────────────────────────────────
REGION = os.getenv("AWS_REGION", "us-west-2")
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-6")
GATEWAY_MCP_URL = os.getenv("GATEWAY_MCP_URL", "")
GATEWAY_CLIENT_ID = os.getenv("GATEWAY_CLIENT_ID", "")
GATEWAY_CLIENT_SECRET = os.getenv("GATEWAY_CLIENT_SECRET", "")
GATEWAY_TOKEN_URL = os.getenv("GATEWAY_TOKEN_URL", "")
GATEWAY_SCOPE = os.getenv("GATEWAY_SCOPE", "fhir-mcp/tools")
GATEWAY_TOOL_PREFIX = os.getenv("GATEWAY_TOOL_PREFIX", "FhirMcpLambdaTarget___")

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text() \
    if (Path(__file__).parent / "system_prompt.md").exists() \
    else "You are a helpful medical data assistant."

app = BedrockAgentCoreApp()


# ── OAuth Token Manager ──────────────────────────────────────
class TokenManager:
    """OAuth2 client_credentials token with auto-refresh."""
    def __init__(self):
        self._token = None
        self._expires_at = 0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at:
            return self._token
        import httpx
        resp = httpx.post(
            GATEWAY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": GATEWAY_CLIENT_ID,
                "client_secret": GATEWAY_CLIENT_SECRET,
                "scope": GATEWAY_SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600) - 60
        return self._token

_token_mgr = TokenManager()


# ── Gateway MCP Tool Caller ──────────────────────────────────
def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    import httpx
    resp = httpx.post(
        GATEWAY_MCP_URL,
        headers={
            "Authorization": f"Bearer {_token_mgr.get_token()}",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": f"{GATEWAY_TOOL_PREFIX}{tool_name}", "arguments": arguments},
        },
        timeout=300,
    )
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        return {"error": result["error"]}
    return result.get("result", result)


# ── Tool Definitions (metadata-driven) ───────────────────────
TOOL_DEFS = [
    {"name": "list_tables",
     "doc": "List available FHIR data lake tables. Optional domain filter: administrative, clinical, financial, medication, security.",
     "params": {"domain": ""}},
    {"name": "get_table_schema",
     "doc": "Get detailed table schema with column names, types, code mappings, and query hints.",
     "params": {"table_name": None}},
    {"name": "get_table_relationships",
     "doc": "Get table relationships and JOIN hints.",
     "params": {"table_name": ""}},
    {"name": "get_patient_summary",
     "doc": "Get comprehensive patient summary including demographics, conditions, allergies, medications.",
     "params": {"patient_id": None}},
    {"name": "search_patients",
     "doc": "Search patients by name, gender, birth date range, or condition keyword.",
     "params": {"name": "", "gender": "", "birth_date_from": "", "birth_date_to": "", "condition_code": ""}},
    {"name": "get_encounter_history",
     "doc": "Get patient encounter history.",
     "params": {"patient_id": None, "date_from": "", "date_to": "", "class_code": ""}},
    {"name": "get_clinical_observations",
     "doc": "Get clinical observations (vitals, lab results) for a patient.",
     "params": {"patient_id": None, "observation_code": "", "date_from": "", "date_to": ""}},
    {"name": "get_medications",
     "doc": "Get medication requests for a patient.",
     "params": {"patient_id": None, "active_only": False}},
    {"name": "get_diagnosis_history",
     "doc": "Get diagnosis/condition history for a patient.",
     "params": {"patient_id": None, "category": ""}},
    {"name": "get_claim_summary",
     "doc": "Get claim and explanation of benefit summary.",
     "params": {"patient_id": "", "date_from": "", "date_to": "", "status": ""}},
    {"name": "detect_care_gaps",
     "doc": "Detect care gaps: missing immunizations, overdue screenings, incomplete care plans.",
     "params": {"patient_id": None}},
    {"name": "get_population_health_metrics",
     "doc": "Get population health metrics aggregated by condition, age group, gender.",
     "params": {"condition_code": "", "age_group": ""}},
    {"name": "run_custom_query",
     "doc": "Execute a read-only Spark SQL query. Only SELECT allowed. Use list_tables and get_table_schema first.",
     "params": {"query": None}},
    {"name": "search_pubmed",
     "doc": "Search PubMed for research articles. Returns title, abstract, journal, authors, and URL.",
     "params": {"query": None, "max_results": 5}},
    {"name": "get_pubmed_article",
     "doc": "Fetch a specific PubMed article by PMID with full abstract.",
     "params": {"pmid": None}},
]

_tools = None

def _get_tools():
    """Dynamically generate Strands @tool wrappers from TOOL_DEFS."""
    global _tools
    if _tools:
        return _tools

    from strands import tool

    def _make_tool(defn):
        param_names = list(defn["params"].keys())
        defaults = defn["params"]

        def fn(**kwargs):
            args = {k: v for k, v in kwargs.items() if k in param_names and v != defaults[k]}
            return json.dumps(call_mcp_tool(defn["name"], args), default=str)

        fn.__name__ = defn["name"]
        fn.__doc__ = defn["doc"]

        # Build signature with proper type annotations for Strands
        import inspect
        params = []
        for pname, pdefault in defaults.items():
            ann = type(pdefault) if pdefault is not None else str
            params.append(inspect.Parameter(
                pname, inspect.Parameter.KEYWORD_ONLY, default=pdefault if pdefault is not None else "", annotation=ann,
            ))
        fn.__signature__ = inspect.Signature(params)
        fn.__annotations__ = {p: (type(d) if d is not None else str) for p, d in defaults.items()}

        return tool(fn)

    _tools = [_make_tool(d) for d in TOOL_DEFS]
    return _tools


# ── Tool Result Summarizer ───────────────────────────────────
def _unwrap_json(s):
    """Recursively unwrap nested MCP Gateway → Lambda JSON layers."""
    try:
        d = json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return s
    if isinstance(d, dict):
        if "content" in d and "isError" in d:
            for c in d.get("content", []):
                if isinstance(c, dict) and "text" in c:
                    return _unwrap_json(c["text"])
        if "result" in d and "status" in d:
            return _unwrap_json(d["result"])
    return d


def _summarize_tool_result(result_content):
    """Parse nested JSON tool result and return a readable summary."""
    raw = ""
    if isinstance(result_content, list):
        for rc in result_content:
            if isinstance(rc, dict) and "text" in rc:
                raw = rc["text"]
                break
    if not raw:
        return "(빈 응답)"

    inner = _unwrap_json(raw)

    if isinstance(inner, dict):
        for key, label in [("tables", "테이블"), ("patients", "환자"), ("rows", "행"), ("columns", "컬럼")]:
            if key in inner:
                items = inner[key]
                count = f"{len(items)}개 {label}"
                if key == "tables":
                    count += ": " + ", ".join(x.get("table", "") for x in items[:5])
                elif key == "columns":
                    return f"스키마 ({count})"
                return count
        if "error" in inner:
            return f"오류: {str(inner['error'])[:150]}"
        return f"키: {', '.join(list(inner.keys())[:6])}"
    if isinstance(inner, list):
        return f"{len(inner)}개 항목"
    return str(inner)[:200]


# ── Entrypoint ───────────────────────────────────────────────
@app.entrypoint
async def invoke(payload, context):
    from strands import Agent

    agent = Agent(model=MODEL_ID, system_prompt=SYSTEM_PROMPT, tools=_get_tools())
    prompt = payload.get("prompt", "안녕하세요")
    emitted_tool_ids = set()

    try:
        async for event in agent.stream_async(prompt):
            if "message" in event and "content" in event["message"]:
                for obj in event["message"]["content"]:
                    if "toolUse" in obj:
                        tu = obj["toolUse"]
                        tid = tu.get("toolUseId", "")
                        if tid not in emitted_tool_ids:
                            emitted_tool_ids.add(tid)
                            name = tu.get("name", "unknown")
                            inp_str = json.dumps(tu.get("input", {}), ensure_ascii=False)[:300]
                            yield f"\n\n🔧 **{name}**\n📥 Input: `{inp_str}`\n"
                    if "toolResult" in obj:
                        tr = obj["toolResult"]
                        status = "✅" if tr.get("status") != "error" else "❌"
                        yield f"\n{status} Result: {_summarize_tool_result(tr.get('content', []))}\n\n"
            if "data" in event:
                yield event["data"]
    except Exception as e:
        yield f"\n\n❌ Error: {str(e)}"


if __name__ == "__main__":
    app.run()
