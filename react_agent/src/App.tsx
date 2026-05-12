import React, { useState, useRef, useEffect } from 'react';
import {
  Stethoscope, Send, User, Bot,
  RefreshCw, Info, Wrench, Check, X, ChevronDown, ChevronRight, LogOut
} from 'lucide-react';
import { useAuth } from './AuthContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from './lib/utils';
import { streamAgentResponse, ChatMessage } from './services/agent';
import { motion, AnimatePresence } from 'motion/react';
import { getT, setLocale, getLocale, subscribeLocale, type Locale } from './i18n';

// Hook that re-renders the component tree whenever the user toggles the
// active locale.
function useLocale(): [ReturnType<typeof getT>, Locale, (l: Locale) => void] {
  const [loc, setLoc] = useState<Locale>(() => getLocale());
  useEffect(() => subscribeLocale(setLoc), []);
  return [getT(), loc, setLocale];
}
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import ForceGraph2D from 'react-force-graph-2d';

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

// ───────────────────────────────────────────────────────────────
// DiseaseTree: ICD-10 / SNOMED hierarchy visualisation produced by
// medical_ontology MCP tools (expand_disease_term / get_disease_hierarchy).
// ───────────────────────────────────────────────────────────────
const RELATION_COLOR: Record<string, string> = {
  primary:          'bg-blue-100 text-blue-800 border-blue-300',
  complication:     'bg-rose-100 text-rose-800 border-rose-300',
  comorbidity:      'bg-amber-100 text-amber-800 border-amber-300',
  context_specific: 'bg-purple-100 text-purple-800 border-purple-300',
  history:          'bg-slate-100 text-slate-600 border-slate-300',
  symptom:          'bg-emerald-100 text-emerald-800 border-emerald-300',
};
const DiseaseTree = React.memo(({ config }: { config: any }) => {
  const { title, chapter, block, nodes = [], children = [] } = config || {};
  const maxPatients = Math.max(1, ...nodes.map((n: any) => Number(n.patients) || 0));
  return (
    <div className="my-4 border border-slate-200 rounded-lg p-3 bg-white">
      {title && <div className="text-sm font-semibold text-slate-800 mb-2">🧬 {title}</div>}
      {chapter && (
        <div className="text-xs text-slate-500 mb-1">
          <span className="inline-block min-w-[60px] font-mono">{chapter.range}</span>
          {chapter.label || chapter.label_en || chapter.label_ko}
        </div>
      )}
      {block && (
        <div className="text-xs text-slate-600 mb-2 pl-4">
          <span className="inline-block min-w-[60px] font-mono">{block.range}</span>
          {block.label || block.label_en || block.label_ko}
        </div>
      )}
      {nodes.length > 0 && (
        <div className="space-y-1.5 mt-2">
          {nodes.map((n: any, idx: number) => {
            const pts = Number(n.patients) || 0;
            const pct = Math.min(100, Math.round((pts / maxPatients) * 100));
            const rel = (n.relation || 'primary') as string;
            const relCls = RELATION_COLOR[rel] || RELATION_COLOR.primary;
            return (
              <div key={n.code || idx} className="flex items-center gap-2 text-xs">
                <span className="font-mono font-semibold w-20 shrink-0 truncate" title={n.code}>{n.code}</span>
                <span className="truncate text-slate-700 w-40 shrink-0" title={n.label}>{n.label || ''}</span>
                <span className={cn('border rounded px-1.5 py-0.5 text-[10px] font-medium', relCls)}>{rel}</span>
                <div className="flex-1 bg-slate-100 rounded h-4 relative overflow-hidden">
                  {pts > 0 && <div className="h-full bg-blue-400" style={{ width: `${pct}%` }} />}
                </div>
                <span className="font-mono text-slate-600 w-14 text-right tabular-nums">{pts.toLocaleString()}</span>
              </div>
            );
          })}
        </div>
      )}
      {children.length > 0 && (
        <div className="mt-3 pt-2 border-t border-dashed border-slate-200">
          <div className="text-[11px] text-slate-500 mb-1">Sub-codes ({children.length})</div>
          <div className="grid grid-cols-2 gap-1 text-[11px]">
            {children.slice(0, 10).map((c: any, i: number) => (
              <div key={c.code || i} className="truncate" title={`${c.code} ${c.label || ''}`}>
                <span className="font-mono text-slate-500">{c.code}</span>
                <span className="text-slate-700 ml-1">{c.label}</span>
              </div>
            ))}
          </div>
          {children.length > 10 && <div className="text-[10px] text-slate-400 mt-1">…+{children.length - 10}</div>}
        </div>
      )}
    </div>
  );
});

