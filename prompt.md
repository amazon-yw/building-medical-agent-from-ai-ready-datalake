# SMUS Data Agent Prompts

---

## [STEP-1] Infer Metadata from Source Tables

Tables in "AwsDataCatalog.fhir_db" are related with patient data.
Please create metadata for the tables in "AwsDataCatalog.fhir_db". The reason I'm asking for metadata creation first is that I want to build tables that AI can understand effectively. For AI to work well with the data, comprehensive metadata for each table and column is essential. I'll use this metadata later when creating tables in S3 Tables to build the data lake. Since there are 24 tables in "AwsDataCatalog.fhir_db", the response might be quite huge, so please create the actual Python code to generate the comprehensive metadata for making it concise and efficient to avoid any issues. Python code should use "boto3.client('glue')" not pyspark.

### Environment Info
- Region: us-east-1
- S3 Bucket: Use the S3 bucket that contains "fhir-data" in its name
- S3 Prefix: metadata/
- Glue Database: fhir_db

### What the Code Generates:
1. Comprehensive Metadata Structure
- Domain Classification: Groups tables by healthcare domains (Administrative, Clinical, Financial, Medication, Security)
- Column-Level Details: For each of the ~498 columns across 24 tables:
  - Full expanded names (e.g., rid → resource_id, sbj_ref → subject_reference)
  - Detailed descriptions
  - Semantic categories (identifier, reference, temporal, coding, status, value, demographics, address, financial, dosage, device, document, 
narrative, etc.)
  - AI-friendly tags for search and discovery
  - Data types and nullability
- Common abbreviated column patterns should be mapped comprehensively (e.g., ref suffix → reference, sys suffix → code system, cd suffix → code
value dsp suffix → display text, dts suffix → datetime, txt suffix → free text)
2. Relationship Mapping
- Identifies foreign key relationships between tables via reference columns (_ref suffix)
- Maps reference columns to their target tables (e.g., sbj_ref → patient, evt_ref → encounter, prf_ref → practitioner, org_ref → 
organization, loc_ref → location, med_ref → medication, clm_ref → claim)
- Provides JOIN hint strings for analytics queries
- Enables proper join strategies for analytics
3. Analytics Hints
- Flags tables suitable for time-series analysis (boolean + specific time columns)
- Identifies cross-reference columns per table
- Suggests appropriate analytics patterns per table (e.g., disease_prevalence, visit_frequency, prescription_trends)
4. Output Files (saved to S3)
- fhir_db_metadata.json: Complete metadata for all tables (~200KB+ of structured data)
- README.md: Human-readable documentation with usage examples (Python code snippets for loading and querying metadata)
- field_mappings.json: Quick reference for field abbreviations with cross-table usage tracking
5. Naming Rule
- Table name and column name should use snake_case (with underscores) instead of camelCase.
- For tables and columns where the mapping is difficult to infer, keep the original names as-is and use pattern-based inference from 
suffixes.
6. Domain-Based Table Classification (actual table prefix mapping)
- Administrative
- Clinical
- Financial
- Medication
- Security
7. [IMPORTANT] If metadata inference for any table results in "Unknown" fields, the code should automatically retry that table's inference (
max 1 retry) before falling back to raw column names.

### [CRITICAL] Output File Schema Specification for MCP Server Integration

The generated fhir_db_metadata.json file is consumed by the MCP server's metadata_loader.py at Lambda cold start. 
The JSON structure MUST conform to the following schema exactly. Any deviation will break the MCP tool chain.

#### Top-Level Structure
```json
{
  "generated_at": "ISO-8601 timestamp string",
  "source_database": "fhir_db",
  "source_catalog": "AwsDataCatalog",
  "region": "us-east-1",
  "total_tables": 24,
  "total_columns": 498,
  "domains": { ... },
  "tables": { ... }
}
```

#### domains Object
Keys are domain names with first letter capitalized (e.g., "Clinical", "Administrative", "Financial", "Medication", "Security"). Each value:
```json
{
  "Clinical": {
    "table_count": 13,
    "tables": ["encounter", "condition", "observation", "procedure", ...]
  }
}
```

