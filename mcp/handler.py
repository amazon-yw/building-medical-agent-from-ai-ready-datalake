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
}


def handler(event, context):
    """AgentCore Gateway invokes this Lambda with tool name and arguments."""
    logger.info(f"Event: {json.dumps(event)}")

    tool_name = event.get("toolName") or event.get("tool_name") or event.get("name")
    arguments = event.get("arguments") or event.get("input") or {}

    if isinstance(arguments, str):
        arguments = json.loads(arguments)

    if tool_name not in TOOL_REGISTRY:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    try:
        result = TOOL_REGISTRY[tool_name](**arguments)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}
