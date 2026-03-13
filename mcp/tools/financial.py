"""Financial tools: claim summary"""
from emr_client import execute_sql

CATALOG = "s3tablescatalog"
DB = "fhir-bucket.data"


def get_claim_summary(patient_id: str = None, date_from: str = None,
                      date_to: str = None, status: str = None) -> list[dict]:
    """Get claim and explanation of benefit summary."""
    conditions = []
    if patient_id:
        conditions.append(f"c.patient_reference LIKE '%{patient_id}'")
    if date_from:
        conditions.append(f"c.billable_period_start >= '{date_from}'")
    if date_to:
        conditions.append(f"c.billable_period_start <= '{date_to}'")
    if status:
        conditions.append(f"c.status = '{status}'")
    where = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
    SELECT c.resource_id, c.status, c.type_display, c.use_code,
           c.billable_period_start, c.billable_period_end,
           c.total_value, c.total_currency,
           e.payment_amount_value, e.payment_amount_currency, e.outcome
    FROM {CATALOG}.`{DB}`.financial_claim c
    LEFT JOIN {CATALOG}.`{DB}`.explanation_of_benefit e
        ON e.claim_reference LIKE CONCAT('%', c.resource_id)
    WHERE {where}
    ORDER BY c.billable_period_start DESC
    LIMIT 100
    """
    return execute_sql(sql)
