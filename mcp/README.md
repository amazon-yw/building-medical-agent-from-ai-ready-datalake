# Medical FHIR MCP Server

FHIR 데이터 레이크를 위한 MCP(Model Context Protocol) 서버입니다. AgentCore Gateway를 통해 AI Agent가 S3 Tables의 FHIR 데이터를 Spark SQL로 조회할 수 있습니다.

## Architecture

```
MCP Client (Claude Desktop / Amazon Q / Bedrock Agent)
    → AgentCore Gateway (MCP endpoint, Cognito OAuth)
        → Lambda (Tool dispatcher)
            → EMR Serverless (Livy endpoint, Spark SQL)
                → S3 Tables (Iceberg, 24 FHIR tables)
```

## Project Structure

```
mcp/
├── handler.py              # Lambda entry point - tool name routing
├── emr_client.py           # EMR Serverless Livy bridge (SigV4 signed HTTP)
├── requirements.txt        # botocore, awscrt, requests
└── tools/
    ├── patient.py           # get_patient_summary, search_patients
    ├── clinical.py          # get_encounter_history, get_clinical_observations,
    │                          get_medications, get_diagnosis_history
    ├── financial.py         # get_claim_summary
    ├── analytics.py         # detect_care_gaps, get_population_health_metrics
    ├── schema_discovery.py  # list_tables, get_table_schema, get_table_relationships
    └── query.py             # run_custom_query
```

## Tools (13)

| Category | Tool | Description |
|----------|------|-------------|
| Patient | `get_patient_summary` | 환자 종합 요약 (기본정보 + 진단 + 알레르기 + 투약) |
| Patient | `search_patients` | 조건 기반 환자 검색 (이름, 성별, 나이, 질환) |
| Clinical | `get_encounter_history` | 진료 이력 (의사, 장소 포함) |
| Clinical | `get_clinical_observations` | 관찰/측정 데이터 (활력징후, 검사결과) |
| Clinical | `get_medications` | 투약 이력 (처방 + 투여 기록) |
| Clinical | `get_diagnosis_history` | 진단 이력 (질환 + 시술) |
| Financial | `get_claim_summary` | 청구/보험 요약 |
| Analytics | `detect_care_gaps` | 케어 갭 분석 (누락 예방접종, 미수행 검진) |
| Analytics | `get_population_health_metrics` | 인구 건강 지표 집계 |
| Schema | `list_tables` | 테이블 목록 + 메타데이터 |
| Schema | `get_table_schema` | 컬럼 구조 + COMMENT 메타데이터 |
| Schema | `get_table_relationships` | 테이블 간 FK 관계 추론 |
| Query | `run_custom_query` | Text-to-SQL (SELECT only, LIMIT 100) |

## Data Lake

- **S3 Tables**: `s3tablescatalog.fhir-bucket.data` namespace
- **24 FHIR tables**: Synthea 생성 데이터, 450,000+ records
- **6 domains**: Administrative, Clinical, Medication, Diagnostic, Care, Financial/Document

## Deployment

`/notebooks` 디렉토리의 JupyterLab 노트북을 순서대로 실행합니다.

| Notebook | Description |
|----------|-------------|
| `01_deploy_mcp_lambda.ipynb` | Lambda 패키징 + 배포 + 테스트 |
| `02_setup_agentcore_gateway.ipynb` | Cognito + Gateway + Target 설정 |

### Prerequisites

- CDK 인프라 배포 완료 (Aurora, S3 Tables, EMR Serverless)
- EMR Serverless Application이 `STARTED` 상태
- Python 3.13 Lambda runtime

### Environment Variables (Lambda)

| Variable | Description |
|----------|-------------|
| `EMR_APPLICATION_ID` | EMR Serverless Application ID |
| `EMR_EXECUTION_ROLE_ARN` | EMR Serverless Execution Role ARN |

## How It Works

1. AgentCore Gateway가 MCP 프로토콜로 tool 호출을 수신
2. Lambda `handler.py`가 tool name으로 해당 함수를 라우팅
3. 각 tool 함수가 Spark SQL을 생성
4. `emr_client.py`가 Livy endpoint에 SigV4 서명된 HTTP 요청으로 SQL 실행
5. Livy 세션은 warm Lambda에서 모듈 변수로 캐싱 (cold start 시에만 새 세션 생성)
6. 결과를 JSON으로 반환

## Demo Scenarios

```
의사: "당뇨 진단받은 60대 환자 목록 보여줘"
  → search_patients(condition_code="diabetes", birth_date_from="1956-01-01", birth_date_to="1966-12-31")

의사: "이 환자 상태 요약해줘"
  → get_patient_summary(patient_id="xxx")

의사: "최근 혈당 수치 추이는?"
  → get_clinical_observations(patient_id="xxx", observation_code="glucose")

의사: "가장 많이 처방되는 약물 top 10은?"
  → list_tables(domain="medication")
  → get_table_schema("medication_request")
  → run_custom_query("SELECT medication_code_display, COUNT(*) ...")
```
