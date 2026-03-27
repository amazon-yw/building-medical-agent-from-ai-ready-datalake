# SMUS Data Agent 프롬프트

---

## [STEP-1] 원본 테이블의 메타데이터 추론

"AwsDataCatalog.fhir_db"에 있는 테이블들은 환자 데이터와 관련된 테이블입니다.
"AwsDataCatalog.fhir_db"의 테이블들에 대한 메타데이터를 생성해주세요. 메타데이터 생성을 먼저 요청하는 이유는 AI가 효과적으로 이해할 수 있는 테이블을 구축하고 싶기 때문입니다. AI가 데이터를 잘 활용하려면 각 테이블과 컬럼에 대한 포괄적인 메타데이터가 필수적입니다. 이 메타데이터는 나중에 데이터 레이크를 구축하기 위해 S3 Tables에 테이블을 생성할 때 사용할 것입니다. "AwsDataCatalog.fhir_db"에는 24개의 테이블이 있어서 응답이 매우 클 수 있으므로, 간결하고 효율적으로 처리하기 위해 포괄적인 메타데이터를 생성하는 실제 Python 코드를 작성해주세요. Python 코드는 pyspark가 아닌 "boto3.client('glue')"를 사용해야 합니다.

### 환경 정보
- 리전: us-east-1
- S3 버킷: 이름에 "fhir-data"가 포함된 S3 버킷 사용
- S3 접두사: metadata/
- Glue 데이터베이스: fhir_db

### 코드가 생성하는 내용:
1. 포괄적인 메타데이터 구조
- 도메인 분류: 테이블을 의료 도메인별로 그룹화 (Administrative, Clinical, Financial, Medication, Security)
- 컬럼 수준 상세 정보: 24개 테이블의 약 498개 컬럼 각각에 대해:
  - 전체 확장 이름 (예: rid → resource_id, sbj_ref → subject_reference)
  - 상세 설명
  - 시맨틱 카테고리 (identifier, reference, temporal, coding, status, value, demographics, address, financial, dosage, device, document, narrative 등)
  - 검색 및 탐색을 위한 AI 친화적 태그
  - 데이터 타입 및 null 허용 여부
- 일반적인 축약 컬럼 패턴을 포괄적으로 매핑해야 함 (예: ref 접미사 → reference, sys 접미사 → code system, cd 접미사 → code value, dsp 접미사 → display text, dts 접미사 → datetime, txt 접미사 → free text)
2. 관계 매핑
- 참조 컬럼(_ref 접미사)을 통해 테이블 간 외래 키 관계 식별
- 참조 컬럼을 대상 테이블에 매핑 (예: sbj_ref → patient, evt_ref → encounter, prf_ref → practitioner, org_ref → organization, loc_ref → location, med_ref → medication, clm_ref → claim)
- 분석 쿼리를 위한 JOIN 힌트 문자열 제공
- 분석을 위한 적절한 조인 전략 활성화
3. 분석 힌트
- 시계열 분석에 적합한 테이블 표시 (boolean + 특정 시간 컬럼)
- 테이블별 교차 참조 컬럼 식별
- 테이블별 적절한 분석 패턴 제안 (예: disease_prevalence, visit_frequency, prescription_trends)
4. 출력 파일 (S3에 저장)
- fhir_db_metadata.json: 모든 테이블의 완전한 메타데이터 (200KB 이상의 구조화된 데이터)
- README.md: 사용 예제가 포함된 사람이 읽을 수 있는 문서 (메타데이터 로딩 및 쿼리를 위한 Python 코드 스니펫)
- field_mappings.json: 테이블 간 사용 추적이 포함된 필드 축약어 빠른 참조
5. 명명 규칙
- 테이블 이름과 컬럼 이름은 camelCase 대신 snake_case(밑줄 포함)를 사용해야 합니다.
- 매핑을 추론하기 어려운 테이블과 컬럼의 경우, 원래 이름을 그대로 유지하고 접미사 기반 패턴 추론을 사용합니다.
6. 도메인 기반 테이블 분류 (실제 테이블 접두사 매핑)
- Administrative
- Clinical
- Financial
- Medication
- Security
7. [중요] 테이블의 메타데이터 추론 결과에 "Unknown" 필드가 있는 경우, 코드가 해당 테이블의 추론을 자동으로 재시도(최대 1회)한 후 원시 컬럼 이름으로 폴백해야 합니다.

### [핵심] MCP 서버 통합을 위한 출력 파일 스키마 사양

