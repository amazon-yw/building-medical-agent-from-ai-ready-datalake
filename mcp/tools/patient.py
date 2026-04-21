"""Patient tools: get_patient_summary, search_patients"""
from emr_client import execute_sql
from metadata_loader import find_column as fc, find_patient_ref_column as fpr, fqn, map_code as mc


def get_patient_summary(patient_id: str) -> dict:
    pt = "patient"
    rid = fc(pt, "resource_id")

    patient_data = execute_sql(f"SELECT * FROM {fqn(pt)} WHERE `{rid}` = '{patient_id}'")

    cond_t = "condition"
    conditions = execute_sql(
        f"SELECT * FROM {fqn(cond_t)} WHERE `{fpr(cond_t)}` LIKE '%{patient_id}' LIMIT 50"
    )

    med_t = "medication_request"
    medications = execute_sql(
        f"SELECT * FROM {fqn(med_t)} WHERE `{fpr(med_t)}` LIKE '%{patient_id}' LIMIT 50"
    )

    allergy_t = "allergy_intolerance"
    allergies = execute_sql(
        f"SELECT * FROM {fqn(allergy_t)} WHERE `{fpr(allergy_t)}` LIKE '%{patient_id}' LIMIT 50"
    )

    return {
        "patient": patient_data,
        "conditions": conditions,
        "medications": medications,
        "allergies": allergies,
    }


def search_patients(name: str = None, gender: str = None, birth_date_from: str = None,
                    birth_date_to: str = None, condition_code: str = None) -> list[dict]:
    pt = "patient"
    given = fc(pt, "name_given")
    family = fc(pt, "name_family")
    gen = fc(pt, "gender")
    bd = fc(pt, "birth_date")
    rid = fc(pt, "resource_id")

    conds = []
    if name:
        conds.append(f"(CONCAT(`{family}`, `{given}`) LIKE '%{name}%')")
    if gender:
        conds.append(f"`{gen}` = '{mc(pt, 'gender', gender)}'")
    if birth_date_from:
        conds.append(f"`{bd}` >= '{birth_date_from}'")
    if birth_date_to:
        conds.append(f"`{bd}` <= '{birth_date_to}'")
    where = " AND ".join(conds) if conds else "1=1"

    if condition_code:
        cond_t = "condition"
        cond_subj = fpr(cond_t)
        cond_disp = fc(cond_t, "code_display", "code_text")
        sql = f"""SELECT DISTINCT p.* FROM {fqn(pt)} p
            JOIN {fqn(cond_t)} c ON c.`{cond_subj}` LIKE CONCAT('%%', p.`{rid}`)
            WHERE {where} AND LOWER(c.`{cond_disp}`) LIKE '%%{condition_code.lower()}%%'
            LIMIT 100"""
    else:
        sql = f"SELECT * FROM {fqn(pt)} p WHERE {where} LIMIT 100"
    return execute_sql(sql)
