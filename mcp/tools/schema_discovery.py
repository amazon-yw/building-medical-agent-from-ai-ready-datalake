"""Schema discovery tools: list_tables, get_table_schema, get_table_relationships"""
import json
from metadata_loader import (
    MCP_MODE,
    get_domain_map, get_all_tables, get_table_info, get_column_map,
    fqn, CATALOG, DB, CODE_MAPS, find_patient_ref_column,
)
from emr_client import execute_sql


def list_tables(domain: str = None) -> str:
    """List available tables with metadata and query hints for AI agents."""
    if MCP_MODE == "with_metadata":
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
    else:
        rows = execute_sql(f"SHOW TABLES IN `{CATALOG}`.`{DB}`")
        tables = []
        for r in rows:
            t = r.get("tableName") or r.get("namespace", "")
            if t:
                tables.append({"table": t, "fqn": fqn(t)})
        return json.dumps({
            "query_hints": {"catalog": CATALOG, "namespace": DB},
            "tables": tables,
        })


def get_table_schema(table_name: str) -> str:
    """Get table schema with column info and query hints."""
    if MCP_MODE == "with_metadata":
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
    else:
        rows = execute_sql(f"DESCRIBE {fqn(table_name)}")
        cols = [{"column_name": r.get("col_name", ""), "data_type": r.get("data_type", "")}
                for r in rows if r.get("col_name")]
        return json.dumps({
            "table": table_name, "fqn": fqn(table_name),
            "query_example": f"SELECT * FROM {fqn(table_name)} LIMIT 10",
            "columns": cols,
        })


def get_table_relationships(table_name: str = None) -> str:
    """Get table relationships from reference columns."""
    if MCP_MODE == "with_metadata":
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
    else:
        if table_name:
            tables = [table_name]
        else:
            rows = execute_sql(f"SHOW TABLES IN `{CATALOG}`.`{DB}`")
            tables = [r.get("tableName") for r in rows if r.get("tableName")]
        results = []
        for t in tables:
            rows = execute_sql(f"DESCRIBE {fqn(t)}")
            refs = [{"column": r["col_name"], "join_hint": f"JOIN ... ON {fqn(t)}.`{r['col_name']}` = <target>.`rid`"}
                    for r in rows if r.get("col_name", "").endswith("_ref")]
            if refs:
                results.append({"table": t, "fqn": fqn(t), "references": refs})
        return json.dumps(results)