생성된 fhir_db_metadata.json 파일은 Lambda 콜드 스타트 시 MCP 서버의 metadata_loader.py에서 사용됩니다.
JSON 구조는 다음 스키마를 정확히 따라야 합니다. 어떤 편차도 MCP 도구 체인을 깨뜨립니다.

#### 최상위 구조
```json
{
  "generated_at": "ISO-8601 타임스탬프 문자열",
  "source_database": "fhir_db",
  "source_catalog": "AwsDataCatalog",
  "region": "us-east-1",
  "total_tables": 24,
  "total_columns": 498,
  "domains": { ... },
  "tables": { ... }
}
```

#### domains 객체
키는 첫 글자가 대문자인 도메인 이름 (예: "Clinical", "Administrative", "Financial", "Medication", "Security"). 각 값:
```json
{
  "Clinical": {
    "table_count": 13,
    "tables": ["encounter", "condition", "observation", "procedure", ...]
  }
}
```

- tables 배열은 snake_case 테이블 키 이름을 포함 (최상위 tables 객체에서 사용되는 것과 동일한 키).

#### tables 객체
키는 snake_case 테이블 이름 (예: "encounter", "patient", "medication_request"). 각 값:
```json
{
  "original_table_name": "fhir_database_public_abc_enc",
  "snake_name": "encounter",
  "fhir_resource": "Encounter",
  "domain": "Clinical",
  "sub_domain": "Encounters",
  "description": "사람이 읽을 수 있는 테이블 설명",
  "column_count": 17,
  "columns": { ... }
}
```

테이블별 필수 필드:
| 필드 | 타입 | 설명 |
|---|---|---|
| original_table_name | string | 원본 Glue 테이블 이름 |
| snake_name | string | 정규화된 snake_case 이름 (키와 동일) |
| fhir_resource | string | FHIR 리소스 타입 (예: "Encounter", "Patient") |
| domain | string | 도메인 분류 (domains의 키와 일치해야 함) |
| sub_domain | string | 하위 도메인 레이블 |
| description | string | 사람이 읽을 수 있는 테이블 설명 |
| column_count | integer | 컬럼 수 |
| columns | object | 컬럼 메타데이터 (아래 참조) |

#### columns 객체 (각 테이블 내부에 중첩)
키는 Glue/Athena 테이블에 존재하는 실제 축약 컬럼 이름 (예: "sbj_ref", "prd_ed_dts", "rid"). 각 값:
```json
{
  "expanded_name": "subject_reference",
  "description": "환자(주체)에 대한 참조",
  "semantic_category": "reference",
  "tags": ["patient", "subject", "foreign_key"],
  "references_table": "patient",
  "original_name": "sbj_ref",
  "data_type": "string",
  "nullable": true
}
```

컬럼별 필수 필드:
| 필드 | 타입 | 설명 |
|---|---|---|
| expanded_name | string | snake_case의 전체 시맨틱 이름 (예: "subject_reference", "period_start_datetime", "resource_id") |
| description | string | 사람이 읽을 수 있는 컬럼 설명 |
| semantic_category | string | 다음 중 하나: identifier, reference, temporal, coding, status, value, demographics, address, financial, dosage, device, document, narrative |
| tags | array of strings | AI 친화적 검색 태그 |
| original_name | string | 원본 축약 컬럼 이름 (키와 동일) |
| data_type | string | Spark/Glue 데이터 타입 (예: "string", "timestamp", "double", "bigint") |
| nullable | boolean | 컬럼의 null 허용 여부 |

조건부 필드:
| 필드 | 타입 | 필요 시점 |
|---|---|---|
| references_table | string | 참조 컬럼인 경우에만 (semantic_category == "reference"). 값은 최상위 tables 객체의 유효한 키여야 함 (예: "patient", "encounter", "practitioner") |

#### 주요 expanded_name 규칙
MCP 서버의 find_column() 함수는 expanded_name으로 컬럼을 조회합니다. 해당 개념이 적용되는 모든 테이블에서 다음 시맨틱 이름을 일관되게 사용해야 합니다:

