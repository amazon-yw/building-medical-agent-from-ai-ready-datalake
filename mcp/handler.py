"""Lambda handler for AgentCore Gateway MCP tool invocations."""
import json
import logging
import traceback

from tools.patient import get_patient_summary, search_patients
from tools.clinical import get_encounter_history, get_clinical_observations, get_medications, get_diagnosis_history
from tools.financial import get_claim_summary
from tools.analytics import detect_care_gaps, get_population_health_metrics
from tools.schema_discovery import list_tables, get_table_schema, get_table_relationships
from tools.query import run_custom_query
from tools.pubmed import search_pubmed, get_pubmed_article

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TOOL_REGISTRY = {
    "get_patient_summary": get_patient_summary,
    "search_patients": search_patients,
    "get_encounter_history": get_encounter_history,
    "get_clinical_observations": get_clinical_observations,
    "get_medications": get_medications,
    "get_diagnosis_history": get_diagnosis_history,
    "get_claim_summary": get_claim_summary,
    "detect_care_gaps": detect_care_gaps,
    "get_population_health_metrics": get_population_health_metrics,
    "list_tables": list_tables,
    "get_table_schema": get_table_schema,
    "get_table_relationships": get_table_relationships,
    "run_custom_query": run_custom_query,
    "search_pubmed": search_pubmed,
    "get_pubmed_article": get_pubmed_article,
}


def handler(event, context):
    """AgentCore Gateway invokes this Lambda with tool name and arguments."""
    logger.info(f"Event: {json.dumps(event)}")

    # Gateway passes tool name in client_context.custom
    tool_name = None
    if hasattr(context, 'client_context') and context.client_context:
        custom = getattr(context.client_context, 'custom', {}) or {}
        gw_tool = custom.get('bedrockAgentCoreToolName', '')
        # Strip target prefix: "FhirMcpLambdaTarget___list_tables" -> "list_tables"
        tool_name = gw_tool.split('___', 1)[-1] if '___' in gw_tool else gw_tool

    # Fallback to event keys
    if not tool_name:
        tool_name = event.get("toolName") or event.get("tool_name") or event.get("name")

    arguments = event.get("arguments", event)  # Direct invoke sends {toolName, arguments}, Gateway sends args as event

    if isinstance(arguments, str):
        arguments = json.loads(arguments)

    # Remove meta keys that are not tool arguments
    for key in ("toolName", "tool_name"):
        arguments.pop(key, None)

    if tool_name not in TOOL_REGISTRY:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    try:
        result = TOOL_REGISTRY[tool_name](**arguments)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}
