# Medical MCP Server 설계

## 아키텍처

```
Medical Agent (Bedrock)
    ↓ MCP Protocol
MCP Server (FastAPI/SSE)
    ↓ Tool 호출
EMR Serverless (Spark SQL)
    ↓ Iceberg REST Catalog
S3 Tables (fhir-bucket/data/*)
```

## 데이터 기반

- S3 Tables: `fhir-bucket/data` 네임스페이스
- 24개 FHIR 테이블 (Synthea 생성 데이터, 450,000+ 레코드)
- 6개 도메인: Administrative, Clinical, Medication, Diagnostic, Care, Financial/Document
- 테이블/컬럼명은 S3 Tables에서 확장된 이름 사용 (예: `subject_reference`, `effective_datetime`)

## Tool 목록 (13개)

### Category 1: Patient (환자 조회)

#### 1. `get_patient_summary`
- 설명: 환자 종합 요약 (기본정보 + 활성 진단 + 알레르기 + 현재 투약)
- 입력: `patient_id`
- JOIN: patient + condition + allergy + medication
- 시나리오: *"환자 aa3c30d5의 현재 상태를 알려줘"*

#### 2. `search_patients`
- 설명: 조건 기반 환자 검색
- 입력: `name?`, `gender?`, `birth_date_range?`, `condition_code?`
- 시나리오: *"당뇨 진단받은 50대 여성 환자 목록"*

### Category 2: Clinical (임상 기록)

#### 3. `get_encounter_history`
- 설명: 진료 이력 조회
- 입력: `patient_id`, `date_range?`, `class_code?`
- JOIN: encounter + practitioner + location + organization
- 시나리오: *"이 환자의 최근 6개월 입원 기록"*

#### 4. `get_clinical_observations`
- 설명: 관찰/측정 데이터 조회 (활력징후, 검사결과)
- 입력: `patient_id`, `observation_code?`, `date_range?`
- LOINC 코드 기반 필터링 (혈압, 혈당, 체중 등)
- 시나리오: *"이 환자의 혈당 추이를 보여줘"*

#### 5. `get_medications`
- 설명: 투약 이력 조회
- 입력: `patient_id`, `active_only?`
- JOIN: medication_request + medication_administration + medication
- 시나리오: *"현재 복용 중인 약물 목록"*

#### 6. `get_diagnosis_history`
- 설명: 진단 이력 조회
- 입력: `patient_id`, `category?`
- JOIN: condition + procedure
- 시나리오: *"이 환자의 만성질환 이력"*

### Category 3: Financial (재무/보험)

#### 7. `get_claim_summary`
- 설명: 청구/보험 요약 조회
- 입력: `patient_id?`, `date_range?`, `status?`
- JOIN: claim + explanation_of_benefit
- 시나리오: *"이 환자의 미결제 청구 건"*, *"지난 분기 청구 현황"*

### Category 4: Analytics (분석)

#### 8. `detect_care_gaps`
- 설명: 케어 갭 분석 (누락된 예방접종, 미수행 검진)
- 입력: `patient_id`
- 비교: care_plan + immunization + observation
- Agent 추론 능력 하이라이트
- 시나리오: *"이 환자에게 빠진 예방 조치가 있나?"*

#### 9. `get_population_health_metrics`
- 설명: 인구 건강 지표 집계
- 입력: `condition_code?`, `region?`, `age_group?`
- 다중 테이블 집계 쿼리
- 시나리오: *"지역별 당뇨 유병률과 합병증 발생률"*

### Category 5: Schema Discovery (메타데이터 조회)

> S3 Tables 생성 시 테이블/컬럼에 COMMENT, TBLPROPERTIES로 메타데이터를 이미 저장해둔 상태.
> 별도 메타데이터 저장소 없이 Spark SQL 명령으로 직접 조회하여 응답.

#### 10. `list_tables`
- 설명: 데이터 레이크 테이블 목록 및 메타데이터 조회
- 입력: `domain?` (administrative, clinical, medication, financial, care, document)
- 구현:
  ```sql
  SHOW TABLES;                              -- 테이블 목록
  SHOW TBLPROPERTIES <table>;               -- 도메인, FHIR 리소스 타입 등
  DESCRIBE TABLE EXTENDED <table>;          -- 테이블 COMMENT (설명)
  ```
