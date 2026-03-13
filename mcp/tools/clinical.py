"""Clinical tools: encounter history, observations, medications, diagnosis history"""
from emr_client import execute_sql

CATALOG = "s3tablescatalog"
DB = "fhir-bucket.data"


def get_encounter_history(patient_id: str, date_from: str = None, date_to: str = None,
                          class_code: str = None) -> list[dict]:
    """Get patient encounter history with practitioner and location details."""
    conditions = [f"e.subject_reference LIKE '%{patient_id}'"]
    if date_from:
        conditions.append(f"e.period_start >= '{date_from}'")
    if date_to:
        conditions.append(f"e.period_start <= '{date_to}'")
    if class_code:
        conditions.append(f"e.class_code = '{class_code}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT e.resource_id, e.class_code, e.type_display, e.status,
           e.period_start, e.period_end, e.reason_display,
           pr.name_given AS practitioner_given, pr.name_family AS practitioner_family,
           l.name AS location_name, o.name AS organization_name
    FROM {CATALOG}.`{DB}`.clinical_encounter e
    LEFT JOIN {CATALOG}.`{DB}`.practitioner_registry pr
        ON e.participant_individual_reference LIKE CONCAT('%', pr.resource_id)
    LEFT JOIN {CATALOG}.`{DB}`.location_registry l
        ON e.location_reference LIKE CONCAT('%', l.resource_id)
    LEFT JOIN {CATALOG}.`{DB}`.organization_registry o
        ON e.service_provider_reference LIKE CONCAT('%', o.resource_id)
    WHERE {where}
    ORDER BY e.period_start DESC
    LIMIT 100
    """
    return execute_sql(sql)


def get_clinical_observations(patient_id: str, observation_code: str = None,
                              date_from: str = None, date_to: str = None) -> list[dict]:
    """Get clinical observations (vitals, lab results) for a patient."""
    conditions = [f"subject_reference LIKE '%{patient_id}'"]
    if observation_code:
        conditions.append(f"LOWER(code_display) LIKE '%{observation_code.lower()}%'")
    if date_from:
        conditions.append(f"effective_datetime >= '{date_from}'")
    if date_to:
        conditions.append(f"effective_datetime <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT code_display, value_quantity_value, value_quantity_unit,
           effective_datetime, category_display, status
    FROM {CATALOG}.`{DB}`.clinical_observation
    WHERE {where}
    ORDER BY effective_datetime DESC
    LIMIT 100
    """
    return execute_sql(sql)


def get_medications(patient_id: str, active_only: bool = False) -> list[dict]:
    """Get medication requests and administration records for a patient."""
    status_filter = "AND mr.status = 'active'" if active_only else ""

    sql = f"""
    SELECT mr.medication_code_display, mr.status, mr.authored_datetime,
           mr.dosage_instruction_text, mr.reason_reference_display,
           ma.effective_datetime AS administered_datetime, ma.status AS admin_status
    FROM {CATALOG}.`{DB}`.medication_request mr
    LEFT JOIN {CATALOG}.`{DB}`.medication_administration ma
        ON ma.request_reference LIKE CONCAT('%', mr.resource_id)
    WHERE mr.subject_reference LIKE '%{patient_id}'
    {status_filter}
    ORDER BY mr.authored_datetime DESC
    LIMIT 100
    """
    return execute_sql(sql)


def get_diagnosis_history(patient_id: str, category: str = None) -> list[dict]:
    """Get diagnosis history including conditions and procedures."""
    cat_filter = f"AND LOWER(c.category_display) LIKE '%{category.lower()}%'" if category else ""

    sql = f"""
    SELECT c.code_display AS condition, c.clinical_status_code, c.verification_status_code,
           c.onset_datetime, c.category_display,
           p.code_display AS procedure_name, p.performed_datetime
    FROM {CATALOG}.`{DB}`.clinical_condition c
    LEFT JOIN {CATALOG}.`{DB}`.clinical_procedure p
        ON p.subject_reference LIKE CONCAT('%', '{patient_id}')
        AND p.reason_reference LIKE CONCAT('%', c.resource_id)
    WHERE c.subject_reference LIKE '%{patient_id}'
    {cat_filter}
    ORDER BY c.onset_datetime DESC
    LIMIT 100
    """
    return execute_sql(sql)
