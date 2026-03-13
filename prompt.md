# SMUS Data Agent Prompts

---

## [STEP-1] 원본 테이블의 메타데이터 추론

Tables in "AwsDataCatalog.fhir_db" are related with patient data.
Please create metadata for the tables in "AwsDataCatalog.fhir_db". The reason I'm asking for metadata creation first is that I want to build tables that AI can 
understand effectively. For AI to work well with the data, comprehensive metadata for each table and column is essential. I'll use this metadata later when creating 
tables in S3 Tables to build the data lake. Since there are 24 tables in "AwsDataCatalog.fhir_db", the response might be quite huge, so please create the actual Python
code to generate the comprehensive metadata for making it concise and efficient to avoid any issues. Python code should use "boto3.client('glue')" not pyspark.

### Environment Info
- Region: us-west-2
- S3 Bucket: Use the S3 bucket that contains "fhir-data" in its name
- S3 Prefix: metadata/
- Glue Database: fhir_db

### What the Code Generates:
1. Comprehensive Metadata Structure
- Domain Classification: Groups tables by healthcare domains (Administrative, Clinical, Financial, Medication, Security)
- Column-Level Details: For each of the ~498 columns across 24 tables:
  - Full expanded names (e.g., rid → resource_id, sbj_ref → subject_reference)
  - Detailed descriptions
  - Semantic categories (identifier, reference, temporal, coding, status, value, demographics, address, financial, dosage, device, document, narrative, etc.)
  - AI-friendly tags for search and discovery
  - Data types and nullability
- Common abbreviated column patterns should be mapped comprehensively (e.g., _ref suffix → reference, _sys suffix → code system, _cd suffix → code value _dsp suffix → display text, _dts suffix → datetime, _txt suffix → free text)
2. Relationship Mapping
- Identifies foreign key relationships between tables via reference columns (_ref suffix)
- Maps reference columns to their target tables (e.g., sbj_ref → patient, evt_ref → encounter, prf_ref → practitioner, org_ref → organization, loc_ref → location, med_ref → medication, clm_ref → claim)
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
- For tables and columns where the mapping is difficult to infer, keep the original names as-is and use pattern-based inference from suffixes.
6. Domain-Based Table Classification (actual table prefix mapping)
- Administrative
- Clinical
- Financial
- Medication
- Security
7. [IMPORTANT] If metadata inference for any table results in "Unknown" fields, the code should automatically retry that table's inference (max 1 retry) before falling back to raw column names.

### Why This Approach?
Instead of printing huge amounts of text (which would be overwhelming), the code:
- Processes efficiently: Iterates through all 24 tables programmatically
- Stores persistently: Saves to S3 for reuse across sessions
- Stays accessible: Keeps metadata in the fhir_metadata variable for immediate use
- Provides summaries: Shows progress per table with column count and unknown column status during execution

### Next Steps for S3 Tables Creation
- Load metadata: fhir_metadata['tables']['table_name']
- Create S3 Tables: Use column descriptions and types from metadata
- Set up relationships: Leverage the relationship mappings and JOIN hints
- Enable AI discovery: Use tags and semantic categories for semantic search

---

## [STEP-2] 생성된 메타데이터로 테이블 생성 노트북 작성

I want to create tables in S3 Tables based on the generated metadata. For the tables created in S3 Tables, use full, descriptive names for all tables and columns instead of abbreviations like in the source tables to improve readability. I'd like to follow along with the table creation process in a SageMaker Unified Studio JupyterLab notebook environment. So please create/save it as a notebook file on Shared S3 so that it can be opened and used directly in JupyterLab.

### Environment Info
- Region: us-west-2
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

## [STEP-3] 데이터 마이그레이션 노트북 생성

I want to generate code that reads data from Aurora PostgreSQL tables and INSERTs it into the corresponding mapped S3 Tables. This code will be executed in SageMaker Unified Studio's JupyterLab, so please create it as a notebook file on Shared S3 so that it can be used directly in JupyterLab.

### Environment Info
- Region: us-west-2
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
secret_id = session.client('secretsmanager').list_secrets()['SecretList'][0]['Name']
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