- 반환: 테이블명, 도메인, FHIR 리소스 타입, 테이블 설명(COMMENT)
- 시나리오: *"어떤 테이블들이 있어?"*, *"임상 관련 테이블만 보여줘"*

#### 11. `get_table_schema`
- 설명: 테이블 스키마 및 컬럼 메타데이터 상세 조회
- 입력: `table_name`
- 구현:
  ```sql
  DESCRIBE TABLE EXTENDED <table>;          -- 컬럼명, 타입, 컬럼 COMMENT (설명)
  SHOW TBLPROPERTIES <table>;               -- 도메인, FHIR 리소스 타입, 서브도메인
  ```
- 반환: 컬럼명, 타입, 컬럼 설명(COMMENT), 테이블 속성(TBLPROPERTIES)
- 시나리오: *"patient_registry 테이블의 컬럼 구조를 알려줘"*

#### 12. `get_table_relationships`
- 설명: 테이블 간 관계(FK/JOIN) 조회
- 입력: `table_name?`
- 구현:
  ```sql
  DESCRIBE TABLE EXTENDED <table>;          -- _reference 접미사 컬럼 → FK 관계 추출
  SHOW TBLPROPERTIES <table>;               -- 관계 힌트 속성 조회
  ```
- 반환: 참조 컬럼, 대상 테이블, JOIN 힌트
- 시나리오: *"encounter 테이블이 어떤 테이블들과 연결돼 있어?"*

### Category 6: Advanced Query (자유 쿼리)

#### 13. `run_custom_query`
- 설명: 자연어 → SQL 변환 후 실행 (Text-to-SQL)
- 입력: `query` (Spark SQL)
- 안전장치: SELECT만 허용, LIMIT 100 강제, 타임아웃 설정
- Agent가 `list_tables` → `get_table_schema` → `get_table_relationships` → `run_custom_query` 순서로 호출
- 시나리오: *"2024년에 가장 많이 처방된 약물 top 10은?"*

## Agent의 Text-to-SQL 동작 흐름

```
사용자: "2024년에 가장 많이 처방된 약물 top 10은?"

Agent:
  1) list_tables(domain="medication")
     → medication_catalog, medication_request, medication_administration 확인

  2) get_table_schema("medication_request")
     → 컬럼 구조 파악 (medication_code_display, authored_datetime 등)

  3) get_table_relationships("medication_request")
     → medication_catalog과 JOIN 가능 확인

  4) run_custom_query("""
       SELECT m.code_display, COUNT(*) as prescription_count
       FROM medication_request mr
       JOIN medication_catalog m ON mr.medication_reference = m.resource_id
       WHERE mr.authored_datetime >= '2024-01-01'
       GROUP BY m.code_display
       ORDER BY prescription_count DESC
       LIMIT 10
     """)
```

## 워크샵 데모 시나리오

### 시나리오 1: 외래 진료 전 환자 파악

> 의사가 오전 외래 시작 전, 오늘 예약된 당뇨 환자의 상태를 빠르게 파악하는 상황

```
의사: "외래에 당뇨 진단받은 50대 환자가 있는데, 목록 좀 보여줘."
   → search_patients(condition_code="diabetes", age_range="60-69")

의사: "이 중 Jarrod Orti 환자 상태 요약해줘."
   → get_patient_summary(patient_id="xxx")

의사: "이 환자 최근 혈당 수치 추이가 어떻게 돼?"
   → get_clinical_observations(patient_id="xxx", observation_code="blood-glucose")

의사: "지금 복용 중인 약은?"
   → get_medications(patient_id="xxx", active_only=true)

의사: "마지막 내원이 언제였지?"
   → get_encounter_history(patient_id="xxx", class_code="AMB")
```

### 시나리오 2: 입원 환자 회진

> 담당의가 병동 회진 전, 입원 환자의 경과와 투약 현황을 확인하는 상황

```
의사: "최근 입원했던 환자 목록 좀 보여줘."

의사: "최근 입원했던 환자 중 Dorethea Koss 환자 진단 이력 보여줘."
   → get_diagnosis_history(patient_id="xxx")

의사: "이 환자한테 투여 중인 약물이랑 투약 기록 확인해줘."
   → get_medications(patient_id="xxx")

의사: "최근 검사 결과 중 이상 소견 있는 거 있어?"
   → get_clinical_observations(patient_id="xxx", date_range="last_7_days")

의사: "이 환자 알레르기 있었나? 항생제 바꿔야 할 수도 있는데"
   → get_patient_summary(patient_id="xxx")  # 알레르기 정보 포함
```

