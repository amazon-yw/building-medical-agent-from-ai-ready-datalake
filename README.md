# Building Medical AI Agent from AI-Ready Data Lake

FHIR 의료 데이터 레이크 기반 AI 에이전트를 구축하는 워크샵입니다. Synthea 합성 데이터를 Aurora PostgreSQL에서 S3 Tables(Iceberg)로 마이그레이션하고, MCP 서버를 통해 AI 에이전트가 자연어로 의료 데이터를 조회·분석할 수 있는 엔드투엔드 파이프라인을 구축합니다.

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Streamlit UI   │────▶│  AgentCore Runtime   │────▶│  Strands Agent      │
│  (EC2:8501)     │ SSE │  (Container/ARM64)   │     │  (Claude Sonnet 4)  │
└─────────────────┘     └──────────────────────┘     └────────┬────────────┘
                                                              │ MCP Protocol
                                                    ┌────────▼────────────┐
                                                    │  AgentCore Gateway  │
                                                    │  (Cognito OAuth)    │
                                                    └────────┬────────────┘
                                                              │
                                                    ┌────────▼────────────┐
                                                    │  Lambda MCP Server  │
                                                    │  (13 Tools)         │
                                                    └────────┬────────────┘
                                                              │ Livy / Spark SQL
                                                    ┌────────▼────────────┐
                                                    │  EMR Serverless     │
                                                    └────────┬────────────┘
                                                              │ Iceberg REST Catalog
                                                    ┌────────▼────────────┐
                                                    │  S3 Tables          │
                                                    │  (24 FHIR Tables)   │
                                                    └─────────────────────┘
