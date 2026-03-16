"""Analytics tools: care gaps detection, population health metrics"""
from emr_client import execute_sql
from metadata_loader import find_column as fc, find_patient_ref_column as fpr, fqn, map_code as mc


def detect_care_gaps(patient_id: str) -> list[dict]:
    imm_t = "immunization"
    immunizations = execute_sql(
        f"SELECT * FROM {fqn(imm_t)} WHERE `{fpr(imm_t)}` LIKE '%{patient_id}' LIMIT 50"
    )

    cp_t = "care_plan"
    care_plans = execute_sql(
        f"SELECT * FROM {fqn(cp_t)} WHERE `{fpr(cp_t)}` LIKE '%{patient_id}' LIMIT 50"
    )

    obs_t = "observation"
    obs_eff = fc(obs_t, "effective_datetime")
    observations = execute_sql(
        f"SELECT * FROM {fqn(obs_t)} WHERE `{fpr(obs_t)}` LIKE '%{patient_id}' ORDER BY `{obs_eff}` DESC LIMIT 50"
    )

    return {
        "immunizations": immunizations,
        "care_plans": care_plans,
        "recent_observations": observations,
    }


def get_population_health_metrics(condition_code: str = None, age_group: str = None) -> list[dict]:
    pt = "patient"
    bd = fc(pt, "birth_date")
    gen = fc(pt, "gender")
    rid = fc(pt, "resource_id")

    cond_t = "condition"
    cond_subj = fpr(cond_t)
    cond_disp = fc(cond_t, "code_display", "code_text")

    age_case = f"""
    CASE
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.`{bd}`)) < 18 THEN '0-17'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.`{bd}`)) < 30 THEN '18-29'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.`{bd}`)) < 40 THEN '30-39'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.`{bd}`)) < 50 THEN '40-49'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.`{bd}`)) < 60 THEN '50-59'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.`{bd}`)) < 70 THEN '60-69'
        WHEN YEAR(CURRENT_DATE) - YEAR(TO_DATE(p.`{bd}`)) < 80 THEN '70-79'
        ELSE '80+'
    END"""

    conds = []
    if condition_code:
        conds.append(f"LOWER(c.`{cond_disp}`) LIKE '%{condition_code.lower()}%'")
    if age_group:
        conds.append(f"{age_case} = '{age_group}'")
    where = " AND ".join(conds) if conds else "1=1"

    sql = f"""
    SELECT {age_case} AS age_group, p.`{gen}` AS gender, c.`{cond_disp}` AS condition_display,
           COUNT(DISTINCT p.`{rid}`) AS patient_count
    FROM {fqn(pt)} p
    JOIN {fqn(cond_t)} c ON c.`{cond_subj}` LIKE CONCAT('%', p.`{rid}`)
    WHERE {where}
    GROUP BY 1, 2, 3
    ORDER BY patient_count DESC
    LIMIT 100
    """
    return execute_sql(sql)
