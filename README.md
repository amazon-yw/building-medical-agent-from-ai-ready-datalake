# Building Medical AI Agent from AI-Ready Data Lake

의료 데이터 레이크 기반 AI 에이전트를 구축하는 워크샵입니다. Synthea 합성 데이터를 Aurora PostgreSQL에서 S3 Tables(Iceberg)로 마이그레이션하고, MCP 서버를 통해 AI 에이전트가 자연어로 의료 데이터를 조회·분석할 수 있는 엔드투엔드 파이프라인을 구축합니다.

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Streamlit UI   │────▶│  AgentCore Runtime   │────▶│  Strands Agent      │
│  (EC2:8501)     │ SSE │  (Container/ARM64)   │     │  (Claude Sonnet 4)  │
└─────────────────┘     └──────────────────────┘     └───────┬─────────────┘
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
| PubMed | `search_pubmed` | Pubmed 검색 |
| PubMed | `get_pubmed_article` | Pubmed Article 조회 |

## Workshop Labs

### Motivation: AI-Assisted Schema Mapping

이 워크샵의 Lab-1은 [Automate schema mappings with LLMs](https://medium.com/road-to-full-stack-data-science/automate-schema-mappings-with-llms-637e55988524) (Tasos Pardalis, 2025)에서 제시한 아이디어에서 영감을 받았습니다. 레거시 데이터베이스에서 클라우드 데이터 레이크로 마이그레이션할 때, LLM을 활용하여 스키마 매핑과 메타데이터 생성을 자동화할 수 있습니다.

이 워크샵에서는 이 컨셉을 실제로 구현합니다:
- Aurora PostgreSQL의 축약된 컬럼명(예: `sbj_ref`, `eff_dts`)을 LLM이 분석하여 의미 있는 이름(예: `subject_reference`, `effective_datetime`)으로 확장
- 각 테이블과 컬럼에 대한 AI 기반 설명(COMMENT), 도메인 분류, 코드 매핑을 자동 생성
- 생성된 메타데이터를 S3 Tables의 Iceberg 테이블 DDL에 반영하여 AI-Ready Data Lake 구축
- 이 메타데이터가 이후 MCP 서버의 Schema Discovery 도구와 Agent의 Text-to-SQL에 직접 활용

### Lab 0 — 인프라 배포 및 개발환경 설정 (Optional)

#### 인프라 배포 (CDK)
> CDK로 워크샵에 필요한 전체 인프라를 배포합니다.

1. VPC, Subnets, Security Groups
2. Aurora PostgreSQL 클러스터 + Synthea FHIR 데이터 로딩
3. S3 버킷 (데이터, DDL 스크립트, 메타데이터)
4. S3 Tables 버킷
5. EMR Serverless Application
6. Glue Crawler + Data Catalog
7. EC2 인스턴스 (VS Code Server + JupyterLab)

```bash
cd cdk
pip install -r requirements.txt
cdk deploy
```

#### 개발환경 설정 > PostgreSQL 테이블 스키마 Crawling
1. Glue 콘솔 페이지로 이동
2. 좌측 메뉴에서 Data Catalog > Crawlers 선택
3. `fhir-aurora-crawler`라는 이름의 Glue Crawler 선택
4. `Run Crawler` 버튼 클릭하여 PostgreSQL 데이터베이스 내 테이블 스키마 크롤링

#### 개발환경 설정 > SageMaker Unified Studio 생성
1. SageMaker Unified Studio - IAM-based domain 생성
    - Project data and administrative control 섹션 밑 Execution IAM role 설정을 `Auto-create a new role with admin permissions`로 셋팅
2. 생성 후 프로젝트 VPC 설정 변경 -> `FhirDataStack/FhirVpc`로 설정
3. 이후 아래 스크립트 수행
    - Lake Formation으로 생성된 `AmazonSageMakerAdminIAMExecutionRole` 역할에 대해 S3 Tables 권한 부여

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

#### 개발환경 설정 > VS Code Server + Kiro CLI 셋업
> EC2에 프로비저닝된 VS Code Server에 접속하여 개발 환경을 구성합니다.

1. Cloud Formation의 `FhirDataStack`의 Outputs 탭에서 `CodeEditorURL` 확보
2. VS Code Server 접속 (`http://<EC2-IP>:8080`)
3. 워크샵 리포지토리 클론
4. Kiro CLI 설치 및 인증
```shell
[participant@CodeEditor workshop]$ curl -fsSL https://cli.kiro.dev/install | bash

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

### Lab 1 — AI-Ready Data Lake 구축을 위한 개발 (Kiro CLI)
> Kiro CLI를 활용하여 레거시 DB의 메타데이터를 LLM으로 추출하고, SageMaker Unified Studio에서 데이터를 마이그레이션합니다.

**Step-1: LLM 기반 메타데이터 생성 (Kiro CLI, VS Code)**
1. `prompt.md` 파일의 `[STEP-1] 원본 테이블의 메타데이터 추론` 섹션의 프롬프트를 사용하여 생성
2. Kiro CLI에서 해당 프롬프트를 활용하여 24개 테이블의 메타데이터 자동 생성
3. 메타데이터 기준으로 DDL 스크립트 생성
    - DDL에는 생성한 메타데이터가 COMMENT나 DESCRIPTION 구문에 담겨져 생성
4. 생성한 메타데이터와 DDL 스크립트를 S3에 업로드

**Step-2: S3 Tables 내 테이블을 생성하는 노트북 생성**
1. `prompt.md` 파일의 `[STEP-2] 생성된 메타데이터로 테이블 생성 노트북 작성` 섹션 내 프롬프트를 사용하여 테이블 생성 노트북 생성
2. Kiro CLI에서 해당 프롬프트를 활용하여 S3 Tables에 24개 테이블을 생성하는 Jupyterlab 노트북 파일 생성
3. 생성한 노트북 파일을 SageMaker Unified Studio가 참조하는 S3 경로에 업로드

**Step-3: PostgreSQL -> S3 Tables 데이터 마이그레이션 노트북 생성**
1. prompt.md 파일의 `[STEP-3] 데이터 마이그레이션 노트북 생성` 섹션 내 프롬프트를 사용하여 데이터 마이그레이션 노트북 생성
2. Kiro CLI에서 해당 프롬프트를 활용하여 PostgreSQL에 있는 Legecy DB의 데이터를 S3 Tables로 마이그레이션 하는 Jupyterlab 노트북 파일 생성
3. 생성한 노트북 파일을 SageMaker Unified Studio가 참조하는 S3 경로에 업로드

### Lab 2 - AI-Ready Data Lake 구축 (SageMaker Unified Studio)
> SageMaker Unified Studio 환경의 노트북에서 관련 작업을 진행합니다.

1. SageMaker Unified Studio JupyterLab 접속
2. `Step-2`에서 생성된 노트북을 열어 S3 Tables에 Iceberg 테이블 생성
3. `Step-3`에서 생성된 노트북을 열어 Aurora PostgreSQL → S3 Tables 데이터 마이그레이션 (Spark SQL) 
4. 마이그레이션 데이터 검증

### Lab 3 — MCP 서버 구축 (VS Code)
> VS Code에서 노트북을 실행하여 MCP 서버와 관련 리소스를 직접 배포합니다.

1. Lambda MCP 서버 패키징 및 배포 — 15개 tool (`notebooks/01_deploy_mcp_lambda.ipynb`)
2. Cognito User Pool + OAuth 클라이언트 설정
3. AgentCore Gateway + MCP Target 생성 (`notebooks/02_setup_agentcore_gateway.ipynb`)
4. MCP 서버 연동 테스트 (`notebooks/03_test_mcp_server.ipynb`)
5. Amazon Quick 연동 — Integrations → MCP server 추가

| 필드 | 값 |
|------|-----|
| MCP Endpoint URL | `https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp` |
| Authentication | OAuth 2.0 (Client Credentials) |
| Token URL | Cognito OAuth Token URL (`/oauth2/token`) |
| Client ID | Cognito App Client ID |
| Client Secret | Cognito App Client Secret |
| Scope | `fhir-mcp/tools` |

### Lab 4 — Medical AI Agent 배포 (VS Code)
> VS Code에서 노트북을 실행하여 Agent와 관련 리소스를 직접 배포합니다.

1. ECR 리포지토리 생성
2. CodeBuild 프로젝트 설정 (ARM64)
3. Strands Agent 컨테이너 빌드 및 ECR 푸시
4. AgentCore Runtime 생성 및 배포 (`notebooks/04_deploy_medical_agent.ipynb`)

> Streamlit 채팅 UI를 실행하여 Medical AI Agent를 체험합니다.
1. EC2에서 Streamlit 앱 실행
```bash
./run_app.py
```

2. 브라우저에서 `http://<EC2-IP>:8501` 접속
3. 사이드바 시나리오 버튼으로 데모 질의 실행
4. 실시간 SSE 스트리밍으로 도구 호출 과정 및 응답 확인

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

### 시나리오 4: Pubmed 관련 질의
```
"제2형 당뇨병 최신 치료 가이드라인 관련 논문 찾아줘"
"이 환자의 진단명과 관련된 최신 연구 논문이 있을까?"
"메트포르민과 SGLT2 억제제 병용 요법에 대한 연구 결과 알려줘"
"이 중에서 가장 관련 있는 논문 상세 내용 보여줘"
```

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