- tables array contains the snake_case table key names (same keys used in the top-level tables object).

#### tables Object
Keys are snake_case table names (e.g., "encounter", "patient", "medication_request"). Each value:
```json
{
  "original_table_name": "fhir_database_public_abc_enc",
  "snake_name": "encounter",
  "fhir_resource": "Encounter",
  "domain": "Clinical",
  "sub_domain": "Encounters",
  "description": "Human-readable table description",
  "column_count": 17,
  "columns": { ... }
}
```

Required fields per table:
| Field | Type | Description |
|---|---|---|
| original_table_name | string | Original Glue table name |
| snake_name | string | Normalized snake_case name (same as the key) |
| fhir_resource | string | FHIR resource type (e.g., "Encounter", "Patient") |
| domain | string | Domain classification (must match a key in domains) |
| sub_domain | string | Sub-domain label |
| description | string | Human-readable description of the table |
| column_count | integer | Number of columns |
| columns | object | Column metadata (see below) |

#### columns Object (nested inside each table)
Keys are the actual abbreviated column names as they exist in the Glue/Athena table (e.g., "sbj_ref", "prd_ed_dts", "rid"). Each value:
```json
{
  "expanded_name": "subject_reference",
  "description": "Reference to the patient (subject)",
  "semantic_category": "reference",
  "tags": ["patient", "subject", "foreign_key"],
  "references_table": "patient",
  "original_name": "sbj_ref",
  "data_type": "string",
  "nullable": true
}
```

Required fields per column:
| Field | Type | Description |
|---|---|---|
| expanded_name | string | Full semantic name in snake_case (e.g., "subject_reference", "period_start_datetime", "resource_id") |
| description | string | Human-readable column description |
| semantic_category | string | One of: identifier, reference, temporal, coding, status, value, demographics, address, financial, dosage, 
device, document, narrative |
| tags | array of strings | AI-friendly search tags |
| original_name | string | Original abbreviated column name (same as the key) |
| data_type | string | Spark/Glue data type (e.g., "string", "timestamp", "double", "bigint") |
| nullable | boolean | Whether the column is nullable |

Conditional field:
| Field | Type | When Required |
|---|---|---|
| references_table | string | Only for reference columns (semantic_category == "reference"). Value must be a valid key in the top-level 
tables object (e.g., "patient", "encounter", "practitioner") |

#### Key expanded_name Conventions
The MCP server's find_column() function looks up columns by expanded_name. The following semantic names MUST be used consistently across all tables where the concept applies:

| Semantic Concept | expanded_name | Typical Abbreviated Pattern |
|---|---|---|
| Resource ID | resource_id | rid |
| Subject/Patient reference | subject_reference | sbj_ref |
| Patient reference | patient_reference | pat_ref |
| Encounter reference | encounter_reference | evt_ref, enc_ref |
| Practitioner reference | practitioner_reference | prf_ref |
| Organization reference | organization_reference | org_ref |
| Location reference | location_reference | loc_ref |
| Status | status | sts, status |
| Code display | code_display | cd_dsp, code_dsp |
| Category display | category_display | ctg_dsp |
| Period start | period_start or period_start_datetime | prd_st_dts |
| Period end | period_end or period_end_datetime | prd_ed_dts |
| Effective datetime | effective_datetime | eff_dts |
| Onset datetime | onset_datetime | ons_dts |
| Authored datetime | authored_datetime | ath_dts |
| Birth date | birth_date | bth_dt |
| Gender | gender | gnd |
| Name given | name_given | nm_gvn |
| Name family | name_family | nm_fml |
| Clinical status | clinical_status or clinical_status_code | cln_sts_cd |
| Billable period start | billable_period_start | blb_prd_st |

│ **Note**: The abbreviated column names above are examples. The actual abbreviated names vary per workshop participant since they are inferred by AI. What matters is that expanded_name follows the conventions above so the MCP server's find_column() can resolve them correctly.

