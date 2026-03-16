"""Clinical tools: encounter history, observations, medications, diagnosis history"""
from emr_client import execute_sql
from metadata_loader import find_column as fc, find_patient_ref_column as fpr, fqn, map_code as mc


def get_encounter_history(patient_id: str, date_from: str = None, date_to: str = None,
                          class_code: str = None) -> list[dict]:
    t = "encounter"
    subj = fpr(t)
    period_start = fc(t, "period_start_datetime", "period_start")
    cls = fc(t, "class_code")

    conds = [f"`{subj}` LIKE '%{patient_id}'"]
    if date_from:
        conds.append(f"`{period_start}` >= '{date_from}'")
    if date_to:
        conds.append(f"`{period_start}` <= '{date_to}'")
    if class_code:
        conds.append(f"`{cls}` = '{mc(t, 'class_code', class_code)}'")

    sql = f"SELECT * FROM {fqn(t)} WHERE {' AND '.join(conds)} ORDER BY `{period_start}` DESC LIMIT 100"
    return execute_sql(sql)


def get_clinical_observations(patient_id: str, observation_code: str = None,
                              date_from: str = None, date_to: str = None) -> list[dict]:
    t = "observation"
    subj = fpr(t)
    code_disp = fc(t, "code_display", "code_text")
    eff_dt = fc(t, "effective_datetime")

    conds = [f"`{subj}` LIKE '%{patient_id}'"]
    if observation_code:
        conds.append(f"LOWER(`{code_disp}`) LIKE '%{observation_code.lower()}%'")
    if date_from:
        conds.append(f"`{eff_dt}` >= '{date_from}'")
    if date_to:
        conds.append(f"`{eff_dt}` <= '{date_to}'")

    sql = f"SELECT * FROM {fqn(t)} WHERE {' AND '.join(conds)} ORDER BY `{eff_dt}` DESC LIMIT 100"
    return execute_sql(sql)


def get_medications(patient_id: str, active_only: bool = False) -> list[dict]:
    t = "medication_request"
    subj = fpr(t)
    status = fc(t, "status")
    authored = fc(t, "authored_datetime")

    conds = [f"`{subj}` LIKE '%{patient_id}'"]
    if active_only:
        conds.append(f"`{status}` = '{mc(t, 'status', 'active')}'")

    sql = f"SELECT * FROM {fqn(t)} WHERE {' AND '.join(conds)} ORDER BY `{authored}` DESC LIMIT 100"
    return execute_sql(sql)


def get_diagnosis_history(patient_id: str, category: str = None) -> list[dict]:
    t = "condition"
    subj = fpr(t)
    onset = fc(t, "onset_datetime")
    cat_disp = fc(t, "category_display")

    conds = [f"`{subj}` LIKE '%{patient_id}'"]
    if category:
        conds.append(f"LOWER(`{cat_disp}`) LIKE '%{category.lower()}%'")

    sql = f"SELECT * FROM {fqn(t)} WHERE {' AND '.join(conds)} ORDER BY `{onset}` DESC LIMIT 100"
    return execute_sql(sql)