| 시맨틱 개념 | expanded_name | 일반적인 축약 패턴 |
|---|---|---|
| 리소스 ID | resource_id | rid |
| 주체/환자 참조 | subject_reference | sbj_ref |
| 환자 참조 | patient_reference | pat_ref |
| 진료 참조 | encounter_reference | evt_ref, enc_ref |
| 의사 참조 | practitioner_reference | prf_ref |
| 기관 참조 | organization_reference | org_ref |
| 위치 참조 | location_reference | loc_ref |
| 상태 | status | sts, status |
| 코드 표시명 | code_display | cd_dsp, code_dsp |
| 카테고리 표시명 | category_display | ctg_dsp |
| 기간 시작 | period_start 또는 period_start_datetime | prd_st_dts |
| 기간 종료 | period_end 또는 period_end_datetime | prd_ed_dts |
| 유효 일시 | effective_datetime | eff_dts |
| 발병 일시 | onset_datetime | ons_dts |
| 작성 일시 | authored_datetime | ath_dts |
| 생년월일 | birth_date | bth_dt |
| 성별 | gender | gnd |
| 이름(이름) | name_given | nm_gvn |
| 이름(성) | name_family | nm_fml |
| 임상 상태 | clinical_status 또는 clinical_status_code | cln_sts_cd |
| 청구 기간 시작 | billable_period_start | blb_prd_st |

│ **참고**: 위의 축약 컬럼 이름은 예시입니다. 실제 축약 이름은 AI가 추론하므로 워크숍 참가자마다 다를 수 있습니다. 중요한 것은 expanded_name이 위의 규칙을 따라야 MCP 서버의 find_column()이 올바르게 해석할 수 있다는 것입니다.

### 이 접근 방식을 사용하는 이유
방대한 양의 텍스트를 출력하는 대신(압도적일 수 있음), 코드는:
- 효율적으로 처리: 24개 테이블을 프로그래밍 방식으로 반복
- 영구 저장: 세션 간 재사용을 위해 S3에 저장
- 접근성 유지: 즉시 사용을 위해 fhir_metadata 변수에 메타데이터 유지
- 요약 제공: 실행 중 테이블별 진행 상황을 컬럼 수 및 unknown 컬럼 상태와 함께 표시

### S3 Tables 생성을 위한 다음 단계
- 메타데이터 로드: fhir_metadata['tables']['table_name']
- S3 Tables 생성: 메타데이터의 컬럼 설명과 타입 사용
- 관계 설정: 관계 매핑과 JOIN 힌트 활용
- AI 탐색 활성화: 시맨틱 검색을 위한 태그와 시맨틱 카테고리 사용

---

## [STEP-2] 생성된 메타데이터로 테이블 생성 노트북 작성

생성된 메타데이터를 기반으로 S3 Tables에 테이블을 생성하고 싶습니다. S3 Tables에 생성되는 테이블은 소스 테이블의 축약어 대신 모든 테이블과 컬럼에 대해 완전하고 설명적인 이름을 사용하여 가독성을 높입니다. SageMaker Unified Studio JupyterLab 노트북 환경에서 테이블 생성 과정을 따라가고 싶습니다. 따라서 JupyterLab에서 직접 열어서 사용할 수 있도록 Shared S3에 노트북 파일로 생성/저장해주세요.

### 환경 정보
- 리전: us-east-1
- 메타데이터 소스: s3://<fhir-data 버킷>/metadata/
- 노트북 저장 위치: s3://<amazon-sagemaker 버킷>/shared/fhir_s3tables_creation.ipynb
- S3 버킷 탐색: 이름에 "fhir-data"와 "amazon-sagemaker"가 포함된 버킷 찾기

### 노트북 생성 방법
- 노트북을 .ipynb JSON을 프로그래밍 방식으로 빌드하는 Python 스크립트로 생성 (수동으로 JSON 작성하지 않음)
- 적절한 노트북 셀 구조 사용: 각 셀의 "source"는 JupyterLab에서 적절한 줄 바꿈을 보장하기 위해 명시적 개행 문자가 포함된 문자열 목록이어야 함
- 생성된 .ipynb 파일을 SageMaker 공유 S3 버킷에 업로드

### Spark 세션 설정
아래 예제를 참조하여 Spark 세션을 생성하고 S3 Tables에 테이블을 생성하는 코드를 작성해주세요. 노트북의 모든 셀은 `%%pyspark default.spark`를 셀 매직으로 사용해야 합니다. 또한 아래 예제 코드에서 region과 account_id 값을 가져오고 Spark 세션을 생성하는 부분은 모두 첫 번째 코드 셀에 있어야 합니다.

`SparkSession.builder`로 Spark 세션을 생성할 때, 아래 샘플 코드에 표시된 대로 `spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse`만 설정하세요. 다른 카탈로그 설정 속성은 SMUS JupyterLab 환경에서 실제로 오류를 발생시킵니다.