### Why This Approach?
Instead of printing huge amounts of text (which would be overwhelming), the code:
- Processes efficiently: Iterates through all 24 tables programmatically
- Stores persistently: Saves to S3 for reuse across sessions
- Stays accessible: Keeps metadata in the fhir_metadata variable for immediate use
- Provides summaries: Shows progress per table with column count and unknown column status during execution

### [HINT] Required Table and Column Names for MCP Server Compatibility

The MCP server tools use `find_column()` to look up columns by `expanded_name`. To ensure compatibility, the metadata MUST use the following table keys and column `expanded_name` values. These are **mandatory** — the MCP server will fail if these names are not present.

#### Required Table Keys (in `tables` object)
```
patient, encounter, condition, observation, medication_request,
allergy_intolerance, immunization, care_plan, claim
```

#### Required Column expanded_name Values per Table

| Table | Required expanded_name | Semantic Purpose |
|-------|----------------------|------------------|
| patient | `resource_id` | Primary key |
| patient | `name_given` | First name |
| patient | `name_family` | Last name |
| patient | `gender` | Gender code |
| patient | `birth_date` | Date of birth |
| encounter | `period_start_datetime` | Encounter start time |
| encounter | `class_code` | Encounter class (AMB/IMP/EMER) |
| observation | `code_display` | Observation type display text |
| observation | `effective_datetime` | Observation timestamp |
| medication_request | `status` | Prescription status |
| medication_request | `authored_datetime` | Prescription date |
| condition | `code_display` | Diagnosis display text |
| condition | `onset_datetime` | Diagnosis onset |
| condition | `category_display` | Condition category |
| claim | `billable_period_start` | Billing period start |
| claim | `status` | Claim status |
| (all clinical tables) | `subject_reference` or `patient_reference` | FK to patient table |

> **Important**: If the LLM infers a different name (e.g., `cd_display` instead of `code_display`), the MCP server's fuzzy matching will attempt to resolve it, but using the exact names above is strongly preferred.

### Next Steps for S3 Tables Creation
- Load metadata: fhir_metadata['tables']['table_name']
- Create S3 Tables: Use column descriptions and types from metadata
- Set up relationships: Leverage the relationship mappings and JOIN hints
- Enable AI discovery: Use tags and semantic categories for semantic search

---

## [STEP-2] Create Table Creation Notebook from Generated Metadata

I want to create tables in S3 Tables based on the generated metadata. For the tables created in S3 Tables, use full, descriptive names for all tables and columns instead of abbreviations like in the source tables to improve readability. I'd like to follow along with the table creation process in a SageMaker Unified Studio JupyterLab notebook environment. So please create/save it as a notebook file on Shared S3 so that it can be opened and used directly in JupyterLab.

### Environment Info
- Region: us-east-1
- Metadata sources: s3://<fhir-data bucket>/metadata/
- Notebook destination: s3://<amazon-sagemaker bucket>/shared/fhir_s3tables_creation.ipynb
- S3 bucket discovery: Find buckets containing "fhir-data" and "amazon-sagemaker" in their names

### Notebook Generation Method
- Generate the notebook as a Python script that builds the .ipynb JSON programmatically (not manually writing JSON)
- Use proper notebook cell structure: each cell's "source" must be a list of strings with explicit newline characters to ensure proper line breaks in JupyterLab
- Upload the generated .ipynb file to the SageMaker shared S3 bucket

### Spark Session Configuration
Please write the code referencing the example below to create a Spark session and create tables in S3 Tables. All cells in the notebook must use `%%pyspark default.spark` as the cell magic. Also, the parts that retrieve the region and account_id values and create the Spark session from the example code below must
all exist in the very first code cell.

When creating the Spark session with `SparkSession.builder`, only set `spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse` as shown in the sample code below. Do not include any other catalog configuration properties, as they actually cause errors in the SMUS JupyterLab environment.

Before the actual table creation, use the spark.sql("USE `s3tablescatalog_fhir-bucket`.data") statement so that the `CREATE TABLE` queries can be simplified to just `CREATE TABLE <table>`.

