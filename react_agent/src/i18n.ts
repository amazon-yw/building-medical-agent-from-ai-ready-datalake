const ko = {
  title: "Medical AI Agent",
  subtitle: "AI-ready Data Lake · AgentCore · MCP Server",
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
        "Lucien Wiegand 환자 상태 요약해줘.",
        "Lucien Wiegand 환자 최근 혈당 수치 추이가 어떻게 돼?",
        "Lucien Wiegand 환자가 지금 복용 중인 약은?",
      ]
    },
    {
      icon: "🏥", label: "입원 회진",
      questions: [
        "현재 입원 중인 환자 목록 좀 보여줘.",
        "Denna Krajcik 환자 진단 이력 보여줘.",
        "Denna Krajcik 환자한테 투여 중인 약물이랑 투약 기록 확인해줘.",
      ]
    },
    {
      icon: "📋", label: "퇴원 요약",
      questions: [
        "퇴원 예정인 Pedro Keebler 환자의 종합 요약 보여줘.",
        "Pedro Keebler 환자의 입원 기간 동안 진료 이력을 정리해줘.",
        "Pedro Keebler 환자 퇴원 시 가져갈 처방 약물 목록 정리해줘.",
      ]
    },
    {
      icon: "💊", label: "처방 검토",
      questions: [
        "Cary Becker 환자가 현재 복용 중인 약물 전체 목록 보여줘.",
        "우리 병원에서 가장 많이 처방되는 약물 top 10이 뭐야?",
        "메트포르민과 SGLT2 억제제 병용 요법에 대한 최신 연구 결과 알려줘.",
      ]
    },
    {
      icon: "📊", label: "경영 분석",
      questions: [
        "데이터 레이크에 어떤 테이블들이 있는지 알려줘.",
        "연령대별 당뇨 유병률 분석해줘.",
        "최근 응급실 방문 환자 수와 주요 진단명 top 5 알려줘.",
      ]
    },
    {
      icon: "📚", label: "PubMed 검색",
      questions: [
        "제2형 당뇨병 최신 치료 가이드라인 관련 논문 찾아줘.",
        "메트포르민과 SGLT2 억제제 병용 요법에 대한 연구 결과 알려줘.",
        "이 중에서 가장 관련 있는 논문 상세 내용 보여줘.",
      ]
    },
  ],
};

const en: typeof ko = {
  title: "Medical AI Agent",
  subtitle: "AI-ready Data Lake · AgentCore · MCP Server",
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
        "Show me a list of diabetic patients in their 50s.",
        "Summarize the status of patient Lucien Wiegand.",
        "What are the recent blood glucose trends for Lucien Wiegand?",
        "What medications is Lucien Wiegand currently taking?",
      ]
    },
    {
      icon: "🏥", label: "Inpatient Rounds",
      questions: [
        "Show me the list of currently admitted patients.",
        "Show the diagnosis history for patient Denna Krajcik.",
        "Check the medications and administration records for Denna Krajcik.",
      ]
    },
    {
      icon: "📋", label: "Discharge Summary",
      questions: [
        "Show a comprehensive summary for patient Pedro Keebler who is about to be discharged.",
        "Summarize the encounter history during Pedro Keebler's admission.",
        "List the discharge medications for Pedro Keebler.",
      ]
    },
    {
      icon: "💊", label: "Prescription Review",
      questions: [
        "Show all current medications for patient Cary Becker.",
        "What are the top 10 most prescribed medications in our hospital?",
        "Find recent research on metformin and SGLT2 inhibitor combination therapy.",
      ]
    },
    {
      icon: "📊", label: "Executive Analytics",
      questions: [
        "What tables are available in the data lake?",
        "Analyze diabetes prevalence by age group.",
        "Show recent ER visit counts and top 5 diagnoses.",
      ]
    },
    {
      icon: "📚", label: "PubMed Search",
      questions: [
        "Find papers on the latest type 2 diabetes treatment guidelines.",
        "Find research on metformin and SGLT2 inhibitor combination therapy.",
        "Show me the details of the most relevant paper.",
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