실제 테이블 생성 전에 `spark.sql("USE `s3tablescatalog_fhir-bucket`.data")` 문을 사용하여 `CREATE TABLE` 쿼리를 `CREATE TABLE <table>`로 간소화할 수 있도록 합니다.

```python
import boto3
from pyspark.sql import SparkSession

session = boto3.session.Session()

# 환경 정보 가져오기
region = session.region_name
account_id = session.client('sts').get_caller_identity()['Account']

# Spark 세션 생성
spark = SparkSession.builder \
    .appName("FHIR_DATA_APP") \
    .config("spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse",
            f"arn:aws:s3tables:{region}:{account_id}:bucket/fhir-bucket") \
    .getOrCreate()

spark.sql("USE `s3tablescatalog_fhir-bucket`.data")

# DDL 스크립트 읽기
...

# 테이블 생성
spark.sql(<create statement>)
```

### SQL 문 규칙
- `spark.sql()` 메서드를 사용하여 `CREATE TABLE` 문 실행
- SQL 문에 백슬래시가 포함되지 않도록 할 것
- `COMMENT` 값은 작은따옴표로 감싸고, 내부에 특수 문자(아포스트로피, 백슬래시, 개행)가 나타나지 않도록 — 설명을 정리하는 sanitize 함수 사용
- 멱등 실행을 위해 `CREATE TABLE IF NOT EXISTS` 사용

### 노트북 셀 구조 (중요)
- 노트북 셀 소스를 빌드할 때, 각 줄이 적절한 개행 문자가 추가된 소스 목록의 별도 문자열 요소인지 확인 (예: ["line1\n", "line2\n", "line3"])
- 소스를 단일 결합 문자열로 빌드한 후 '\n'으로 분할하지 마세요 — 이렇게 하면 리터럴 백슬래시-n 문제가 발생하여 모든 코드가 한 줄로 합쳐짐

### 노트북 내용 구조
1. 제목 마크다운 셀
2. 첫 번째 코드 셀: Spark 세션 설정 (boto3 import, region/account_id 조회, SparkSession 생성, USE 문)
3. 선택적 정리 셀: DROP TABLE 문 (주석 처리)
4. 도메인별 테이블 생성: 도메인별 마크다운 헤더 하나, 그 다음 테이블별 try/except 오류 처리가 포함된 코드 셀 하나
5. 검증 셀: SHOW TABLES, 주요 테이블에 대한 DESCRIBE TABLE
6. 컬럼 매핑 참조 셀: 테이블별 원본 축약 이름에서 확장 이름으로의 매핑 딕셔너리 (데이터 로딩용)
7. 데이터 로딩 예제 셀: 소스에서 읽기, 컬럼 이름 변경, S3 Tables에 쓰기 방법 표시 (주석 처리)

### 도메인 기반 테이블 생성 순서
- Administrative
- Clinical
- Financial
- Medication
- Security

### 주요 기능
- 메타데이터 기반: 이전에 생성된 메타데이터에서 컬럼 정의를 읽음
- 확장된 컬럼 이름: 메타데이터의 expanded_name 필드 사용 (예: sbj_ref 대신 subject_reference)
- 컬럼 설명: 각 컬럼에 메타데이터 설명이 포함된 COMMENT
- 테이블 속성: FHIR 리소스 타입, 도메인, sub_domain이 TBLPROPERTIES로 저장
- 타입 매핑: Glue 타입을 Iceberg 호환 타입으로 변환 (string -> STRING, timestamp -> TIMESTAMP, decimal(x,y) -> DECIMAL(x,y) 등)
- 오류 처리: 각 테이블 생성에 대해 테이블 이름이 포함된 오류 메시지와 함께 try/except

---

## [STEP-3] 데이터 마이그레이션 노트북 생성

Aurora PostgreSQL 테이블에서 데이터를 읽어 대응하는 매핑된 S3 Tables에 INSERT하는 코드를 생성하고 싶습니다. 이 코드는 SageMaker Unified Studio의 JupyterLab에서 실행될 것이므로, JupyterLab에서 직접 사용할 수 있도록 Shared S3에 노트북 파일로 생성해주세요.

### 환경 정보
- 리전: us-east-1
- 메타데이터 소스: s3://<fhir-data 버킷>/metadata/
- 노트북 저장 위치: s3://<amazon-sagemaker 버킷>/shared/fhir_data_loading.ipynb
- S3 버킷 탐색: 이름에 "fhir-data"와 "amazon-sagemaker"가 포함된 버킷 찾기
- JDBC 드라이버: s3://<fhir-data 버킷>/lib/postgresql-42.7.1.jar
- Aurora 자격 증명: AWS Secrets Manager에서 조회 (목록의 첫 번째 시크릿)

