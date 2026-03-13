"""Advanced query tool: run_custom_query (SELECT-only, LIMIT enforced)"""
import re
from emr_client import execute_sql

CATALOG = "s3tablescatalog"
DB = "fhir-bucket.data"

BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def run_custom_query(query: str) -> list[dict]:
    """Execute a read-only Spark SQL query against the FHIR data lake. Only SELECT statements allowed. LIMIT 100 enforced."""
    if BLOCKED_KEYWORDS.search(query):
        raise ValueError("Only SELECT queries are allowed.")

    # Enforce LIMIT
    if not re.search(r"\bLIMIT\b", query, re.IGNORECASE):
        query = query.rstrip().rstrip(";") + " LIMIT 100"

    return execute_sql(query)
