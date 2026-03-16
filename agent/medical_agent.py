"""
FHIR Medical Data Agent — AgentCore Runtime + Memory + Gateway MCP
"""

import os, json, logging
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Configuration ────────────────────────────────────────────
REGION = os.getenv("AWS_REGION", "us-west-2")
MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-6")

GATEWAY_MCP_URL = os.getenv("GATEWAY_MCP_URL", "")
GATEWAY_CLIENT_ID = os.getenv("GATEWAY_CLIENT_ID", "")
GATEWAY_CLIENT_SECRET = os.getenv("GATEWAY_CLIENT_SECRET", "")
GATEWAY_TOKEN_URL = os.getenv("GATEWAY_TOKEN_URL", "")
GATEWAY_SCOPE = os.getenv("GATEWAY_SCOPE", "fhir-mcp/tools")

_prompt_path = Path(__file__).parent / "system_prompt.md"
SYSTEM_PROMPT = _prompt_path.read_text() if _prompt_path.exists() else "You are a helpful medical data assistant."

app = BedrockAgentCoreApp()

# ── OAuth Token Manager ──────────────────────────────────────
_token_cache = None

def _get_token():
    global _token_cache
    if _token_cache:
        return _token_cache
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
    _token_cache = resp.json()["access_token"]
    return _token_cache


# ── Gateway MCP Tool Caller ──────────────────────────────────
GATEWAY_TOOL_PREFIX = os.getenv("GATEWAY_TOOL_PREFIX", "FhirMcpLambdaTarget___")

def call_mcp_tool_sync(tool_name: str, arguments: dict) -> dict:
    import httpx
    token = _get_token()
    full_name = f"{GATEWAY_TOOL_PREFIX}{tool_name}"
    resp = httpx.post(
        GATEWAY_MCP_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": full_name, "arguments": arguments},
        },
        timeout=300,
    )
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        return {"error": result["error"]}
    return result.get("result", result)


# ── Strands Tool wrappers ────────────────────────────────────
# Lazy import: strands @tool loaded only at first invocation
_tools = None

def _get_tools():
    global _tools
    if _tools:
        return _tools

    from strands import tool

    @tool
    def list_tables(domain: str = "") -> str:
        """List available FHIR data lake tables. Optional domain filter: administrative, clinical, financial, medication, security."""
        args = {"domain": domain} if domain else {}
        return json.dumps(call_mcp_tool_sync("list_tables", args), default=str)

    @tool
    def get_table_schema(table_name: str) -> str:
        """Get detailed table schema with column names, types, code mappings, and query hints."""
        return json.dumps(call_mcp_tool_sync("get_table_schema", {"table_name": table_name}), default=str)

    @tool
    def get_table_relationships(table_name: str = "") -> str:
        """Get table relationships and JOIN hints."""
        args = {"table_name": table_name} if table_name else {}
        return json.dumps(call_mcp_tool_sync("get_table_relationships", args), default=str)

    @tool
    def get_patient_summary(patient_id: str) -> str:
        """Get comprehensive patient summary including demographics, conditions, allergies, medications."""
        return json.dumps(call_mcp_tool_sync("get_patient_summary", {"patient_id": patient_id}), default=str)

    @tool
    def search_patients(name: str = "", gender: str = "", birth_date_from: str = "", birth_date_to: str = "", condition_code: str = "") -> str:
        """Search patients by name, gender, birth date range, or condition keyword."""
        args = {k: v for k, v in {"name": name, "gender": gender, "birth_date_from": birth_date_from, "birth_date_to": birth_date_to, "condition_code": condition_code}.items() if v}
        return json.dumps(call_mcp_tool_sync("search_patients", args), default=str)

    @tool
    def get_encounter_history(patient_id: str, date_from: str = "", date_to: str = "", class_code: str = "") -> str:
        """Get patient encounter history."""
        args = {"patient_id": patient_id}
        if date_from: args["date_from"] = date_from
        if date_to: args["date_to"] = date_to
        if class_code: args["class_code"] = class_code
        return json.dumps(call_mcp_tool_sync("get_encounter_history", args), default=str)

    @tool
    def get_clinical_observations(patient_id: str, observation_code: str = "", date_from: str = "", date_to: str = "") -> str:
        """Get clinical observations (vitals, lab results) for a patient."""
        args = {"patient_id": patient_id}
        if observation_code: args["observation_code"] = observation_code
        if date_from: args["date_from"] = date_from
        if date_to: args["date_to"] = date_to
        return json.dumps(call_mcp_tool_sync("get_clinical_observations", args), default=str)

    @tool
    def get_medications(patient_id: str, active_only: bool = False) -> str:
        """Get medication requests for a patient."""
        args = {"patient_id": patient_id}
        if active_only: args["active_only"] = True
        return json.dumps(call_mcp_tool_sync("get_medications", args), default=str)

    @tool
    def get_diagnosis_history(patient_id: str, category: str = "") -> str:
        """Get diagnosis/condition history for a patient."""
        args = {"patient_id": patient_id}
        if category: args["category"] = category
        return json.dumps(call_mcp_tool_sync("get_diagnosis_history", args), default=str)

    @tool
    def get_claim_summary(patient_id: str = "", date_from: str = "", date_to: str = "", status: str = "") -> str:
        """Get claim and explanation of benefit summary."""
        args = {k: v for k, v in {"patient_id": patient_id, "date_from": date_from, "date_to": date_to, "status": status}.items() if v}
        return json.dumps(call_mcp_tool_sync("get_claim_summary", args), default=str)

    @tool
    def detect_care_gaps(patient_id: str) -> str:
        """Detect care gaps: missing immunizations, overdue screenings, incomplete care plans."""
        return json.dumps(call_mcp_tool_sync("detect_care_gaps", {"patient_id": patient_id}), default=str)

    @tool
    def get_population_health_metrics(condition_code: str = "", age_group: str = "") -> str:
        """Get population health metrics aggregated by condition, age group, gender."""
        args = {k: v for k, v in {"condition_code": condition_code, "age_group": age_group}.items() if v}
        return json.dumps(call_mcp_tool_sync("get_population_health_metrics", args), default=str)

    @tool
    def run_custom_query(query: str) -> str:
        """Execute a read-only Spark SQL query. Only SELECT allowed. Use list_tables and get_table_schema first."""
        return json.dumps(call_mcp_tool_sync("run_custom_query", {"query": query}), default=str)

    _tools = [
        list_tables, get_table_schema, get_table_relationships,
        get_patient_summary, search_patients,
        get_encounter_history, get_clinical_observations, get_medications, get_diagnosis_history,
        get_claim_summary,
        detect_care_gaps, get_population_health_metrics,
        run_custom_query,
    ]
    return _tools


