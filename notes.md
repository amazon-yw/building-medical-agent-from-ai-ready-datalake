Biomni
- 스탠포드 대학교
- 연구진들이 함께 만든 150개 툴, 59개 DB 등의 소프트웨어를 하나에
- 외부의 Biomedical 리서치에 관련된 것들
- Public 하게 오픈된 API들
- 좋은 점
    - 대부분 데이터베이스
    - 


이제부터 cdk 디렉토리를 만든 뒤 그 디렉토리 안에서 cdk 프로젝트를 만들어보자. 
다음 순서로 us-east-1 리전에 AWS 리소스를 provisioning 하게 구성해줘. 

1/ "fhir-data-<accountId>"라는 이름으로 S3 버킷 생성.
2/ "/Users/yunwoo/Projects/hcls_data_lake_workshop/fhir_data/fhir" 디렉토리 내 ndjson 파일들에 대해 "s3://fhir-data-<accountId>-<region>/data/raw/" 경로 내 s3 업로드.
3/ "/Users/yunwoo/Projects/hcls_data_lake_workshop/fhir_ddl_scripts" 디렉토리 내 sql 파일들에 대해 "s3://fhir-data-<accountId>-<region>/scripts/ddl/" 경로 내 s3 업로드.
4/ "fhir-database" 이름으로 aurora postgresql 데이터베이스 생성.
   -> 이 데이터베이스는 나중에 SageMaker Unified Studio의 노트북 환경에서 접속이 가능해야 함.
   -> 그러므로 관련 IAM Role 생성해둠.
5/ "fhir-table-creator"라는 이름으로 Lambda 함수 생성.
   -> 이 Lambda 함수는 "s3://fhir-data-<accountId>-<region>/scripts/ddl/" 경로 내 sql을 이용하여 "fhir-database" 내에 테이블 생성하도록 동작
6/ "fhir-data-loader"라는 이름으로 Lambda 함수 생성.
   -> 이 Lambda 함수는 "s3://fhir-data-<accountId>-<region>/data/raw/" 경로에 있는 데이터들을 대상 DB 테이블로 Insert 하도록 동작
7/ 5, 6단계에서 만들어진 Lambda 함수를 순서대로 실행하여 DB 준비 완료하도록 함.


여태까지 cdk 프로젝트를 구성해왔어.

# 1. Glue Crawler 구동

# 2. SageMaker Unified Studio - IAM-based Domain 생성

# 3. SageMaker Unified Studio 관련 설정
AmazonSageMakerAdminIAMExecutionRole에 Secrets Manger 관련 권한 부여 - 정책명: SecretsManagerReadWrite

SAGEMAKER_SG=$(aws cloudformation describe-stacks --stack-name FhirDataStack --query 'Stacks[0].Outputs[?OutputKey==`SageMakerSecurityGroupId`].OutputValue' --output text)

--> 메타데이터 생성 요청
Tables in "AwsDataCatalog.fhir_db" are related with patient data.

> 에러 발생 시
Why does it keep throwing errors?





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
7. [IMPORTANT] If the table metadata generation fails and results in "Unknown", please retry it once more.

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

Please write the code referencing the example below to create a Spark session and create tables in S3 Tables. All cells in the notebook must use `%%pyspark default.spark` as the cell magic. Also, the parts that retrieve the region and account_id values and create the Spark session from the example code below must all exist in the very first cell. 

When creating the Spark session with `SparkSession.builder`, only set `spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse` as shown in the sample code below. Do not include any other catalog configuration properties, as they actually cause errors in the SMUS JupyterLab environment.

Before the actual table creation, use the spark.sql("USE `s3tablescatalog_fhir-bucket`.data") statement so that the CREATE TABLE queries can be simplified to just CREATE TABLE <table>. Please configure the `CREATE TABLE` statements to be executed using the `spark.sql()` method. Make sure no SQL statements contain backslashes (\). Wrap COMMENT values in single quotes, and ensure no special characters appear inside them.

Lastly, when splitting the code string by '\n', it can create a single-element list because the string contains literal \n characters instead of actual newlines. So sometimes the line breaks are not properly applied, like this: "%%pyspark default.sparkimport boto3from pyspark.sql import SparkSession". Please fix the line breaks so each statement appears on its own line.

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