### 노트북 생성 방법
- 노트북을 .ipynb JSON을 프로그래밍 방식으로 빌드하는 Python 스크립트로 생성
- 각 셀의 "source"는 명시적 개행 문자가 포함된 문자열 목록이어야 함 (예: ["line1\n", "line2\n", "line3"])
- 소스를 단일 결합 문자열로 빌드한 후 '\n'으로 분할하지 마세요

### Spark 세션 설정
모든 노트북 셀은 `%%pyspark default.spark`를 셀 매직으로 사용해야 합니다. 첫 번째 코드 셀에는 다음이 모두 포함되어야 합니다:
- boto3 세션 생성, region/account_id 조회
- Secrets Manager 자격 증명 조회 및 JDBC URL 구성
- JDBC JAR 설정과 S3 Tables 카탈로그 설정이 포함된 SparkSession 생성
- spark.sql("USE `s3tablescatalog_fhir-bucket`.data") 문

`spark.sql.catalog.s3tablescatalog_fhir-bucket.warehouse`만 설정하세요 — 다른 카탈로그 속성은 SMUS JupyterLab에서 오류를 발생시킵니다.

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

# Aurora DB에서 데이터프레임 읽기 (JDBC 연결)
source_df = spark.read \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("dbtable", "<source_table>") \
    .option("user", creds['username']) \
    .option("password", creds['password']) \
    .option("driver", "org.postgresql.Driver") \
    .load()

# 임시 뷰 생성
source_df.createOrReplaceTempView("source_table")

# 대상 테이블에 삽입
spark.sql(f"""
INSERT INTO {<target_table>}
SELECT <columns> FROM source_table
""")
```

### 소스 테이블 읽기
- `spark.read.format("jdbc")`를 사용하여 Aurora PostgreSQL에서 JDBC로 읽기
- "dbtable" 값 형식: "public.<table_name>" (예: public.abc_reg_ptnt)
- 소스 테이블 이름은 메타데이터의 original_table_name에서 `fhir_database_public_` 접두사를 제거하여 도출
- 코드 중복을 피하기 위해 재사용 가능한 헬퍼 함수 read_source_table(table_name) 생성

### 데이터 로딩 패턴
`INSERT INTO {target_table} SELECT {columns} FROM source_table` 패턴 사용:
1. JDBC를 통해 소스 테이블을 DataFrame으로 읽기
2. DataFrame에서 임시 뷰 생성 (예: source_{target_table_name})
3. 컬럼 매핑이 포함된 INSERT INTO ... SELECT로 `spark.sql()` 실행

### 컬럼 매핑 및 타입 캐스팅
- 메타데이터의 expanded_name 필드를 사용하여 소스 축약 컬럼 이름을 대상 확장 이름으로 매핑 (예: sbj_ref AS subject_reference)
- 소스와 대상 타입이 다른 경우 CAST 표현식 적용:
  - boolean 컬럼: CAST(col AS BOOLEAN) — 예: active_indicator, multiple_birth_indicator, primary_source, value_boolean
  - date 컬럼: CAST(col AS DATE) — 예: birth_date, expiration_date, payment_date, recorded_date
  - decimal 컬럼: CAST(col AS DECIMAL(x,y)) — 예: total_amount, payment_amount, dose_quantity, value_quantity, position_latitude/longitude
- 원본 이름과 확장 이름이 같은 컬럼은 별칭 불필요

### SQL 문 규칙
- SQL 문에 백슬래시 없음
- 문자열 리터럴에 특수 문자 없음
- 각 테이블에 대해 테이블 이름이 포함된 오류 메시지와 함께 try/except 사용

### 노트북 내용 구조
1. 제목 마크다운 셀
2. 첫 번째 코드 셀: Spark 세션 설정 (자격 증명, JDBC, SparkSession, USE 문)
3. 헬퍼 함수 셀: read_source_table() 함수
4. 도메인별 데이터 로딩: 도메인별 마크다운 헤더 하나, 그 다음 테이블별 코드 셀 하나
   - 도메인 순서: Administrative, Clinical, Financial, Medication, Security
   - 각 셀: 소스 읽기 → 임시 뷰 생성 → SELECT 컬럼 매핑으로 INSERT INTO → 행 수 출력
5. 검증 셀: 24개 전체 테이블의 행 수와 합계
6. 샘플 데이터 셀: 주요 테이블(patient, encounter, observation, claim)의 처음 몇 행 표시

---