```python
import boto3
from pyspark.sql import SparkSession

session = boto3.session.Session()

# Get environments
region = session.region_name
account_id = session.client('sts').get_caller_identity()['Account']

# Create Spark session
spark = SparkSession.builder \
    .appName("FHIR_DATA_APP") \
    .config("spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse",
            f"arn:aws:s3tables:{region}:{account_id}:bucket/fhir-bucket") \
    .getOrCreate()

spark.sql("USE `s3tablescatalog_fhir-bucket`.data")

# Read DDL scripts
...

# Create table
spark.sql(<create statement>)
```

### SQL Statement Rules
- Execute `CREATE TABLE` statements using `spark.sql()` method
- Make sure no SQL statements contain backslashes
- Wrap `COMMENT` values in single quotes, and ensure no special characters (apostrophes, backslashes, newlines) appear inside them — use a sanitize function to clean descriptions
- Use `CREATE TABLE IF NOT EXISTS` for idempotent execution

### Notebook Cell Structure (Important)
- When building notebook cell source, ensure each line is a separate string element in the source list with proper newline characters appended (e.g., ["line1\n", "line2\n", "line3"])
- Do NOT build source as a single joined string and then split by '\n' — this causes literal backslash-n issues where all code merges into one line like: "%%pyspark default.sparkimport boto3from pyspark.sql import SparkSession"

### Notebook Content Structure
1. Title markdown cell
2. First code cell: Spark session setup (boto3 imports, region/account_id retrieval, SparkSession creation, USE statement)
3. Optional cleanup cell: DROP TABLE statements (commented out)
4. Domain-grouped table creation: One markdown header per domain, then one code cell per table with try/except error handling
5. Verification cells: SHOW TABLES, DESCRIBE TABLE for key tables
6. Column mapping reference cell: Dictionary mapping original abbreviated names to expanded names per table (for data loading)
7. Data loading example cell: Shows how to read from source, rename columns, and write to S3 Tables (commented out)

### Domain-Based Table Creation Order
- Administrative
- Clinical
- Financial
- Medication
- Security

### Key Features
- Metadata-driven: Reads column definitions from the previously generated metadata
- Expanded column names: Uses metadata's expanded_name field (e.g., subject_reference instead of sbj_ref)
- Column descriptions: Each column has a COMMENT with the metadata description
- Table properties: FHIR resource type, domain, sub_domain stored as TBLPROPERTIES
- Type mapping: Converts Glue types to Iceberg-compatible types (string -> STRING, timestamp -> TIMESTAMP, decimal(x,y) -> DECIMAL(x,y), etc.)
- Error handling: try/except for each table creation with table name in error message

---

## [STEP-3] Create Data Migration Notebook

I want to generate code that reads data from Aurora PostgreSQL tables and INSERTs it into the corresponding mapped S3 Tables. This code will be executed in SageMaker Unified Studio's JupyterLab, so please create it as a notebook file on Shared S3 so that it can be used directly in JupyterLab.

### Environment Info
- Region: us-east-1
- Metadata sources: s3://<fhir-data bucket>/metadata/
- Notebook destination: s3://<amazon-sagemaker bucket>/shared/fhir_data_loading.ipynb
- S3 bucket discovery: Find buckets containing "fhir-data" and "amazon-sagemaker" in their names
- JDBC driver: s3://<fhir-data bucket>/lib/postgresql-42.7.1.jar
- Aurora credentials: Retrieved from AWS Secrets Manager (first secret in the list)

### Notebook Generation Method
- Generate the notebook as a Python script that builds the .ipynb JSON programmatically
- Each cell's "source" must be a list of strings with explicit newline characters (e.g., ["line1\n", "line2\n", "line3"])
- Do NOT build source as a single joined string and split by '\n'