// ───────────────────────────────────────────────────────────────
// DiseaseGraph: force-directed relationship view
// ───────────────────────────────────────────────────────────────
const GRAPH_GROUP_COLOR: Record<string, string> = {
  primary:          '#2563eb',
  complication:     '#e11d48',
  comorbidity:      '#d97706',
  synonym:          '#6b7280',
  context_specific: '#9333ea',
  history:          '#64748b',
  symptom:          '#059669',
};
const GRAPH_EDGE_COLOR: Record<string, string> = {
  complication: '#fb7185',
  comorbidity:  '#fbbf24',
  synonym:      '#9ca3af',
  parent:       '#60a5fa',
  default:      '#cbd5e1',
};
const DiseaseGraph = React.memo(({ config }: { config: any }) => {
  const { title, nodes = [], links = [] } = config || {};
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [width, setWidth] = useState(600);
  const height = 480;
  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      if (w > 0) setWidth(Math.floor(w));
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    const charge = -90 - Math.min(8, nodes.length) * 10;
    if (fg.d3Force) {
      try { fg.d3Force('charge').strength(charge); } catch {}
      try { fg.d3Force('link').distance(90).strength(0.6); } catch {}
      try { fg.d3Force('center').strength(0.05); } catch {}
    }
    if (fg.d3ReheatSimulation) fg.d3ReheatSimulation();
  }, [nodes.length]);
  const nodeRadius = (n: any): number => {
    const p = Math.max(0, Number(n.patients) || 0);
    return 5 + Math.min(10, Math.log2(p + 1) * 2);
  };
  const data = {
    nodes: nodes.map((n: any) => ({
      ...n,
      __r: nodeRadius(n),
      __color: GRAPH_GROUP_COLOR[n.group || 'primary'] || GRAPH_GROUP_COLOR.primary,
    })),
    links: links.map((l: any) => ({
      ...l,
      __color: GRAPH_EDGE_COLOR[l.type || 'default'] || GRAPH_EDGE_COLOR.default,
    })),
  };
  const uniqueGroups = Array.from(new Set(nodes.map((n: any) => n.group || 'primary'))) as string[];
  return (
    <div className="my-4 border border-slate-200 rounded-lg p-3 bg-white">
      {title && <div className="text-sm font-semibold text-slate-800 mb-2">🌐 {title}</div>}
      <div className="flex flex-wrap gap-3 text-[11px] text-slate-600 mb-2">
        {uniqueGroups.map((g) => (
          <span key={g} className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: GRAPH_GROUP_COLOR[g] || GRAPH_GROUP_COLOR.primary }} />
            {g}
          </span>
        ))}
      </div>
      <div ref={containerRef} className="w-full" style={{ height }}>
        <ForceGraph2D
          ref={fgRef}
          graphData={data}
          width={width}
          height={height}
          backgroundColor="#ffffff"
          linkColor={(link: any) => link.__color}
          linkWidth={1.2}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={0.95}
          nodeCanvasObjectMode={() => 'replace'}
          nodeCanvasObject={(node: any, ctx: any, scale: number) => {
            const r = node.__r || 6;
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
            ctx.fillStyle = node.__color;
            ctx.fill();
            ctx.lineWidth = 1 / scale;
            ctx.strokeStyle = 'rgba(0,0,0,0.25)';
            ctx.stroke();
            const label = node.label ? `${node.id} ${node.label}` : String(node.id);
            const fontSize = Math.max(8, 11 / Math.max(1, scale));
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillStyle = '#0f172a';
            ctx.fillText(label, node.x, node.y + r + 2);
          }}
          nodePointerAreaPaint={(node: any, color: any, ctx: any) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, (node.__r || 6) + 2, 0, 2 * Math.PI, false);
            ctx.fill();
          }}
          nodeLabel={(n: any) =>
            `${n.id}${n.label ? ' - ' + n.label : ''}${n.patients != null ? ` (patients ${n.patients})` : ''}`
          }
          cooldownTicks={120}
          d3VelocityDecay={0.3}
        />
      </div>
    </div>
  );
});

// Parse a JSON snippet that may represent chart / disease_tree / disease_graph.
function tryRenderJson(text: string): React.ReactElement | null {
  const s = text.trim();
  if (!(s.startsWith('{"chart"') || s.startsWith('{"disease_tree"') || s.startsWith('{"disease_graph"'))) return null;
  const attempts: string[] = [s,
    s.replace(/\r/g, '').replace(/\n/g, ' '),
    s.replace(/[\u0000-\u001F]+/g, ' '),
  ];
  for (const candidate of attempts) {
    try {
      const parsed = JSON.parse(candidate);
      if (parsed.chart) return <DataChart config={parsed.chart} />;
      if (parsed.disease_tree) return <DiseaseTree config={parsed.disease_tree} />;
      if (parsed.disease_graph) return <DiseaseGraph config={parsed.disease_graph} />;
    } catch {}
  }
  return null;
}

function splitJsonPayloads(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /\{"(chart|disease_tree|disease_graph)"\s*:[^]*?\}\s*\}/g;
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    const prefix = text.slice(lastIdx, m.index);
    if (prefix) out.push(<React.Fragment key={`t${key++}`}>{prefix}</React.Fragment>);
    const rendered = tryRenderJson(m[0]);
    if (rendered) out.push(<React.Fragment key={`j${key++}`}>{rendered}</React.Fragment>);
    else out.push(<React.Fragment key={`t${key++}`}>{m[0]}</React.Fragment>);
    lastIdx = m.index + m[0].length;
  }
  const tail = text.slice(lastIdx);
  if (tail) out.push(<React.Fragment key={`t${key++}`}>{tail}</React.Fragment>);
  return out;
}