### Domain-Based Table Creation
- Administrative: Patient, Practitioner, Organization, Location, PractitionerRole
- Clinical: Procedures, Allergies, Diagnoses, Documents, Encounters, Imaging, Immunizations, Observations, Care Plans, Service Requests, Specimens, Vital Signs
- Financial: Claims, ExplanationOfBenefit
- Medication: Administration, Dispensing, Requests
- Security: Audit tracking

### Key Features
- Metadata-driven: Reads from the generated metadata JSON
- Expanded column names: Uses full names (e.g., subject_reference instead of sbj_ref)
- Column descriptions: Each column has a COMMENT with AI-friendly description
- Table properties: FHIR resource type, domain, subdomain stored as table properties
- Type mapping: Converts Glue types to Iceberg-compatible types
- Error handling: Try-catch for each table creation
- Verification: Lists tables, shows schemas, counts
- Data loading example: Shows how to load data with column mapping

---

## [STEP-3] 데이터 마이그레이션 노트북 생성
I want to generate code that reads data from Aurora PostgreSQL tables and INSERTs it into the corresponding mapped s3 tables. This code will be executed in SageMaker Unified Studio's JupyterLab, so please create it as a notebook file on Shared S3 so that it can be used directly in JupyterLab. Please write the code referencing the example below to create a session, read data, and write it. All notebook cells must use `%%pyspark default.spark` as the cell magic. Also, the parts that create Spark session must all exist in the first cell. 

```python
import boto3
import json

session = boto3.session.Session()

region = session.region_name
account_id = session.client('sts').get_caller_identity()['Account']
secret_id = session.client('secretsmanager').list_secrets()['SecretList'][0]['Name']
secretsmanager = boto3.client('secretsmanager', region_name=region)
secret = secretsmanager.get_secret_value(SecretId=secret_id)
creds = json.loads(secret['SecretString'])

jdbc_url = f"jdbc:postgresql://{creds['host']}:{creds['port']}/{creds['dbname']}"
driver_s3_path = f"s3://fhir-data-{account_id}-{region}/lib/postgresql-42.7.1.jar"

from pyspark.sql import SparkSession

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

### Important Notes
1/ Please construct the queries using an INSERT INTO {target_table} SELECT {columns} FROM source_table pattern, mapping the source columns to the corresponding target table columns. Also, check whether type casting is needed for any columns and include the appropriate CAST expressions where necessary.
2/ Since the source tables are read from Aurora DB, Spark session creation requires JDBC and JAR settings as shown above example. Only set `spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse` in the Spark session config as shown below — other catalog properties cause errors in SMUS JupyterLab.
3/ spark.read must be read via JDBC as shown above example. "dbtable" value will be in the format "public.<table_name>".
4/ Please use spark.sql("USE `s3tablescatalog_fhir-bucket`.data") statement so that the queries can be simplified to just INSERT INTO <table>.
5/ Configure 'INSERT INTO' statements to be executed using `spark.sql()` method. 
6/ Make sure no SQL statements contain backslashes (\). Wrap COMMENT values in single quotes, and ensure no special characters appear inside them.
7/ Lastly, when splitting the code string by '\n', it can create a single-element list because the string contains literal \n characters instead of actual newlines. So please fix the line breaks so each statement appears on its own line.

---


## Create Tables

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("FHIR_DATA_APP") \
    .config("spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse",
            f"arn:aws:s3tables:{region}:{account_id}:bucket/fhir-bucket") \
    .getOrCreate()

spark.sql("USE `s3tablescatalog_fhir-bucket`.data")
spark.sql("SHOW TABLES").show()

# 테이블 생성
spark.sql("""
CREATE TABLE daily_sales (
    sale_date date,
    product_category string,
    sales_price double
)
PARTITIONED BY (month(sale_date))
TBLPROPERTIES ('table_type' = 'iceberg')
""")
```

