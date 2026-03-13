"""Schema discovery tools: list_tables, get_table_schema, get_table_relationships"""
from emr_client import execute_spark_code

CATALOG = "s3tablescatalog"
DB = "fhir-bucket.data"

DOMAIN_MAP = {
    "administrative": ["patient_registry", "practitioner_registry", "organization_registry", "location_registry", "practitioner_role"],
    "clinical": ["clinical_encounter", "clinical_condition", "clinical_procedure", "clinical_observation"],
    "medication": ["medication_catalog", "medication_request", "medication_administration"],
    "diagnostic": ["diagnostic_report", "imaging_study", "immunization_record", "allergy_intolerance"],
    "care": ["care_plan", "care_team", "device_catalog", "supply_delivery"],
    "financial": ["financial_claim", "explanation_of_benefit"],
    "document": ["document_reference", "provenance_audit"],
}


def list_tables(domain: str = None) -> list[dict]:
    """List available tables with metadata from TBLPROPERTIES and COMMENT."""
    tables = []
    if domain and domain.lower() in DOMAIN_MAP:
        tables = DOMAIN_MAP[domain.lower()]
    else:
        for t_list in DOMAIN_MAP.values():
            tables.extend(t_list)

    code = f"""
import json
results = []
for table in {tables}:
    try:
        props = spark.sql(f"SHOW TBLPROPERTIES `{CATALOG}`.`{DB}`.{{table}}").collect()
        prop_dict = {{r['key']: r['value'] for r in props}}
        desc = spark.sql(f"DESCRIBE TABLE EXTENDED `{CATALOG}`.`{DB}`.{{table}}").collect()
        comment = ''
        for r in desc:
            if r['col_name'] == 'Comment' or r['col_name'] == '# Detailed Table Information':
                continue
            if r['data_type'] and r['data_type'].startswith('Table Comment:'):
                comment = r['data_type'].replace('Table Comment:', '').strip()
        results.append({{'table': table, 'domain': prop_dict.get('domain', ''), 'fhir_resource': prop_dict.get('fhir_resource', ''), 'comment': comment}})
    except Exception as e:
        results.append({{'table': table, 'error': str(e)}})
print(json.dumps(results))
"""
    return execute_spark_code(code)


def get_table_schema(table_name: str) -> str:
    """Get detailed table schema with column comments from DESCRIBE TABLE EXTENDED."""
    code = f"""
import json
rows = spark.sql("DESCRIBE TABLE EXTENDED `{CATALOG}`.`{DB}`.{table_name}").collect()
cols = []{{'name': r['col_name'], 'type': r['data_type'], 'comment': r['comment'] or ''}} for r in rows if r['col_name'] and not r['col_name'].startswith('#')]
props = spark.sql("SHOW TBLPROPERTIES `{CATALOG}`.`{DB}`.{table_name}").collect()
prop_dict = {{r['key']: r['value'] for r in props}}
print(json.dumps({{'columns': cols, 'properties': prop_dict}}))
"""
    return execute_spark_code(code)


def get_table_relationships(table_name: str = None) -> str:
    """Infer table relationships from _reference suffix columns."""
    tables = [table_name] if table_name else []
    if not tables:
        for t_list in DOMAIN_MAP.values():
            tables.extend(t_list)

    code = f"""
import json
results = []
for table in {tables}:
    rows = spark.sql(f"DESCRIBE TABLE EXTENDED `{CATALOG}`.`{DB}`.{{table}}").collect()
    refs = []
    for r in rows:
        if r['col_name'] and r['col_name'].endswith('_reference'):
            target = r['col_name'].replace('_reference', '').replace('subject', 'patient_registry').replace('patient', 'patient_registry').replace('encounter', 'clinical_encounter').replace('practitioner', 'practitioner_registry').replace('organization', 'organization_registry').replace('location', 'location_registry')
            refs.append({{'column': r['col_name'], 'comment': r['comment'] or '', 'inferred_target': target}})
    if refs:
        results.append({{'table': table, 'references': refs}})
print(json.dumps(results))
"""
    return execute_spark_code(code)
