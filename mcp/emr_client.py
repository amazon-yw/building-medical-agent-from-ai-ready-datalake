"""EMR Serverless Livy client for executing Spark SQL queries."""
import json
import os
import time
import logging

import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import requests

logger = logging.getLogger(__name__)

REGION = os.environ.get("AWS_REGION", "us-west-2")
APPLICATION_ID = os.environ["EMR_APPLICATION_ID"]
EXECUTION_ROLE_ARN = os.environ["EMR_EXECUTION_ROLE_ARN"]
ACCOUNT_ID = EXECUTION_ROLE_ARN.split(":")[4]
ENDPOINT = f"https://{APPLICATION_ID}.livy.emr-serverless-services.{REGION}.amazonaws.com"
HEADERS = {"Content-Type": "application/json"}

# Module-level session cache (persists across warm Lambda invocations)
_session_id = None


def _get_signer():
    session = botocore.session.Session()
    return SigV4Auth(session.get_credentials(), "emr-serverless", REGION)


def _signed_request(method, url, data=None):
    signer = _get_signer()
    body = json.dumps(data) if data else None
    req = AWSRequest(method=method, url=url, data=body, headers=HEADERS)
    signer.add_auth(req)
    prepped = req.prepare()
    fn = getattr(requests, method.lower())
    kwargs = {"headers": prepped.headers}
    if body:
        kwargs["data"] = body
    return fn(prepped.url, **kwargs)


def _get_or_create_session():
    """Reuse existing Livy session or create a new one."""
    global _session_id

    # Check if cached session is still alive
    if _session_id is not None:
        r = _signed_request("GET", f"{ENDPOINT}/sessions/{_session_id}/state")
        if r.status_code == 200 and r.json().get("state") in ("idle", "busy"):
            return _session_id
        _session_id = None

    # Reuse existing idle pyspark session or clean up incompatible ones
    r = _signed_request("GET", f"{ENDPOINT}/sessions")
    if r.status_code == 200:
        for s in r.json().get("sessions", []):
            if s.get("state") == "idle" and s.get("kind") == "pyspark":
                _session_id = s["id"]
                logger.info(f"Reusing existing session {_session_id}")
                return _session_id
            elif s.get("state") in ("idle", "busy"):
                _signed_request("DELETE", f"{ENDPOINT}/sessions/{s['id']}")
                logger.info(f"Deleted session {s['id']}")

    # Create new session
    data = {
        "kind": "pyspark",
        "heartbeatTimeoutInSecond": 600,
        "conf": {
            "emr-serverless.session.executionRoleArn": EXECUTION_ROLE_ARN,
            "spark.jars.packages": "software.amazon.s3tables:s3-tables-catalog-for-iceberg-runtime:0.1.3",
            "spark.sql.catalog.s3tablescatalog": "org.apache.iceberg.spark.SparkCatalog",
            "spark.sql.catalog.s3tablescatalog.catalog-impl": "software.amazon.s3tables.iceberg.S3TablesCatalog",
            "spark.sql.catalog.s3tablescatalog.warehouse": f"arn:aws:s3tables:{REGION}:{ACCOUNT_ID}:bucket/fhir-bucket",
            "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            "spark.driver.extraJavaOptions": "-Dfile.encoding=UTF-8",
            "spark.executor.extraJavaOptions": "-Dfile.encoding=UTF-8" 
        },
        "ttl": "2h",
    }
    r = _signed_request("POST", f"{ENDPOINT}/sessions", data)
    r.raise_for_status()
    _session_id = r.json()["id"]
    logger.info(f"Created new session {_session_id}")

    # Wait for session to become idle
    for _ in range(120):
        r = _signed_request("GET", f"{ENDPOINT}/sessions/{_session_id}/state")
        state = r.json().get("state")
        if state == "idle":
            return _session_id
        if state in ("dead", "error", "shutting_down"):
            raise RuntimeError(f"Session failed with state: {state}")
        time.sleep(2)
    raise TimeoutError("Session did not become idle within timeout")


def execute_sql(sql: str, timeout: int = 120) -> list[dict]:
    """Execute Spark SQL and return results as list of dicts."""
    session_id = _get_or_create_session()

    # Submit statement
    code = f"spark.sql(\"\"\"{sql}\"\"\").toJSON().collect()"
    r = _signed_request("POST", f"{ENDPOINT}/sessions/{session_id}/statements", {"code": code})
    r.raise_for_status()
    stmt_id = r.json()["id"]

    # Poll for completion
    stmt_url = f"{ENDPOINT}/sessions/{session_id}/statements/{stmt_id}"
    for _ in range(timeout):
        r = _signed_request("GET", stmt_url)
        resp = r.json()
        state = resp.get("state")
        if state == "available":
            output = resp.get("output", {})
            if output.get("status") == "error":
                raise RuntimeError(output.get("evalue", "Unknown Spark SQL error"))
            # Parse JSON strings from collect()
            data = output.get("data", {}).get("text/plain", "[]")
            try:
                # PySpark collect() returns Python repr: ['{"k":"v"}', ...]
                # Use ast.literal_eval to safely parse Python literals
                import ast
                parsed = ast.literal_eval(data)
                if isinstance(parsed, list):
                    return [json.loads(r) if isinstance(r, str) else r for r in parsed]
                return [{"raw_output": data}]
            except (ValueError, SyntaxError, json.JSONDecodeError):
                # Try direct JSON parse as fallback
                try:
                    parsed = json.loads(data)
                    if isinstance(parsed, list):
                        return parsed
                    return [parsed]
                except json.JSONDecodeError:
                    return [{"raw_output": data}]
        if state in ("error", "cancelled"):
            raise RuntimeError(f"Statement failed: {resp}")
        time.sleep(1)
    raise TimeoutError(f"Statement did not complete within {timeout}s")


def execute_spark_code(code: str, timeout: int = 120) -> str:
    """Execute arbitrary PySpark/Spark code and return raw output."""
    session_id = _get_or_create_session()

    r = _signed_request("POST", f"{ENDPOINT}/sessions/{session_id}/statements", {"code": code})
    r.raise_for_status()
    stmt_id = r.json()["id"]

    stmt_url = f"{ENDPOINT}/sessions/{session_id}/statements/{stmt_id}"
    for _ in range(timeout):
        r = _signed_request("GET", stmt_url)
        resp = r.json()
        state = resp.get("state")
        if state == "available":
            output = resp.get("output", {})
            if output.get("status") == "error":
                raise RuntimeError(output.get("evalue", "Unknown error"))
            return output.get("data", {}).get("text/plain", "")
        if state in ("error", "cancelled"):
            raise RuntimeError(f"Statement failed: {resp}")
        time.sleep(1)
    raise TimeoutError(f"Statement did not complete within {timeout}s")