## Get dataframe from aurora
```python
import boto3
import json

session = boto3.session.Session()

region = session.region_name
account_id = session.client('sts').get_caller_identity()['Account']
secret_id = session.client('secretsmanager').list_secrets()['SecretList'][0]['Name']

secretsmanager = boto3.client('secretsmanager', region_name=region)
secret = secretsmanager.get_secret_value(SecretId=secret_id)
creds = json.loads(secret['SecretString'])

jdbc_url = f"jdbc:postgresql://{creds['host']}:{creds['port']}/{creds['dbname']}"

postgresql_driver_path = f"s3://fhir-data-{account_id}-{region}/lib/postgresql-42.7.1.jar"

# Spark 설정에 추가
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.jars", postgresql_driver_path) \
    .config("spark.driver.extraClassPath", postgresql_driver_path) \
    .config("spark.executor.extraClassPath", postgresql_driver_path) \
    .config("spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse",
            f"arn:aws:s3tables:{region}:{account_id}:bucket/fhir-bucket") \
    .getOrCreate()

# 이제 JDBC 연결
df = spark.read \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("dbtable", "public.xmh_alg_rec") \
    .option("user", creds['username']) \
    .option("password", creds['password']) \
    .option("driver", "org.postgresql.Driver") \
    .load()

df.show(10, False)
```

레코드 없는 테이블
xmh_alg_rec
xmh_aud_trk
xmh_dev_cat
xmh_doc_ref
xmh_img_std
xmh_imz_rec
xmh_pln_doc
xmh_rx_adm
xmh_rx_ord
xmh_sup_dlv
xmh_tm_grp

NULL 값을 갖는 컬럼이 많은 테이블
xmh_loc_reg


## Lake Formation 권한 설정 부분
https://docs.aws.amazon.com/next-generation-sagemaker/latest/userguide/s3-tables-integration.html

Lake Formation에서 S3 Tables의 database에 권한을 부여해줘:
Running aws cli command (using tool: aws):

Service name: lakeformation
Operation name: grant-permissions
Parameters:
- --permissions: ["ALL"]
- --principal: "{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::997924005000:role/service-role/AmazonSageMakerAdminIAMExecutionRole\"}"
- --resource: "{\"Database\":{\"CatalogId\":\"997924005000:s3tablescatalog/fhir-bucket\",\"Name\":\"data\"}}"
- --permissions-with-grant-option: ["ALL"]
Region: us-west-2
Label: Grant CREATE_TABLE on data database in s3tablescatalog/fhir-bucket

```bash
aws lakeformation grant-permissions \
  --region us-west-2 \
  --principal '{"DataLakePrincipalIdentifier":"arn:aws:iam::997924005000:role/service-role/AmazonSageMakerAdminIAMExecutionRole"}' \
  --resource '{"Database":{"CatalogId":"997924005000:s3tablescatalog/fhir-bucket","Name":"data"}}' \
  --permissions '["ALL"]' \
  --permissions-with-grant-option '["ALL"]'
```

## CDK 변경해야 하는 것들
1. CSV 데이터 파일들 워크샵 Asset으로 등록
2. CSV 데이터 핸들링하는 람다 함수들이 워크샵 Asset 이용하도록 코드 변경
3. PostgreSQL Jar 파일들 워크샵 Asset으로 등록
4. PostgreSQL Jar 파일을 S3에 업로드 하는 람다 함수가 워크샵 Asset 이용하도록 코드 변경
5. 모든 람다 함수들의 Python 버전 업
6. EMR Serverless Application 셋업

## 프로젝트 개발
1. EMR Serverless Application에 데이터 쿼리를 수행하는 람다 기반 어플리케이션 개발
2. PubMed 람다 기반 어플리케이션 개발
3. AgentCore Runtime에서 동작하는 Medical Agent 개발
4. Frontend 어플리케이션 개발

## 워크샵 진행순서

### Prerequisite
- Glue Crawler Job Run
- SageMaker Unified Studio - IAM-based domain 생성
    . Project data and administrative control
        . Execution IAM role - Auto-create a new role with admin permissions
- 생성 후 프로젝트 VPC 설정 변경
- 아래 스크립트 수행
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="${AWS_REGION:-us-east-1}"

aws lakeformation grant-permissions \
  --region $REGION \
  --principal "{\"DataLakePrincipalIdentifier\":\"arn:aws:iam::${ACCOUNT_ID}:role/service-role/AmazonSageMakerAdminIAMExecutionRole\"}" \
  --resource "{\"Database\":{\"CatalogId\":\"${ACCOUNT_ID}:s3tablescatalog/fhir-bucket\",\"Name\":\"data\"}}" \
  --permissions '["ALL"]' \
  --permissions-with-grant-option '["ALL"]'

