"""Schema discovery tools: list_tables, get_table_schema, get_table_relationships"""
import json
from metadata_loader import (
    get_domain_map, get_all_tables, get_table_info, get_column_map,
    fqn, CATALOG, DB, CODE_MAPS, find_patient_ref_column,
)


def list_tables(domain: str = None) -> list[dict]:
    """List available tables with metadata and query hints for AI agents."""
    domain_map = get_domain_map()
    if domain and domain.lower() in domain_map:
        tables = domain_map[domain.lower()]
    else:
        tables = get_all_tables()

    results = []
    for t in tables:
        info = get_table_info(t)
        cols = info.get("columns", {})
        column_names = [c.get("expanded_name", "") for c in cols.values()]
        results.append({
            "table": t,
            "fqn": fqn(t),
            "domain": info.get("domain", ""),
            "fhir_resource": info.get("fhir_resource", ""),
            "description": info.get("description", ""),
            "column_count": info.get("column_count", 0),
            "columns": column_names,
        })

    return json.dumps({
        "query_hints": {
            "catalog": CATALOG,
            "namespace": DB,
            "fqn_format": f"`{CATALOG}`.`{DB}`.`<table_name>`",
            "note": "Always use backtick-quoted fully qualified names. Column names in the tables are the expanded_name values listed below, NOT abbreviated names.",
        },
        "tables": results,
    })


def get_table_schema(table_name: str) -> str:
    """Get detailed table schema with column info, code mappings, and query hints."""
    info = get_table_info(table_name)
    if not info:
        return json.dumps({"error": f"Table '{table_name}' not found in metadata"})

    patient_ref = find_patient_ref_column(table_name)
    cols = []
    for abbr, col_info in info.get("columns", {}).items():
        expanded = col_info.get("expanded_name", abbr)
        col_entry = {
            "column_name": expanded,
            "data_type": col_info.get("data_type", ""),
            "description": col_info.get("description", ""),
            "semantic_category": col_info.get("semantic_category", ""),
            "nullable": col_info.get("nullable", True),
        }
        if col_info.get("references_table"):
            col_entry["references_table"] = col_info["references_table"]
        # Include code mappings if this column has coded values
        if expanded in CODE_MAPS:
            col_entry["code_values"] = CODE_MAPS[expanded]
        cols.append(col_entry)

    return json.dumps({
        "table": table_name,
        "fqn": fqn(table_name),
        "domain": info.get("domain", ""),
        "fhir_resource": info.get("fhir_resource", ""),
        "description": info.get("description", ""),
        "patient_reference_column": patient_ref,
        "query_example": f"SELECT * FROM {fqn(table_name)} LIMIT 10",
        "columns": cols,
    })


def get_table_relationships(table_name: str = None) -> str:
    """Get table relationships from metadata reference columns."""
    tables = [table_name] if table_name else get_all_tables()
    results = []
    for t in tables:
        cols = get_column_map(t)
        refs = []
        for abbr, col_info in cols.items():
            if col_info.get("references_table"):
                expanded = col_info.get("expanded_name", abbr)
                target = col_info["references_table"]
                refs.append({
                    "column": expanded,
                    "references_table": target,
                    "references_fqn": fqn(target),
                    "join_hint": f"JOIN {fqn(target)} ON `{expanded}` = {fqn(target)}.`resource_id`",
                })
        if refs:
            results.append({"table": t, "fqn": fqn(t), "references": refs})
    return json.dumps(results)
