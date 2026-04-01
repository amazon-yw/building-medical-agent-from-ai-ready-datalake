import React, { useState, useRef, useEffect } from 'react';
import {
  Stethoscope, Send, User, Bot, AlertCircle,
  RefreshCw, Info, Wrench, Check, X
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { cn } from './lib/utils';
import { streamAgentResponse, ChatMessage } from './services/agent';
import { motion, AnimatePresence } from 'motion/react';

const SCENARIOS = [
  { icon: "🩺", label: "외래 진료", q: "오늘 외래에 당뇨 진단받은 50대 환자가 있는데, 목록 좀 보여줘." },
  { icon: "🏥", label: "입원 회진", q: "현재 입원 중인 환자 목록 좀 보여줘." },
  { icon: "📋", label: "퇴원 요약", q: "퇴원 예정인 Pedro Keebler 환자의 종합 요약 보여줘." },
  { icon: "💊", label: "처방 검토", q: "우리 병원에서 가장 많이 처방되는 약물 top 10이 뭐야?" },
  { icon: "📊", label: "경영 분석", q: "연령대별 당뇨 유병률 분석해줘." },
  { icon: "📚", label: "PubMed", q: "제2형 당뇨병 최신 치료 가이드라인 관련 논문 찾아줘." },
];

interface ToolStep {
  name: string;
  result?: string;
  elapsed?: string;
  isError?: boolean;
  done: boolean;
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [toolSteps, setToolSteps] = useState<ToolStep[]>([]);
  const [sessionId] = useState(() => {
    const hex = () => Math.random().toString(16).slice(2);
    return `${hex()}${hex()}-${hex()}-${hex()}-${hex()}-${hex()}${hex()}${hex()}-aaaaaaaaaa`;
  });
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading, toolSteps]);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isLoading) return;

    const userMessage: ChatMessage = { role: 'user', text: msg };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setToolSteps([]);

    let buf = '';

    try {
      await streamAgentResponse(
        msg,
        sessionId,
        (chunk) => {
          buf += chunk;
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'model') {
              return [...prev.slice(0, -1), { ...last, text: buf }];
            }
            return [...prev, { role: 'model', text: buf }];
          });
        },
        (name) => {
          setToolSteps(prev => [...prev, { name, done: false }]);
        },
        (_name, result, elapsed, isError) => {
          setToolSteps(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last) {
              last.result = result;
              last.elapsed = elapsed;
              last.isError = isError;
              last.done = true;
            }
            return updated;
          });
        }
      );
    } catch (error: any) {
      setMessages(prev => [...prev, {
        role: 'model',
        text: `❌ 오류: ${error.message}`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

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
            <p className="text-[10px] md:text-xs text-slate-500 font-medium">FHIR Data Lake · AgentCore Runtime · MCP Server</p>
          </div>
        </div>
        <button
          onClick={() => { setMessages([]); setToolSteps([]); }}
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
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 w-full">
              {SCENARIOS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => handleSend(s.q)}
                  className="text-left px-3 py-3 bg-white border border-slate-200 rounded-xl text-xs text-slate-700 hover:border-sky-300 hover:bg-sky-50 transition-all shadow-sm"
                >
                  <span className="text-lg block mb-1">{s.icon}</span>
                  <span className="font-semibold">{s.label}</span>
                </button>
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
              "w-7 h-7 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm",
              msg.role === 'user' ? "bg-sky-600" : "bg-white border border-slate-200"
            )}>
              {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-sky-600" />}
            </div>
            <div className={cn(
              "space-y-2 p-3 md:p-4 rounded-2xl shadow-sm text-sm",
              msg.role === 'user'
                ? "bg-sky-600 text-white rounded-tr-none"
                : "bg-white border border-slate-200 rounded-tl-none"
            )}>
              <div className="markdown-body prose prose-sm max-w-none">
                <ReactMarkdown>{msg.text}</ReactMarkdown>
              </div>
            </div>
          </motion.div>
        ))}

        {/* Tool Steps */}
        {toolSteps.length > 0 && (
          <div className="max-w-3xl mr-auto ml-10 md:ml-11 space-y-1">
            {toolSteps.map((step, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs",
                  step.done
                    ? step.isError ? "bg-red-50 border border-red-200" : "bg-green-50 border border-green-200"
                    : "bg-slate-100 border border-slate-200"
                )}
              >
                {step.done ? (
                  step.isError ? <X className="w-3.5 h-3.5 text-red-500" /> : <Check className="w-3.5 h-3.5 text-green-500" />
                ) : (
                  <Wrench className="w-3.5 h-3.5 text-slate-400 animate-spin" />
                )}
                <span className="font-semibold text-slate-700">{step.name || `Step ${idx + 1}`}</span>
                {step.elapsed && <span className="text-slate-400 ml-auto">{step.elapsed}</span>}
                {step.result && <span className="text-slate-500 truncate max-w-[200px]">{step.result}</span>}
              </motion.div>
            ))}
          </div>
        )}

        {isLoading && toolSteps.length === 0 && (
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