aws iam put-role-policy \
  --role-name AmazonSageMakerAdminIAMExecutionRole \
  --policy-name SecretsManagerReadAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets"
        ],
        "Resource": "*"
      }
    ]
  }'
```
- code editor에서 kiro-cli 설치
```shell
curl -fsSL https://cli.kiro.dev/install | bash

Kiro CLI installer:

Downloading package...
✓ Downloaded and extracted
✓ Package installed successfully

🎉 Installation complete! Happy coding!

Next steps:
Use the command "kiro-cli" to get started!

[participant@CodeEditor workshop]$ kiro-cli

Welcome to Kiro CLI, let's get you signed in!

Press enter to continue to the browser or esc to cancel
```

- git clone https://github.com/amazon-yw/building-medical-agent-from-ai-ready-datalake.git

### LAB-1
- [Glue Crawler] Job Run 하여 PostgreSQL 데이터베이스에 대한 데이터 카탈로그 생성
- [SMUS Notebook] PostgreSQL 내 테이블, 컬럼에 대한 상세 description 생성
- [SMUS Notebook] S3 Tables 내 테이블 DDL 스크립트 생성
- [SMUS Notebook] DDL 스크립트를 읽어서 실제 S3 Tables 테이블 생성하는 Python 생성

### LAB-2
- [SMUS JupyterLab] S3 Tables 테이블 생성 Python 스크립트로 테이블 생성
- [SMUS JupyterLab] 생성된 테이블에 데이터 Migration
- [SMUS JupyterLab] Migration 된 데이터 확인

### LAB-3 - MCP 서버 구축
- EMR Serverless Application
- Tools
- 
- Run Query
- View Schema 
- 

### LAB-4






## MCP Tool 설계안

### 프롬프트
1/ cdk 프로젝트 그리고 바이브코딩으로 aurora db 테이블들에 대한 메타데이터 추출부터 s3 tables 테이블 생성과 데이터 마이그레이션까지 모두 성공적으로 진행했어.
2/ 다음으로는 이렇게 구축된 데이터 레이크와 데이터 메타데이터를 기반으로 medical mcp server를 만들어보려고 해. 이 mcp 서버가 제공하는 툴들은 어떤 것들이 될지 같이 고민해보자.
3/ fhir 데이터레이크가 s3 tables에 테이블로 생성이 되어있어. 이 데이터를 근간으로 emr serverless application을 통해 mcp 서버를 제공하려고 하는데 어떤 툴들을 제공하는게 좋을까? 이 mcp 서버의 사용자는 medical agent 가 될거야. 이 기능들은 모두 워크샵 컨텐츠용으로 제작중으로, 뭔가 시나리오에 맞춰서 기획하고 싶어서 물어보는거야.
4/ financial 부분도 병원에서 중요한 부분이라 추가하면 좋겠고, run_custom_query는 mcp 서버를 사용하게 될 medical agent가 text-to-sql 하는 것을 잘 보여줄 수 있지 않을까 싶어.
5/ tool description에 넣는게 아니라, 데이터 메타데이터 정보를 조회할 수 있는 툴을 추가하면 좋겠어.
6/ 지금까지 mcp 서버 관련하여 같이 정리한 내용을 md파일로 만들어줄 수 있어?
7/ 메타데이터 조회의 경우, s3 tables에 테이블 생성 시 COMMENT로 다양한 메타데이터를 이미 넣어뒀어. 메타데이터 조회할 때 그 정보를 함께 조회하여 응답하는 것이 좋을거 같아.
8/ mcp 서버 개발 작업을 위해 가장 처읍으로 진행할 것은 cdk에 emr serverless app을 셋업하는 것을 진행하자. 동일한 vpc를 사용하며, s3 와 s3 tables, glue 관련 권한이 부여되어야 해. 그리고, sagemaker unified studio의 jupyterlab에서 접근이 가능해야해. 관련된 작업을 진행해줘.

### 1. 환자 조회 (Patient Lookup)

get_patient_summary(patient_id)

- patient_registry + diagnosis_conditions + allergy_intolerances를 JOIN
- 환자 기본정보, 현재 진단, 알레르기 정보를 한번에 반환
- Agent 시나리오: "환자 P12345의 현재 상태를 알려줘"

search_patients(name?, gender?, birth_date_range?, condition?)

- 조건 기반 환자 검색
- Agent 시나리오: "당뇨 진단을 받은 50대 여성 환자 목록"

### 2. 임상 기록 조회 (Clinical Records)

get_encounter_history(patient_id, date_range?, encounter_type?)

- patient_encounters + practitioner_registry + location_registry JOIN
- 진료 이력, 담당의, 진료 장소 포함
- Agent 시나리오: "이 환자의 최근 6개월 입원 기록"

get_clinical_observations(patient_id, observation_type?, date_range?)

- clinical_observations 테이블 조회 (활력징후, 검사결과 등)
- Agent 시나리오: "이 환자의 혈압 추이를 보여줘"

get_medications(patient_id, active_only?)

- medication_administrations + medical_devices JOIN
- 현재/과거 투약 이력
- Agent 시나리오: "현재 복용 중인 약물 목록과 상호작용 위험"

### 3. 진단/검사 (Diagnostics)

get_diagnosis_history(patient_id, category?)

- diagnosis_conditions + clinical_procedures JOIN
- Agent 시나리오: "이 환자의 만성질환 이력"

get_immunization_records(patient_id)

- immunization_records 조회
- Agent 시나리오: "백신 접종 이력과 미접종 항목"

### 4. 재무/보험 (Financial - 워크샵 차별화 포인트)

get_claim_summary(patient_id?, date_range?, status?)

- financial_claims + explanation_of_benefits JOIN
- Agent 시나리오: "이 환자의 미결제 청구 건"

analyze_cost_by_condition(condition_code?, department?, date_range?)

- 질환별/부서별 비용 분석 (집계 쿼리)
- Agent 시나리오: "당뇨 환자의 평균 치료 비용 추이"

### 5. 분석/집계 (Analytics - 워크샵 하이라이트)

get_population_health_metrics(condition?, region?, age_group?)

- 다중 테이블 집계 - 인구 건강 지표
- Agent 시나리오: "지역별 당뇨 유병률과 합병증 발생률"

detect_care_gaps(patient_id)

- care_plans + immunization_records + clinical_observations 비교
- 권장 검진/접종 vs 실제 수행 비교
- Agent 시나리오: "이 환자에게 누락된 예방 조치가 있나?"

## 워크샵 시나리오 흐름 제안

[워크샵 참가자]
    ↓
1단계: "65세 이상 당뇨 환자 중 최근 6개월 내 입원한 환자를 찾아줘"
    → search_patients + get_encounter_history

2단계: "그 중 김OO 환자의 전체 임상 요약을 보여줘"
    → get_patient_summary + get_medications + get_diagnosis_history

3단계: "이 환자의 치료 비용 추이와 보험 청구 현황은?"
    → get_claim_summary + analyze_cost_by_condition

4단계: "이 환자에게 빠진 예방 조치나 검진이 있어?"
    → detect_care_gaps

5단계: "전체 당뇨 환자 집단의 건강 지표를 분석해줘"
    → get_population_health_metrics


## 기술 아키텍처

Medical Agent (Bedrock)
    ↓ MCP Protocol
MCP Server (FastAPI/SSE)
    ↓ Tool 호출
EMR Serverless (Spark SQL)
    ↓ Iceberg REST Catalog
S3 Tables (fhir-bucket/data/*)


## 추천 우선순위

워크샵 시간이 제한적이라면 이 순서로 구현하는 걸 추천합니다:

1. get_patient_summary - 가장 기본, 즉시 임팩트
2. search_patients - 자연어 → SQL 변환 데모
3. get_encounter_history - 다중 테이블 JOIN 시연
4. get_medications - 의료 도메인 특화
5. detect_care_gaps - Agent의 추론 능력 시연 (하이라이트)

총 몇 개 정도의 tool을 구현할 계획인가요? 그리고 EMR Serverless에서 MCP 서버를 어떤 형태로 띄울지 (Spark Connect? REST API wrapper?) 방향이 있으면 더 구체적으로 설계해드릴 수 있습니다.