# ── Entrypoint ───────────────────────────────────────────────
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

    # Unwrap nested JSON layers
    def _unwrap(s):
        try:
            d = json.loads(s) if isinstance(s, str) else s
        except (json.JSONDecodeError, TypeError):
            return s
        # MCP Gateway layer: {"isError": false, "content": [{"type":"text","text":"..."}]}
        if isinstance(d, dict) and "content" in d and "isError" in d:
            for c in d.get("content", []):
                if isinstance(c, dict) and "text" in c:
                    return _unwrap(c["text"])
        # Lambda layer: {"status": "success", "result": "..."}
        if isinstance(d, dict) and "result" in d and "status" in d:
            return _unwrap(d["result"])
        return d

    inner = _unwrap(raw)

    # Summarize
    if isinstance(inner, dict):
        if "tables" in inner:
            t = inner["tables"]
            return f"{len(t)}개 테이블: {', '.join(x.get('table','') for x in t[:5])}"
        if "columns" in inner:
            return f"스키마 ({len(inner['columns'])}개 컬럼)"
        if "rows" in inner:
            return f"{len(inner['rows'])}개 행 반환"
        if "patients" in inner:
            return f"{len(inner['patients'])}명 환자"
        if "error" in inner:
            return f"오류: {str(inner['error'])[:150]}"
        keys = list(inner.keys())[:6]
        return f"키: {', '.join(keys)}"
    if isinstance(inner, list):
        return f"{len(inner)}개 항목"
    return str(inner)[:200]


@app.entrypoint
async def invoke(payload, context):
    from strands import Agent

    tools = _get_tools()
    agent = Agent(
        model=MODEL_ID,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
    )

    prompt = payload.get("prompt", "안녕하세요")
    emitted_tool_ids = set()

    try:
        async for event in agent.stream_async(prompt):
            # Completed toolUse and toolResult in message content
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
                        summary = _summarize_tool_result(tr.get("content", []))
                        yield f"\n{status} Result: {summary}\n\n"

            # Text streaming
            if "data" in event:
                yield event["data"]
    except Exception as e:
        yield f"\n\n❌ Error: {str(e)}"


if __name__ == "__main__":
    app.run()
