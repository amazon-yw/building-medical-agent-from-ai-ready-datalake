"""Patient tools: get_patient_summary, search_patients"""
from emr_client import execute_sql

CATALOG = "s3tablescatalog"
DB = "fhir-bucket.data"


def get_patient_summary(patient_id: str) -> dict:
    """Get comprehensive patient summary including demographics, active conditions, allergies, and current medications."""
    sql = f"""
    WITH patient AS (
        SELECT resource_id, name_given, name_family, gender, birth_date, address_city, address_state
        FROM {CATALOG}.`{DB}`.patient_registry
        WHERE resource_id = '{patient_id}'
    ),
    conditions AS (
        SELECT code_display, clinical_status_code, onset_datetime
        FROM {CATALOG}.`{DB}`.clinical_condition
        WHERE subject_reference LIKE '%{patient_id}'
          AND clinical_status_code = 'active'
    ),
    allergies AS (
        SELECT code_display, criticality, clinical_status_code
        FROM {CATALOG}.`{DB}`.allergy_intolerance
        WHERE patient_reference LIKE '%{patient_id}'
    ),
    medications AS (
        SELECT mr.medication_code_display, mr.status, mr.authored_datetime
        FROM {CATALOG}.`{DB}`.medication_request mr
        WHERE mr.subject_reference LIKE '%{patient_id}'
          AND mr.status = 'active'
    )
    SELECT 'patient' AS section, to_json(struct(*)) AS data FROM patient
    UNION ALL
    SELECT 'condition', to_json(struct(*)) FROM conditions
    UNION ALL
    SELECT 'allergy', to_json(struct(*)) FROM allergies
    UNION ALL
    SELECT 'medication', to_json(struct(*)) FROM medications
    """
    return execute_sql(sql)


def search_patients(name: str = None, gender: str = None, birth_date_from: str = None,
                    birth_date_to: str = None, condition_code: str = None) -> list[dict]:
    """Search patients by name, gender, birth date range, or condition."""
    conditions = []
    if name:
        conditions.append(f"(p.name_given LIKE '%{name}%' OR p.name_family LIKE '%{name}%')")
    if gender:
        conditions.append(f"p.gender = '{gender}'")
    if birth_date_from:
        conditions.append(f"p.birth_date >= '{birth_date_from}'")
    if birth_date_to:
        conditions.append(f"p.birth_date <= '{birth_date_to}'")

    where = " AND ".join(conditions) if conditions else "1=1"

    if condition_code:
        sql = f"""
        SELECT DISTINCT p.resource_id, p.name_given, p.name_family, p.gender, p.birth_date,
               c.code_display AS condition_display
        FROM {CATALOG}.`{DB}`.patient_registry p
        JOIN {CATALOG}.`{DB}`.clinical_condition c ON c.subject_reference LIKE CONCAT('%', p.resource_id)
        WHERE {where}
          AND LOWER(c.code_display) LIKE '%{condition_code.lower()}%'
        LIMIT 100
        """
    else:
        sql = f"""
        SELECT p.resource_id, p.name_given, p.name_family, p.gender, p.birth_date
        FROM {CATALOG}.`{DB}`.patient_registry p
        WHERE {where}
        LIMIT 100
        """
    return execute_sql(sql)
