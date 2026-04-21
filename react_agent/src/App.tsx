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
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6','#ec4899','#06b6d4','#f97316','#6366f1','#14b8a6'];

const DataChart = React.memo(({ config }: { config: any }) => {
  const { type, title, labels, datasets } = config;

  if (type === 'pie') {
    const data = labels.map((l: string, i: number) => ({ name: l, value: datasets[0].data[i] }));
    return (
      <div className="my-4">
        {title && <div className="text-sm font-semibold text-center text-slate-700 mb-2">{title}</div>}
        <ResponsiveContainer width="100%" height={300}>
          <PieChart><Pie data={data} cx="50%" cy="50%" outerRadius={100} dataKey="value" label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}>
            {data.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie><Tooltip /><Legend /></PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // bar or line
  const data = labels.map((l: string, i: number) => {
    const point: any = { name: l };
    datasets.forEach((ds: any) => { point[ds.label] = ds.data[i]; });
    return point;
  });
  const ChartComp = type === 'line' ? LineChart : BarChart;

  return (
    <div className="my-4">
      {title && <div className="text-sm font-semibold text-center text-slate-700 mb-2">{title}</div>}
      <ResponsiveContainer width="100%" height={300}>
        <ChartComp data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {datasets.map((ds: any, i: number) =>
            type === 'line'
              ? <Line key={ds.label} type="monotone" dataKey={ds.label} stroke={COLORS[i % COLORS.length]} strokeWidth={2} />
              : <Bar key={ds.label} dataKey={ds.label} fill={COLORS[i % COLORS.length]} />
          )}
        </ChartComp>
      </ResponsiveContainer>
    </div>
  );
});

const mdComponents = {
  code({ className, children, ...props }: any) {
    const text = String(children).trim();
    // Detect JSON chart blocks
    if (text.startsWith('{"chart"')) {
      try {
        const parsed = JSON.parse(text);
        if (parsed.chart) return <DataChart config={parsed.chart} />;
      } catch {}
    }
    // Legacy mermaid support
    const match = /language-(\w+)/.exec(className || '');
    if (match && match[1] === 'mermaid') {
      return <pre className="text-xs bg-slate-100 p-2 rounded">{text}</pre>;
    }
    return <code className={className} {...props}>{children}</code>;
  }
};

const MessageBubble = React.memo(({ msg, isLast, isLoading, currentTools }: {
  msg: MessageWithTools; isLast: boolean; isLoading: boolean; currentTools: ToolStep[];
}) => {
  const showStreaming = msg.role === 'model' && isLoading && isLast;
  return (
    <div className={cn("flex gap-3", msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto")}>
      <div className={cn(
        "w-7 h-7 md:w-8 md:h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm mt-1",
        msg.role === 'user' ? "bg-sky-600" : "bg-white border border-slate-200"
      )}>
        {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-sky-600" />}
      </div>
      <div className={cn(
        "space-y-1 p-3 md:p-4 rounded-2xl shadow-sm text-sm w-full",
        msg.role === 'user' ? "bg-sky-600 text-white rounded-tr-none" : "bg-white border border-slate-200 rounded-tl-none"
      )}>
        {msg.role === 'model' && msg.toolSteps && msg.toolSteps.length > 0 && (
          <ToolPanel steps={msg.toolSteps} />
        )}
        {isLast && isLoading && currentTools.length > 0 && (
          <ToolPanel steps={currentTools} />
        )}
        <div className="markdown-body">
          {showStreaming ? (
            <pre className="whitespace-pre-wrap font-sans text-sm">{msg.text}<span className="animate-pulse">▌</span></pre>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                if (match && match[1] === 'mermaid') {
                  return <MermaidChart chart={String(children).trim()} />;
                }
                return <code className={className} {...props}>{children}</code>;
              }
            }}>{msg.text}</ReactMarkdown>
          )}
        </div>
      </div>
    </div>
  );
}, (prev, next) => {
  // Only re-render if this message actually changed
  if (prev.msg.text !== next.msg.text) return false;
  if (prev.msg.toolSteps?.length !== next.msg.toolSteps?.length) return false;
  if (prev.isLast !== next.isLast) return false;
  if (prev.isLast && prev.isLoading !== next.isLoading) return false;
  if (prev.isLast && prev.currentTools.length !== next.currentTools.length) return false;
  return true;
});

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
  const [sessionId, setSessionId] = useState(() => {
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
    let lastToolCount = 0;

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
          const newTools = tools.slice(lastToolCount);
          updateLast(buf, newTools.length > 0 ? newTools : undefined);
        },
        (name: string, toolInput: string) => {
          if (!name && tools.length > 0) {
            tools[tools.length - 1].input = toolInput;
          } else if (name) {
            tools.push({ name, input: toolInput, done: false });
          }
          setCurrentTools([...tools]);
          const newTools = tools.slice(lastToolCount);
          updateLast(buf, newTools);
        },
        (result, isError) => {
          const last = tools[tools.length - 1];
          if (last) { last.result = result; last.isError = isError; last.done = true; }
          buf += "\n";
          setCurrentTools([...tools]);
          const newTools = tools.slice(lastToolCount);
          updateLast(buf, newTools);
        }
      );
    } catch (error: any) {
      buf += `\n\n❌ 오류: ${error.message}`;
    } finally {
      const finalTools = tools.slice(lastToolCount);
      if (buf.trim() || finalTools.length > 0) updateLast(buf, finalTools.length > 0 ? finalTools : undefined);
      setIsLoading(false);
      setCurrentTools([]);
    }
  };

  const ToolPanel = ({ steps }: { steps: ToolStep[] }) => (
    <div className="space-y-1.5">
      {steps.map((step, idx) => {
        let queryDisplay = '';
        if (step.input) {
          try { const p = JSON.parse(step.input); queryDisplay = p.query || step.input; } catch { queryDisplay = step.input; }
        }
        return (
          <div key={`${step.name}-${idx}`} className={cn(
            "px-3 py-2 rounded-lg text-xs transition-all duration-300",
            step.done
              ? step.isError ? "bg-red-50 border border-red-200" : "bg-green-50 border border-green-200"
              : "bg-blue-50 border border-blue-200 animate-pulse"
          )}>
            <div className="flex items-center gap-2">
              {step.done ? (
                step.isError ? <X className="w-3.5 h-3.5 text-red-500" /> : <Check className="w-3.5 h-3.5 text-green-500" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5 text-blue-500 animate-spin" />
              )}
              <span className="font-semibold text-slate-700">{step.name}</span>
              {step.done && <span className="text-slate-400 ml-auto text-[10px]">{step.isError ? 'error' : 'done'}</span>}
            </div>
            {queryDisplay && (
              <div className="mt-1.5 px-2 py-1 rounded bg-slate-800 text-green-300 text-[11px] font-mono whitespace-pre-wrap break-all max-h-[10rem] overflow-auto">{queryDisplay}</div>
            )}
          </div>
        );
      })}
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
            <h1 className="text-lg md:text-xl font-bold text-slate-800 tracking-tight">
              🏥 Medical AI Agent{' '}
              {(window as any).__APP_MODE__ === 'legacy' && (
                <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">Legacy</span>
              )}
            </h1>
            <p className="text-[10px] md:text-xs text-slate-500 font-medium">{t.subtitle}</p>
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
              onClick={() => { setMessages([]); setCurrentTools([]); setExpandedScenario(null); const hex = () => Math.random().toString(16).slice(2); setSessionId(`${hex()}${hex()}-${hex()}-${hex()}-${hex()}-${hex()}${hex()}${hex()}-aaaaaaaaaa`); }}
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
          <div
            key={idx}
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
              {msg.role === 'model' && msg.toolSteps && msg.toolSteps.length > 0 && (
                <ToolPanel steps={msg.toolSteps} />
              )}
              {msg.role === 'model' && isLoading && idx === messages.length - 1 && currentTools.length > 0 && (
                <ToolPanel steps={currentTools} />
              )}
              <div className="markdown-body">
                {msg.role === 'model' && isLoading && idx === messages.length - 1 ? (
                  <pre className="whitespace-pre-wrap font-sans text-sm">{msg.text}<span className="animate-pulse">▌</span></pre>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{msg.text}</ReactMarkdown>
                )}
              </div>
            </div>
          </div>
        ))}



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
