"""Analytics tools: care gaps detection, population health metrics"""
from emr_client import execute_sql

CATALOG = "s3tablescatalog"
DB = "fhir-bucket.data"


def detect_care_gaps(patient_id: str) -> list[dict]:
    """Detect care gaps: missing immunizations, overdue screenings, incomplete care plans."""
    sql = f"""
    WITH patient_immunizations AS (
        SELECT DISTINCT vaccine_code_display
        FROM {CATALOG}.`{DB}`.immunization_record
        WHERE patient_reference LIKE '%{patient_id}'
    ),
    patient_care_plans AS (
        SELECT resource_id, category_display, status, period_start, period_end
        FROM {CATALOG}.`{DB}`.care_plan
        WHERE subject_reference LIKE '%{patient_id}'
    ),
    recent_observations AS (
        SELECT code_display, MAX(effective_datetime) AS last_date
        FROM {CATALOG}.`{DB}`.clinical_observation
        WHERE subject_reference LIKE '%{patient_id}'
        GROUP BY code_display
    )
    SELECT 'immunizations' AS category, to_json(collect_list(struct(*))) AS data
    FROM patient_immunizations
    UNION ALL
    SELECT 'care_plans', to_json(collect_list(struct(*)))
    FROM patient_care_plans
    UNION ALL
    SELECT 'recent_screenings', to_json(collect_list(struct(*)))
    FROM recent_observations
    """
    return execute_sql(sql)


def get_population_health_metrics(condition_code: str = None, age_group: str = None) -> list[dict]:
    """Get population health metrics with optional condition and age group filters."""
    conditions = []
    if condition_code:
        conditions.append(f"LOWER(c.code_display) LIKE '%{condition_code.lower()}%'")
    cond_where = " AND ".join(conditions) if conditions else "1=1"

    age_case = """
    CASE
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.birth_date)) < 18 THEN '0-17'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.birth_date)) < 30 THEN '18-29'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.birth_date)) < 40 THEN '30-39'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.birth_date)) < 50 THEN '40-49'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.birth_date)) < 60 THEN '50-59'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.birth_date)) < 70 THEN '60-69'
        ELSE '70+'
    END
    """
    age_filter = f"AND {age_case} = '{age_group}'" if age_group else ""

    sql = f"""
    SELECT {age_case} AS age_group,
           p.gender,
           c.code_display AS condition,
           COUNT(DISTINCT p.resource_id) AS patient_count
    FROM {CATALOG}.`{DB}`.patient_registry p
    JOIN {CATALOG}.`{DB}`.clinical_condition c
        ON c.subject_reference LIKE CONCAT('%', p.resource_id)
    WHERE {cond_where} {age_filter}
    GROUP BY 1, 2, 3
    ORDER BY patient_count DESC
    LIMIT 100
    """
    return execute_sql(sql)