### 시나리오 3: 예방의학 / 건강검진 누락 확인

> 가정의학과 의사가 정기 검진 환자의 예방 조치 누락 여부를 확인하는 상황

```
의사: "이 환자 예방접종이나 정기 검진 중 빠진 거 있어?"
   → detect_care_gaps(patient_id="xxx")

의사: "이 환자 과거 접종 이력 전체 보여줘."
   → get_clinical_observations(patient_id="xxx", observation_code="immunization")

의사: "같은 연령대 환자들의 당뇨 유병률은 어느 정도야?"
   → get_population_health_metrics(condition_code="diabetes", age_group="60-69")
```

### 시나리오 4: 보험 청구 / 수납 확인

> 원무과 직원이나 담당의가 환자의 청구 현황을 확인하는 상황

```
직원: "이 환자의 최근 보험 청구 현황 보여줘."
   → get_claim_summary(patient_id="xxx")

직원: "미결제 건이 있나?"
   → get_claim_summary(patient_id="xxx", status="active")
```

### 시나리오 5: 자유 질의 (Text-to-SQL)

> 의료진이 정형화된 tool로는 답하기 어려운 복합 질문을 하는 상황

```
의사: "우리 병원에서 가장 많이 처방되는 약물 top 10이 뭐야?"
   → list_tables(domain="medication")
   → get_table_schema("medication_request")
   → run_custom_query("SELECT medication_code_display, COUNT(*) ...")

의사: "작년에 응급실 재방문율이 높은 환자군 특성이 궁금한데..."
   → list_tables(domain="clinical")
   → get_table_schema("clinical_encounter")
   → get_table_relationships("clinical_encounter")
   → run_custom_query("SELECT ... GROUP BY ... HAVING visit_count > 2")

의사: "당뇨 환자 중 합병증으로 입원한 비율이 연령대별로 어떻게 되지?"
   → get_table_schema("clinical_condition")
   → get_table_schema("clinical_encounter")
   → run_custom_query("SELECT age_group, ... JOIN ... WHERE ...")
```

## 테이블 매핑 참조

| 도메인 | FHIR 리소스 | Aurora 테이블 | S3 Tables 테이블 |
|--------|------------|--------------|-----------------|
| Administrative | Patient | abc_reg_ptnt | patient_registry |
| Administrative | Practitioner | abc_reg_prct | practitioner_registry |
| Administrative | Organization | abc_reg_orgz | organization_registry |
| Administrative | Location | abc_reg_lctn | location_registry |
| Administrative | PractitionerRole | abc_reg_prol | practitioner_role |
| Clinical | Encounter | abc_cln_enct | clinical_encounter |
| Clinical | Condition | abc_cln_cond | clinical_condition |
| Clinical | Procedure | abc_cln_prcd | clinical_procedure |
| Clinical | Observation | abc_cln_obsv | clinical_observation |
| Medication | Medication | abc_rx_mdcn | medication_catalog |
| Medication | MedicationRequest | abc_rx_mreq | medication_request |
| Medication | MedicationAdministration | abc_rx_madm | medication_administration |
| Diagnostic | DiagnosticReport | abc_dgn_drpt | diagnostic_report |
| Diagnostic | ImagingStudy | abc_dgn_imgs | imaging_study |
| Diagnostic | Immunization | abc_dgn_imzn | immunization_record |
| Diagnostic | AllergyIntolerance | abc_dgn_algy | allergy_intolerance |
| Care | CarePlan | abc_car_cpln | care_plan |
| Care | CareTeam | abc_car_ctm | care_team |
| Care | Device | abc_car_devc | device_catalog |
| Care | SupplyDelivery | abc_car_sdlv | supply_delivery |
| Financial | Claim | abc_fin_clam | financial_claim |
| Financial | ExplanationOfBenefit | abc_fin_eob | explanation_of_benefit |
| Document | DocumentReference | abc_doc_dref | document_reference |
| Document | Provenance | abc_doc_prvn | provenance_audit |