const mdComponents = {
  code({ className, children, ...props }: any) {
    const text = String(children).trim();
    const rendered = tryRenderJson(text);
    if (rendered) return rendered;
    // Legacy mermaid support
    const match = /language-(\w+)/.exec(className || '');
    if (match && match[1] === 'mermaid') {
      return <pre className="text-xs bg-slate-100 p-2 rounded">{text}</pre>;
    }
    return <code className={className} {...props}>{children}</code>;
  },
  // Defensive: agent 가 fence 를 빠뜨려 JSON 이 paragraph 안에 들어가는 케이스 처리
  p({ children, ...props }: any) {
    const mapped = React.Children.toArray(children).flatMap((child, i) => {
      if (typeof child === 'string') {
        const parts = splitJsonPayloads(child);
        return parts.length ? parts.map((p, j) =>
          React.isValidElement(p) ? React.cloneElement(p, { key: `p${i}-${j}` }) : p
        ) : [child];
      }
      return [child];
    });
    const hasBlock = mapped.some((c) => React.isValidElement(c) &&
      ((c.type as any) === DataChart || (c.type as any) === DiseaseTree || (c.type as any) === DiseaseGraph));
    if (hasBlock) return <div className="space-y-2">{mapped}</div>;
    return <p {...props}>{mapped}</p>;
  },
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

const SCENARIOS_FALLBACK = getT().scenarioItems;
// Note: the real SCENARIOS list is read reactively inside <App/> via useLocale().
// The fallback above only exists so any stray module-level reference (should be none)
// still compiles. Prefer `scenarios` from the App component.
void SCENARIOS_FALLBACK;

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
  const { tokens, email, loading, signIn, signOut, getAccessToken, authDisabled } = useAuth();
  const [t, locale, changeLocale] = useLocale();
  const SCENARIOS = t.scenarioItems;
  const [messages, setMessages] = useState<MessageWithTools[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentTools, setCurrentTools] = useState<ToolStep[]>([]);
  const [expandedScenario, setExpandedScenario] = useState<number | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
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

  // ── Auth gate ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <div className="w-8 h-8 border-4 border-sky-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  if (!tokens) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-6 p-8 bg-white rounded-2xl shadow-lg border border-slate-200 max-w-sm w-full mx-4">
          <div className="bg-sky-500 p-4 rounded-2xl">
            <Stethoscope className="w-10 h-10 text-white" />
          </div>
          <div className="text-center space-y-1">
            <h1 className="text-xl font-bold text-slate-800">Medical AI Agent</h1>
            <p className="text-sm text-slate-500">로그인하여 서비스를 이용하세요</p>
          </div>
          <button
            onClick={signIn}
            className="w-full bg-sky-600 hover:bg-sky-700 text-white font-semibold py-3 px-6 rounded-xl transition-colors shadow-md shadow-sky-500/20"
          >
            Cognito로 로그인
          </button>
        </div>
      </div>
    );
  }

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isLoading) return;

    setMessages(prev => [...prev, { role: 'user', text: msg }]);
    setInput('');
    setIsLoading(true);
    setCurrentTools([]);
    setElapsedTime(0);
    timerRef.current = setInterval(() => setElapsedTime(t => t + 1), 1000);

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
      const accessToken = await getAccessToken() ?? undefined;
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
        },
        undefined,
        accessToken,
      );
    } catch (error: any) {
      buf += `\n\n❌ 오류: ${error.message}`;
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
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
        <div className="flex items-center gap-3">
          {/* Language toggle */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
            {(['ko','en'] as const).map((lng) => (
              <button
                key={lng}
                type="button"
                onClick={() => changeLocale(lng)}
                aria-pressed={locale === lng}
                className={cn(
                  'px-2 py-1 rounded-md transition-colors',
                  locale === lng
                    ? 'bg-white text-sky-600 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                {lng === 'ko' ? '한국어' : 'English'}
              </button>
            ))}
          </div>
          {!authDisabled && <span className="text-xs text-slate-500 hidden md:block">{email}</span>}
          {!authDisabled && (
            <button
              onClick={signOut}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-red-500 transition-colors px-2 py-1 rounded-lg hover:bg-red-50"
              title="로그아웃"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden md:block">로그아웃</span>
            </button>
          )}
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
              onClick={() => { setMessages([]); setCurrentTools([]); setIsLoading(false); setElapsedTime(0); if (timerRef.current) clearInterval(timerRef.current); setExpandedScenario(null); const hex = () => Math.random().toString(16).slice(2); setSessionId(`${hex()}${hex()}-${hex()}-${hex()}-${hex()}-${hex()}${hex()}${hex()}-aaaaaaaaaa`); }}
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
                  <>
                    <pre className="whitespace-pre-wrap font-sans text-sm">{msg.text}<span className="animate-pulse">▌</span></pre>
                    <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      <span>{t.analyzing}</span>
                      <span className="font-mono">{elapsedTime}s</span>
                    </div>
                  </>
                ) : (                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{msg.text}</ReactMarkdown>
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
