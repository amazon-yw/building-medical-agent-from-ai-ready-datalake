import React, { useState, useRef, useEffect } from 'react';
import {
  Stethoscope, Send, User, Bot,
  RefreshCw, Info, Wrench, Check, X, ChevronDown, ChevronRight
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from './lib/utils';
import { streamAgentResponse, ChatMessage } from './services/agent';
import { motion, AnimatePresence } from 'motion/react';
import { t } from './i18n';

const SCENARIOS = t.scenarioItems;

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

    const updateLast = (text: string, ts?: ToolStep[]) => {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'model') {
          return [...prev.slice(0, -1), { ...last, text, toolSteps: ts ? [...ts] : last.toolSteps }];
        }
        return [...prev, { role: 'model', text, toolSteps: ts }];
      });
    };

    try {
      await streamAgentResponse(
        msg,
        sessionId,
        (chunk) => {
          buf += chunk;
          updateLast(buf);
        },
        (name: string, toolInput: string) => {
          // New tool call
          if (buf.trim()) {
            updateLast(buf);
          }
          buf = '';
          tools.push({ name, input: toolInput, done: false });
          setCurrentTools([...tools]);
          setMessages(prev => [...prev, { role: 'model', text: '', toolSteps: [] }]);
        },
        (result, isError) => {
          const last = tools[tools.length - 1];
          if (last) { last.result = result; last.isError = isError; last.done = true; }
          setCurrentTools([...tools]);
          updateLast(buf, tools);
        }
      );
    } catch (error: any) {
      buf += `\n\n❌ 오류: ${error.message}`;
    } finally {
      if (buf.trim()) updateLast(buf, tools);
      setIsLoading(false);
      setCurrentTools([]);
    }
  };

  const ToolTimeline = ({ steps }: { steps: ToolStep[] }) => (
    <div className="space-y-1 my-2">
      {steps.map((step, idx) => (
        <div
          key={`${step.name}-${idx}`}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs",
            step.done
              ? step.isError ? "bg-red-50 border border-red-200" : "bg-green-50 border border-green-200"
              : "bg-blue-50 border border-blue-200"
          )}
        >
          <div className="flex items-center gap-2">
            {step.done ? (
              step.isError ? <X className="w-3.5 h-3.5 text-red-500 flex-shrink-0" /> : <Check className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
            ) : (
              <Wrench className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
            )}
            <span className="font-semibold text-slate-700">{step.name || `${t.step} ${idx + 1}`}</span>
            {step.result && <span className="text-slate-500 ml-auto text-[10px] flex-shrink-0">{step.result}</span>}
          </div>
          {step.input && <div className="text-slate-400 text-[10px] font-mono mt-1 break-all overflow-hidden max-h-[3rem]">{step.input}</div>}
        </div>
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
            <h1 className="text-lg md:text-xl font-bold text-slate-800 tracking-tight">🏥 Medical AI Agent</h1>
            <p className="text-[10px] md:text-xs text-slate-500 font-medium">AI-ready Data Lake · AgentCore · MCP Server</p>
          </div>
        </div>
      </header>

      {/* Body: Sidebar + Chat */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar — Scenarios */}
        <aside className="w-72 flex-shrink-0 border-r border-slate-200 bg-white overflow-y-auto p-3 space-y-2">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider px-1 mb-2">{t.scenarios}</h3>
          {SCENARIOS.map((s, i) => (
            <div key={i} className="bg-slate-50 border border-slate-200 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpandedScenario(expandedScenario === i ? null : i)}
                className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-sky-50 transition-colors text-left"
              >
                <span className="text-base">{s.icon}</span>
                <span className="font-semibold text-slate-700 text-xs flex-1">{s.label}</span>
                {expandedScenario === i ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
              </button>
              <AnimatePresence>
                {expandedScenario === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="px-3 pb-2.5 space-y-1 border-t border-slate-100 pt-1.5">
                      {s.questions.map((q, qi) => (
                        <button
                          key={qi}
                          onClick={() => handleSend(q)}
                          className="w-full text-left px-2.5 py-1.5 bg-white hover:bg-sky-50 hover:border-sky-300 border border-slate-200 rounded-lg text-[11px] text-slate-600 transition-all leading-snug"
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
          <div className="pt-2">
            <button
              onClick={() => { setMessages([]); setCurrentTools([]); setExpandedScenario(null); }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs text-slate-500 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> {t.reset}
            </button>
          </div>
        </aside>

        {/* Right: Chat Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
      <main ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 scroll-smooth">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-4 max-w-md mx-auto">
            <div className="bg-sky-100 p-6 rounded-full">
              <Bot className="w-12 h-12 text-sky-600" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-bold text-slate-800">{t.welcome}</h2>
              <p className="text-slate-500 text-sm">{t.welcomeSub}</p>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
              "flex gap-3",
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
              "space-y-1 p-3 md:p-4 rounded-2xl shadow-sm text-sm w-full",
              msg.role === 'user'
                ? "bg-sky-600 text-white rounded-tr-none"
                : "bg-white border border-slate-200 rounded-tl-none"
            )}>
              {/* Tool steps for this message */}
              {msg.role === 'model' && msg.toolSteps && msg.toolSteps.length > 0 && (
                <ToolTimeline steps={msg.toolSteps} />
              )}
              <div className="markdown-body">
                {msg.role === 'model' && isLoading && idx === messages.length - 1 ? (
                  <pre className="whitespace-pre-wrap font-sans text-sm">{msg.text}<span className="animate-pulse">▌</span></pre>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                )}
              </div>
            </div>
          </motion.div>
        ))}

        {/* Live tool steps while loading */}
        {isLoading && currentTools.length > 0 && (
          <div className="mr-auto ml-10 md:ml-11">
            <ToolTimeline steps={currentTools} />
          </div>
        )}

        {isLoading && currentTools.length === 0 && (
          <div className="flex gap-3 mr-auto">
            <div className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-white border border-slate-200 flex items-center justify-center flex-shrink-0 animate-pulse">
              <Bot className="w-4 h-4 text-sky-400" />
            </div>
            <div className="bg-white border border-slate-200 p-3 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-2">
              <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" />
              <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.2s]" />
              <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.4s]" />
              <span className="text-xs text-slate-400 ml-2">{t.analyzing}</span>
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
            placeholder={t.placeholder}
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
      </div>{/* end chat column */}
      </div>{/* end body flex */}
    </div>
  );
}
