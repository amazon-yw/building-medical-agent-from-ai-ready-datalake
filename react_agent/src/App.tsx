import React, { useState, useRef, useEffect } from 'react';
import {
  Stethoscope, Send, User, Bot,
  RefreshCw, Info, Wrench, Check, X, ChevronDown, ChevronRight
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { cn } from './lib/utils';
import { streamAgentResponse, ChatMessage } from './services/agent';
import { motion, AnimatePresence } from 'motion/react';

const SCENARIOS = [
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
];

interface ToolStep {
  name: string;
  input?: string;
  result?: string;
  isError?: boolean;
  done: boolean;
}

interface MessageWithTools {
  role: 'user' | 'model';
  text: string;
  toolSteps?: ToolStep[];
}

export default function App() {
  const [messages, setMessages] = useState<MessageWithTools[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentTools, setCurrentTools] = useState<ToolStep[]>([]);
  const [expandedScenario, setExpandedScenario] = useState<number | null>(null);
  const [sessionId] = useState(() => {
    const hex = () => Math.random().toString(16).slice(2);
    return `${hex()}${hex()}-${hex()}-${hex()}-${hex()}-${hex()}${hex()}${hex()}-aaaaaaaaaa`;
  });
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading, currentTools]);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isLoading) return;

    setMessages(prev => [...prev, { role: 'user', text: msg }]);
    setInput('');
    setIsLoading(true);
    setCurrentTools([]);

    let buf = '';
    const tools: ToolStep[] = [];

    try {
      await streamAgentResponse(
        msg,
        sessionId,
        (chunk) => {
          buf += chunk;
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'model') {
              return [...prev.slice(0, -1), { ...last, text: buf, toolSteps: [...tools] }];
            }
            return [...prev, { role: 'model', text: buf, toolSteps: [...tools] }];
          });
        },
        (name) => {
          tools.push({ name, done: false });
          setCurrentTools([...tools]);
        },
        (result, isError) => {
          const last = tools[tools.length - 1];
          if (last) {
            last.result = result;
            last.isError = isError;
            last.done = true;
          }
          setCurrentTools([...tools]);
        }
      );
    } catch (error: any) {
      buf += `\n\n❌ 오류: ${error.message}`;
    } finally {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'model') {
          return [...prev.slice(0, -1), { ...last, text: buf, toolSteps: [...tools] }];
        }
        return [...prev, { role: 'model', text: buf, toolSteps: [...tools] }];
      });
      setIsLoading(false);
      setCurrentTools([]);
    }
  };

  const ToolTimeline = ({ steps }: { steps: ToolStep[] }) => (
    <div className="space-y-1 my-2">
      {steps.map((step, idx) => (
        <motion.div
          key={idx}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs",
            step.done
              ? step.isError ? "bg-red-50 border border-red-200" : "bg-green-50 border border-green-200"
              : "bg-blue-50 border border-blue-200 animate-pulse"
          )}
        >
          {step.done ? (
            step.isError ? <X className="w-3.5 h-3.5 text-red-500 flex-shrink-0" /> : <Check className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
          ) : (
            <Wrench className="w-3.5 h-3.5 text-blue-500 flex-shrink-0 animate-spin" />
          )}
          <span className="font-semibold text-slate-700">{step.name || `Step ${idx + 1}`}</span>
          {step.result && <span className="text-slate-500 truncate max-w-[250px] ml-auto">{step.result}</span>}
        </motion.div>
      ))}
    </div>
  );

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-4 md:px-6 py-3 flex items-center justify-between shadow-sm z-10">
        <div className="flex items-center gap-3">
          <div className="bg-sky-500 p-2 rounded-xl">
            <Stethoscope className="text-white w-5 h-5 md:w-6 md:h-6" />
          </div>
          <div>
            <h1 className="text-lg md:text-xl font-bold text-slate-800 tracking-tight">Medical AI Agent</h1>
            <p className="text-[10px] md:text-xs text-slate-500 font-medium">FHIR Data Lake · AgentCore · MCP Server</p>
          </div>
        </div>
        <button
          onClick={() => { setMessages([]); setCurrentTools([]); }}
          className="text-slate-400 hover:text-sky-500 transition-colors p-2 hover:bg-sky-50 rounded-full"
          title="대화 초기화"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </header>

      {/* Chat Area */}
      <main ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 scroll-smooth">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6 max-w-lg mx-auto">
            <div className="bg-sky-100 p-6 rounded-full">
              <Bot className="w-12 h-12 text-sky-600" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl md:text-2xl font-bold text-slate-800">무엇을 도와드릴까요?</h2>
              <p className="text-slate-500 text-sm">FHIR 데이터 레이크 기반 의료 AI 에이전트입니다.</p>
            </div>
            {/* Scenario cards with expandable questions */}
            <div className="w-full space-y-2">
              {SCENARIOS.map((s, i) => (
                <div key={i} className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                  <button
                    onClick={() => setExpandedScenario(expandedScenario === i ? null : i)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-sky-50 transition-colors text-left"
                  >
                    <span className="text-xl">{s.icon}</span>
                    <span className="font-semibold text-slate-700 text-sm flex-1">{s.label}</span>
                    {expandedScenario === i ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                  </button>
                  <AnimatePresence>
                    {expandedScenario === i && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="px-4 pb-3 space-y-1.5 border-t border-slate-100 pt-2">
                          {s.questions.map((q, qi) => (
                            <button
                              key={qi}
                              onClick={() => handleSend(q)}
                              className="w-full text-left px-3 py-2 bg-slate-50 hover:bg-sky-50 hover:border-sky-300 border border-slate-200 rounded-lg text-xs text-slate-600 transition-all"
                            >
                              {q}
                            </button>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              "flex gap-3 max-w-3xl",
              msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto"
            )}
          >
            <div className={cn(
              "w-7 h-7 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm mt-1",
              msg.role === 'user' ? "bg-sky-600" : "bg-white border border-slate-200"
            )}>
              {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-sky-600" />}
            </div>
            <div className={cn(
              "space-y-1 p-3 md:p-4 rounded-2xl shadow-sm text-sm max-w-[85%]",
              msg.role === 'user'
                ? "bg-sky-600 text-white rounded-tr-none"
                : "bg-white border border-slate-200 rounded-tl-none"
            )}>
              {/* Tool steps for this message */}
              {msg.role === 'model' && msg.toolSteps && msg.toolSteps.length > 0 && (
                <ToolTimeline steps={msg.toolSteps} />
              )}
              <div className="prose prose-sm max-w-none prose-slate">
                <ReactMarkdown>{msg.text}</ReactMarkdown>
              </div>
            </div>
          </motion.div>
        ))}

        {/* Live tool steps while loading */}
        {isLoading && currentTools.length > 0 && (
          <div className="max-w-3xl mr-auto ml-10 md:ml-11">
            <ToolTimeline steps={currentTools} />
          </div>
        )}

        {isLoading && currentTools.length === 0 && (
          <div className="flex gap-3 max-w-3xl mr-auto">
            <div className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-white border border-slate-200 flex items-center justify-center flex-shrink-0 animate-pulse">
              <Bot className="w-4 h-4 text-sky-400" />
            </div>
            <div className="bg-white border border-slate-200 p-3 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-2">
              <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" />
              <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.2s]" />
              <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.4s]" />
              <span className="text-xs text-slate-400 ml-2">분석 중...</span>
            </div>
          </div>
        )}
      </main>

      {/* Input */}
      <footer className="bg-white border-t border-slate-200 p-3 md:p-4">
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="max-w-3xl mx-auto relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="의료 데이터에 대해 질문하세요..."
            disabled={isLoading}
            className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3 md:py-4 pl-4 md:pl-6 pr-12 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all text-slate-800 text-sm disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-sky-600 hover:bg-sky-700 disabled:bg-slate-300 text-white p-2 md:p-2.5 rounded-xl transition-all shadow-lg shadow-sky-500/20 active:scale-95"
          >
            <Send className="w-4 h-4 md:w-5 md:h-5" />
          </button>
        </form>
        <div className="max-w-3xl mx-auto mt-2 flex items-center justify-center gap-3 text-[9px] md:text-[10px] text-slate-400 font-medium uppercase tracking-widest">
          <span className="flex items-center gap-1"><Info className="w-3 h-3" /> FHIR DATA LAKE</span>
          <span className="w-1 h-1 bg-slate-300 rounded-full" />
          <span>AGENTCORE RUNTIME</span>
          <span className="w-1 h-1 bg-slate-300 rounded-full" />
          <span>MCP SERVER</span>
        </div>
      </footer>
    </div>
  );
}