```

## Project Structure

```
.
├── cdk/                          # CDK 인프라 (Aurora, S3, EMR, VPC, EC2)
│   ├── cdk/fhir_data_stack.py    # 메인 스택
│   └── lambda/                   # 인프라 Lambda (table_creator, data_loader)
├── data/
│   ├── fhir/                     # Synthea FHIR ndjson 원본 데이터
│   ├── ddl/                      # S3 Tables DDL 스크립트
│   └── metadata/                 # 테이블/컬럼 메타데이터 JSON
├── mcp/                          # MCP 서버 (Lambda)
│   ├── handler.py                # Lambda 진입점 — tool name 라우팅
│   ├── emr_client.py             # EMR Serverless Livy 브릿지 (SigV4)
│   ├── metadata_loader.py        # S3 메타데이터 로더
│   └── tools/                    # 13개 tool 구현
│       ├── patient.py            # get_patient_summary, search_patients
│       ├── clinical.py           # encounter, observation, medication, diagnosis
│       ├── financial.py          # get_claim_summary
│       ├── analytics.py          # detect_care_gaps, population_health_metrics
│       ├── schema_discovery.py   # list_tables, get_table_schema, relationships
│       └── query.py              # run_custom_query (Text-to-SQL)
├── agent/                        # AI 에이전트 + Streamlit UI
│   ├── medical_agent.py          # Strands Agent (AgentCore Runtime 컨테이너)
│   ├── app.py                    # Streamlit 채팅 UI (SSE 스트리밍)
│   ├── system_prompt.md          # 에이전트 시스템 프롬프트
│   ├── scenarios.json            # 데모 시나리오 질문 목록
│   ├── Dockerfile                # ARM64 컨테이너 (AgentCore Runtime)
│   └── requirements.txt          # strands-agents, bedrock-agentcore, httpx
├── notebooks/                    # 배포 노트북 (JupyterLab)
│   ├── 01_deploy_mcp_lambda.ipynb
│   ├── 02_setup_agentcore_gateway.ipynb
│   ├── 03_test_mcp_server.ipynb
│   └── 04_deploy_medical_agent.ipynb
└── mcp-server-design.md          # MCP 서버 설계 문서
```

## Data Lake

| 항목 | 내용 |
|------|------|
| 원본 | Synthea 합성 FHIR 데이터 (24 리소스 타입) |
| 스토리지 | S3 Tables (`s3tablescatalog.fhir-bucket.data`) |
| 포맷 | Apache Iceberg |
| 레코드 | 450,000+ |
| 도메인 | Administrative, Clinical, Medication, Diagnostic, Care, Financial/Document |

### Table Mapping

| Domain | FHIR Resource | S3 Tables |
|--------|--------------|-----------|
| Administrative | Patient | patient_registry |
| Administrative | Practitioner | practitioner_registry |
| Administrative | Organization | organization_registry |
| Administrative | Location | location_registry |
| Administrative | PractitionerRole | practitioner_role |
| Clinical | Encounter | clinical_encounter |
| Clinical | Condition | clinical_condition |
| Clinical | Procedure | clinical_procedure |
| Clinical | Observation | clinical_observation |
| Medication | Medication | medication_catalog |
| Medication | MedicationRequest | medication_request |
| Medication | MedicationAdministration | medication_administration |
| Diagnostic | DiagnosticReport | diagnostic_report |
| Diagnostic | ImagingStudy | imaging_study |
| Diagnostic | Immunization | immunization_record |
| Diagnostic | AllergyIntolerance | allergy_intolerance |
| Care | CarePlan | care_plan |
| Care | CareTeam | care_team |
| Care | Device | device_catalog |
| Care | SupplyDelivery | supply_delivery |
| Financial | Claim | financial_claim |
| Financial | ExplanationOfBenefit | explanation_of_benefit |
| Document | DocumentReference | document_reference |
| Document | Provenance | provenance_audit |

## MCP Tools (13)

| Category | Tool | Description |
|----------|------|-------------|
| Schema | `list_tables` | 테이블 목록 + 도메인/FHIR 리소스 메타데이터 |
| Schema | `get_table_schema` | 컬럼 구조 + COMMENT 메타데이터 + 코드 매핑 |
| Schema | `get_table_relationships` | 테이블 간 FK 관계 (reference 컬럼 기반) |
| Patient | `get_patient_summary` | 환자 종합 요약 (인구통계 + 진단 + 알레르기 + 투약) |
| Patient | `search_patients` | 조건 기반 환자 검색 (이름, 성별, 나이, 질환) |
| Clinical | `get_encounter_history` | 진료 이력 (의사, 장소 포함) |
| Clinical | `get_clinical_observations` | 관찰/측정 데이터 (활력징후, 검사결과) |
| Clinical | `get_medications` | 투약 이력 (처방 + 투여 기록) |
| Clinical | `get_diagnosis_history` | 진단 이력 (질환 + 시술) |
| Financial | `get_claim_summary` | 청구/보험 요약 |
| Analytics | `detect_care_gaps` | 케어 갭 분석 (누락 예방접종, 미수행 검진) |
| Analytics | `get_population_health_metrics` | 인구 건강 지표 집계 |
| Query | `run_custom_query` | Spark SQL 직접 실행 (SELECT only, LIMIT 100) |

## Workshop Labs

### Prerequisites
- CDK 인프라 배포 (`cdk deploy`)
- Glue Crawler 실행 → 데이터 카탈로그 생성
- SageMaker Unified Studio IAM-based Domain 생성
- Lake Formation 권한 설정 (S3 Tables database)

### Lab 1 — AI-Ready Data Lake 구축
SageMaker Unified Studio 노트북에서:
1. Glue Crawler로 Aurora PostgreSQL 데이터 카탈로그 생성
2. AI 기반 테이블/컬럼 메타데이터 생성 (COMMENT, TBLPROPERTIES)
3. S3 Tables에 Iceberg 테이블 DDL 생성 및 실행
4. Aurora → S3 Tables 데이터 마이그레이션

### Lab 2 — MCP 서버 배포
노트북 `01`, `02`, `03` 순서로 실행:
1. Lambda MCP 서버 패키징 및 배포 (13개 tool)
2. AgentCore Gateway + Cognito OAuth 설정
3. MCP 서버 연동 테스트

### Lab 3 — Medical AI Agent 배포
노트북 `04` 실행:
1. ECR 리포지토리 생성 + CodeBuild 프로젝트 설정
2. Strands Agent 컨테이너 빌드 (ARM64)
3. AgentCore Runtime 배포
4. Streamlit UI 실행 및 테스트

## Demo Scenarios

### 시나리오 1: 외래 진료 전 환자 파악
```
"당뇨 진단받은 50대 환자 목록 보여줘"
"이 중 Jarrod Orti 환자 상태 요약해줘"
"이 환자 최근 혈당 수치 추이가 어떻게 돼?"
"지금 복용 중인 약은?"
```

### 시나리오 2: 입원 환자 회진
```
"최근 입원했던 환자 목록 좀 보여줘"
"Dorethea Koss 환자 진단 이력 보여줘"
"이 환자한테 투여 중인 약물이랑 투약 기록 확인해줘"
```

### 시나리오 3: 자유 질의 (Text-to-SQL)
```
"우리 병원에서 가장 많이 처방되는 약물 top 10이 뭐야?"
```
→ Agent가 `list_tables` → `get_table_schema` → `run_custom_query` 순서로 호출하여 SQL 생성 및 실행

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Infrastructure | AWS CDK (Python) |
| Database | Aurora PostgreSQL → S3 Tables (Iceberg) |
| Compute | EMR Serverless (Spark SQL via Livy) |
| MCP Server | AWS Lambda (Python 3.13) |
| Gateway | Amazon Bedrock AgentCore Gateway + Cognito OAuth |
| Agent | Strands Agents + AgentCore Runtime (ARM64 Container) |
| Model | Claude Sonnet 4 (cross-region inference) |
| Frontend | Streamlit (SSE streaming) |
| Build | AWS CodeBuild (ARM64) + ECR |

## Notes

- 모든 환자 데이터는 Synthea 합성 데이터이며 실제 환자 정보가 아닙니다
- EMR Serverless Livy 세션 초기화에 1-2분 소요될 수 있습니다
- 복잡한 쿼리(다중 JOIN, 집계)는 실행에 1-2분 걸릴 수 있습니다
