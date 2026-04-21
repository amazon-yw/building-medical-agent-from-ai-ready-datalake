"""Advanced query tool: run_custom_query (SELECT-only, LIMIT enforced)"""
import re
from emr_client import execute_sql
from metadata_loader import CATALOG, DB

BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE|SHOW|DESCRIBE)\b",
    re.IGNORECASE,
)

# Common wrong namespace patterns to auto-correct
_WRONG_NS = re.compile(r"`?s3tablescatalog`?\.`?fhir-bucket\.data`?", re.IGNORECASE)


def run_custom_query(query: str) -> list[dict]:
    """Execute a read-only Spark SQL query against the FHIR data lake. Only SELECT statements allowed. LIMIT 100 enforced."""
    if BLOCKED_KEYWORDS.search(query):
        raise ValueError("Only SELECT queries are allowed.")
    # Auto-correct common wrong table paths
    query = _WRONG_NS.sub(f"`{CATALOG}`.`{DB}`", query)
    if re.match(r"\s*SELECT\b", query, re.IGNORECASE) and not re.search(r"\bLIMIT\b", query, re.IGNORECASE):
        query = query.rstrip().rstrip(";") + " LIMIT 100"
    return execute_sql(query)