### Spark Session Configuration
All notebook cells must use `%%pyspark default.spark` as the cell magic. The first code cell must contain all of the following:
- boto3 session creation, region/account_id retrieval
- Secrets Manager credential retrieval and JDBC URL construction
- SparkSession creation with JDBC JAR config and S3 Tables catalog config
- spark.sql("USE `s3tablescatalog_fhir-bucket`.data") statement

Only set `spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse` — other catalog properties cause errors in SMUS JupyterLab.

```python
import boto3
import json
from pyspark.sql import SparkSession

session = boto3.session.Session()

region = session.region_name
account_id = session.client('sts').get_caller_identity()['Account']
secrets = session.client('secretsmanager').list_secrets()['SecretList']
secret_id = next(s['Name'] for s in secrets if 'FhirDatabase' in s['Name'])
secretsmanager = boto3.client('secretsmanager', region_name=region)
secret = secretsmanager.get_secret_value(SecretId=secret_id)
creds = json.loads(secret['SecretString'])

jdbc_url = f"jdbc:postgresql://{creds['host']}:{creds['port']}/{creds['dbname']}"
driver_s3_path = f"s3://fhir-data-{account_id}-{region}/lib/postgresql-42.7.1.jar"

spark = SparkSession.builder \
    .config("spark.jars", driver_s3_path) \
    .config("spark.driver.extraClassPath", driver_s3_path) \
    .config("spark.executor.extraClassPath", driver_s3_path) \
    .config("spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse",
            f"arn:aws:s3tables:{region}:{account_id}:bucket/fhir-bucket") \
    .getOrCreate()

spark.sql("USE `s3tablescatalog_fhir-bucket`.data")

# Read dataframe from aurora db (JDBC connection)
source_df = spark.read \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("dbtable", "<source_table>") \
    .option("user", creds['username']) \
    .option("password", creds['password']) \
    .option("driver", "org.postgresql.Driver") \
    .load()

# Create temp view
source_df.createOrReplaceTempView("source_table")

# Insert into target table
spark.sql(f"""
INSERT INTO {<target_table>}
SELECT <columns> FROM source_table
""")
```

### Source Table Reading
- Read from Aurora PostgreSQL via JDBC using `spark.read.format("jdbc")`
- The "dbtable" value format: "public.<table_name>" (e.g., public.abc_reg_ptnt)
- The source table name is derived from metadata's original_table_name by removing the `fhir_database_public_` prefix
- Create a reusable helper function read_source_table(table_name) to avoid code duplication

### Data Loading Pattern
Use `INSERT INTO {target_table} SELECT {columns} FROM source_table` pattern:
1. Read source table via JDBC into DataFrame
2. Create temp view from DataFrame (e.g., source_{target_table_name})
3. Execute `spark.sql()` with INSERT INTO ... SELECT with column mapping

### Column Mapping and Type Casting
- Map source abbreviated column names to target expanded names using metadata's expanded_name field (e.g., sbj_ref AS subject_reference)
- Apply CAST expressions where source and target types differ:
  - boolean columns: CAST(col AS BOOLEAN) — e.g., active_indicator, multiple_birth_indicator, primary_source, value_boolean
  - date columns: CAST(col AS DATE) — e.g., birth_date, expiration_date, payment_date, recorded_date
  - decimal columns: CAST(col AS DECIMAL(x,y)) — e.g., total_amount, payment_amount, dose_quantity, value_quantity, position_latitude/longitude
- Columns where original name equals expanded name need no alias

### SQL Statement Rules
- No backslashes in SQL statements
- No special characters in string literals
- Use try/except for each table with table name in error message

### Notebook Content Structure
1. Title markdown cell
2. First code cell: Spark session setup (credentials, JDBC, SparkSession, USE statement)
3. Helper function cell: read_source_table() function
4. Domain-grouped data loading: One markdown header per domain, then one code cell per table
   - Domain order: Administrative, Clinical, Financial, Medication, Security
   - Each cell: read source → create temp view → INSERT INTO with SELECT column mapping → print row count
5. Verification cell: Row counts for all 24 tables with total
6. Sample data cell: Show first few rows from key tables (patient, encounter, observation, claim)

---