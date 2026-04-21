declare const __APP_MODE__: string;
const isLegacy = __APP_MODE__ === 'legacy';

const ko = {
  title: isLegacy ? "Medical AI Agent (Legacy)" : "Medical AI Agent",
  subtitle: isLegacy ? "⚠️ Obfuscated tables/columns · No metadata · data_legacy namespace" : "AI-ready Data Lake · AgentCore · MCP Server",
  welcome: "무엇을 도와드릴까요?",
  welcomeSub: "좌측 시나리오를 선택하거나 직접 질문하세요.",
  placeholder: "의료 데이터에 대해 질문하세요...",
  scenarios: "💡 데모 시나리오",
  reset: "대화 초기화",
  analyzing: "분석 중...",
  step: "Step",
  scenarioItems: [
    {
      icon: "🩺", label: "외래 진료",
      questions: [
        "오늘 외래에 당뇨 진단받은 50대 환자가 있는데, 목록 좀 보여줘.",
        "박재윤 환자 상태 요약해줘.",
        "이 환자 최근 혈당 수치 추이가 어떻게 돼?",
        "지금 복용 중인 약은?",
        "이 환자 예방접종이나 정기 검진 중 빠진 거 있어?",
      ]
    },
    {
      icon: "🏥", label: "입원 회진",
      questions: [
        "최근 입원했던 환자 목록 좀 보여줘.",
        "곽소윤 환자 진단 이력 보여줘.",
        "이 환자한테 투여 중인 약물이랑 투약 기록 확인해줘.",
        "이 환자 알레르기 있어? 항생제 바꿔야 할 수도 있는데.",
        "이 환자 퇴원 요약서 작성해줘.",
      ]
    },
    {
      icon: "💊", label: "처방 검토",
      questions: [
        "이현우 환자가 현재 복용 중인 약물 전체 목록 보여줘.",
        "이 환자가 복용 중인 약물 간 상호작용 위험이 있을까?",
        "이 환자의 주요 진단명과 관련된 최신 연구 논문 찾아줘.",
        "이 중에서 가장 관련 있는 논문 상세 내용 보여줘.",
      ]
    },
    {
      icon: "💰", label: "보험 청구",
      questions: [
        "진료비가 가장 많이 발생한 환자 top 5 보여줘.",
        "우다인 환자의 보험 청구 요약 보여줘.",
        "이 환자의 진단 이력과 청구 내역이 일치하는지 확인해줘.",
      ]
    },
    {
      icon: "📊", label: "경영 분석",
      questions: [
        "연령대별 당뇨 유병률 분석해줘.",
        "최근 응급실 방문 환자 수와 주요 진단명 top 5 알려줘.",
        "우리 병원에서 가장 많이 처방되는 약물 top 10이 뭐야?",
        "최근 1년간 월별 입원 환자 수 추이를 보여줘.",
        "성별, 연령대별 외래 진료 건수 분포를 분석해줘.",
      ]
    },
  ],
};

const en: typeof ko = {
  title: isLegacy ? "Medical AI Agent (Legacy)" : "Medical AI Agent",
  subtitle: isLegacy ? "⚠️ Obfuscated tables/columns · No metadata · data_legacy namespace" : "AI-ready Data Lake · AgentCore · MCP Server",
  welcome: "How can I help you?",
  welcomeSub: "Select a scenario on the left or ask a question.",
  placeholder: "Ask about medical data...",
  scenarios: "💡 Demo Scenarios",
  reset: "Reset Chat",
  analyzing: "Analyzing...",
  step: "Step",
  scenarioItems: [
    {
      icon: "🩺", label: "Outpatient Visit",
      questions: [
        "Show me diabetic patients in their 50s.",
        "Summarize the status of patient 박재윤.",
        "What are this patient's recent blood glucose trends?",
        "What medications are they currently taking?",
        "Any missing vaccinations or overdue screenings?",
      ]
    },
    {
      icon: "🏥", label: "Inpatient Rounds",
      questions: [
        "Show me recently admitted patients.",
        "Show diagnosis history for patient 곽소윤.",
        "Check medications and administration records for this patient.",
        "Does this patient have any allergies? May need to change antibiotics.",
        "Write a discharge summary for this patient.",
      ]
    },
    {
      icon: "💊", label: "Rx Review",
      questions: [
        "Show all current medications for patient 이현우.",
        "Any drug interaction risks with this patient's medications?",
        "Find recent research papers related to this patient's diagnoses.",
        "Show details of the most relevant paper.",
      ]
    },
    {
      icon: "💰", label: "Claims",
      questions: [
        "Show top 5 patients by total claim amount.",
        "Show insurance claim summary for patient 우다인.",
        "Check if diagnoses match the claim records for this patient.",
      ]
    },
    {
      icon: "📊", label: "Analytics",
      questions: [
        "Analyze diabetes prevalence by age group.",
        "Show recent ER visit counts and top 5 diagnoses.",
        "What are the top 10 most prescribed medications?",
        "Show monthly admission trends for the past year.",
        "Analyze outpatient visit distribution by gender and age group.",
      ]
    },
  ],
};

const locales = { ko, en } as const;
type Locale = keyof typeof locales;

function detectLocale(): Locale {
  const param = new URLSearchParams(window.location.search).get("lang");
  if (param && param in locales) return param as Locale;
  const nav = navigator.language.split("-")[0];
  return nav === "ko" ? "ko" : "en";
}

export const locale = detectLocale();
export const t = locales[locale];
export type { Locale };
