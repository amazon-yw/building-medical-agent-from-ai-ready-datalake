"""Financial tools: claim summary"""
from emr_client import execute_sql
from metadata_loader import find_column as fc, find_patient_ref_column as fpr, fqn, map_code as mc


def get_claim_summary(patient_id: str = None, date_from: str = None,
                      date_to: str = None, status: str = None) -> list[dict]:
    t = "claim"
    pat = fpr(t)
    period_start = fc(t, "billable_period_start", "system_created_datetime", "created_datetime")
    st = fc(t, "status")

    conds = []
    if patient_id:
        conds.append(f"`{pat}` LIKE '%{patient_id}'")
    if date_from:
        conds.append(f"`{period_start}` >= '{date_from}'")
    if date_to:
        conds.append(f"`{period_start}` <= '{date_to}'")
    if status:
        conds.append(f"`{st}` = '{mc(t, 'status', status)}'")
    where = " AND ".join(conds) if conds else "1=1"

    sql = f"SELECT * FROM {fqn(t)} WHERE {where} ORDER BY `{period_start}` DESC LIMIT 100"
    return execute_sql(sql)
