"""Load FHIR table/column metadata from S3 at Lambda cold start."""
import json
import os
import logging
import boto3

logger = logging.getLogger(__name__)

# MCP_MODE: with_metadata (default) | legacy
MCP_MODE = os.environ.get("MCP_MODE", "with_metadata")

REGION = os.environ.get("AWS_REGION", "us-west-2")
ACCOUNT_ID = os.environ.get("AWS_ACCOUNT_ID", "")
METADATA_BUCKET = os.environ.get("METADATA_BUCKET", f"fhir-data-{ACCOUNT_ID}-{REGION}")
METADATA_KEY = os.environ.get("METADATA_KEY", "metadata/fhir_db_metadata.json")

CATALOG = "s3tablescatalog"
_DB_MAP = {
    "with_metadata": "data",
    "legacy": "data_legacy",
}
DB = _DB_MAP.get(MCP_MODE, "data")

_metadata = None


def _has_metadata() -> bool:
    return MCP_MODE == "with_metadata"


def _load():
    global _metadata
    if not _has_metadata():
        return {"domains": {}, "tables": {}}
    if _metadata is not None:
        return _metadata
    try:
        s3 = boto3.client("s3", region_name=REGION)
        obj = s3.get_object(Bucket=METADATA_BUCKET, Key=METADATA_KEY)
        _metadata = json.loads(obj["Body"].read())
        logger.info(f"Loaded metadata: {_metadata['total_tables']} tables")
    except Exception as e:
        logger.error(f"Failed to load metadata from s3://{METADATA_BUCKET}/{METADATA_KEY}: {e}")
        _metadata = {"domains": {}, "tables": {}}
    return _metadata


def get_domain_map() -> dict[str, list[str]]:
    meta = _load()
    return {d.lower(): info["tables"] for d, info in meta.get("domains", {}).items()}


def get_all_tables() -> list[str]:
    meta = _load()
    return list(meta.get("tables", {}).keys())


def get_table_info(table_name: str) -> dict:
    meta = _load()
    return meta.get("tables", {}).get(table_name, {})


def get_column_map(table_name: str) -> dict[str, dict]:
    info = get_table_info(table_name)
    return info.get("columns", {})


def _all_expanded_names(table_name: str) -> dict[str, str]:
    """Return {expanded_name: expanded_name} for all columns in a table."""
    cols = get_column_map(table_name)
    return {info["expanded_name"]: info["expanded_name"] for info in cols.values() if "expanded_name" in info}


def find_column(table_name: str, *keywords: str) -> str:
    """Find column by matching keywords against expanded_name.
    Tries exact match, then substring match, then token-based fuzzy match.
    Returns the expanded_name (which is the actual S3 Tables column name)."""
    cols = get_column_map(table_name)
    expanded_names = [info.get("expanded_name", "") for info in cols.values()]

    for kw in keywords:
        kw_lower = kw.lower()
        # Exact match
        for en in expanded_names:
            if en == kw:
                return en
        # Substring match (keyword in column name or column name in keyword)
        for en in expanded_names:
            en_lower = en.lower()
            if kw_lower in en_lower or en_lower in kw_lower:
                return en
        # Token-based fuzzy match: split by _ and check if key tokens overlap
        kw_tokens = set(kw_lower.replace("datetime", "").replace("date", "").split("_"))
        kw_tokens.discard("")
        if kw_tokens:
            best, best_score = None, 0
            for en in expanded_names:
                en_tokens = set(en.lower().replace("datetime", "").replace("date", "").split("_"))
                en_tokens.discard("")
                overlap = len(kw_tokens & en_tokens)
                if overlap > best_score:
                    best, best_score = en, overlap
            if best and best_score >= max(1, len(kw_tokens) - 1):
                return best
    # Return first keyword as fallback
    return keywords[0] if keywords else ""


def find_patient_ref_column(table_name: str) -> str:
    """Find the column that references the patient table."""
    if not _has_metadata():
        return "sbj_ref"
    cols = get_column_map(table_name)
    # Priority 1: references_table == "patient"
    for info in cols.values():
        if info.get("references_table") == "patient":
            return info.get("expanded_name", "")
    # Priority 2: known patient reference expanded names
    return find_column(table_name, "patient_reference", "subject_reference")


def find_columns(table_name: str) -> dict[str, str]:
    """Return {expanded_name: expanded_name} dict for all columns - useful for SELECT."""
    cols = get_column_map(table_name)
    return {info["expanded_name"]: info["expanded_name"] for info in cols.values() if "expanded_name" in info}


def fqn(table_name: str) -> str:
    return f"`{CATALOG}`.`{DB}`.`{table_name}`"


# Code value mappings: expanded column name -> {human_readable: db_code}
CODE_MAPS = {
    "status": {"active": "A", "completed": "C", "final": "F", "inactive": "I",
               "superseded": "S", "available": "V", "current": "A", "finished": "C"},
    "gender": {"male": "M", "female": "F", "other": "O", "unknown": "U"},
    "clinical_status_code": {"active": "A", "recurrence": "R", "relapse": "RL",
                             "inactive": "IA", "remission": "RE", "resolved": "RS"},
    "verification_status_code": {"unconfirmed": "U", "provisional": "P", "differential": "D",
                                 "confirmed": "C", "refuted": "R", "entered-in-error": "E"},
    "allergy_type": {"allergy": "AL", "intolerance": "IT"},
    "criticality": {"low": "L", "high": "H", "unable-to-assess": "UC"},
    "allergy_category": {"food": "FD", "medication": "MD", "environment": "EN", "biologic": "BL"},
    "intent": {"order": "O", "plan": "P", "proposal": "PR"},
    "use_code": {"claim": "CL", "preauthorization": "PA", "predetermination": "PD"},
    "outcome": {"queued": "Q", "complete": "CP", "partial": "PE", "error": "ER"},
    "document_status": {"preliminary": "P", "final": "F", "amended": "A", "entered-in-error": "EE"},
    "class_code": {"AMB": "AMB", "EMER": "EMER", "IMP": "IMP", "VR": "VR", "HH": "HH"},
    "primary_source": {"true": "Y", "false": "N"},
}


def map_code(table_name: str, column_semantic_name: str, value: str) -> str:
    """Map a human-readable value to its DB code."""
    col_name = find_column(table_name, column_semantic_name)
    if col_name in CODE_MAPS:
        return CODE_MAPS[col_name].get(value.lower(), value)
    return value
