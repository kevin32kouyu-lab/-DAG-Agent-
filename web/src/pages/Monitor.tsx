import { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { useWebSocket } from '../hooks/useWebSocket';
import { useDemoSimulation } from '../hooks/useDemoSimulation';
import { useTaskContext } from '../hooks/useTaskContext';
import { useToast } from '../hooks/useToast';
import type { AgentType, NodeState, WSEvent } from '../types';

// ── Agent 流水线定义 ──
interface PipelineAgent {
  id: string;
  label: string;
  icon: string;
  color: string;
  dependsOn: string[];
  /** 从 KG 查询的节点类型，用于显示实际产出 */
  outputTypes: string[];
}

const PIPELINE: PipelineAgent[] = [
  // Phase 1: 意图理解
  { id: 'intent', label: '意图理解', icon: '🧠', color: '#6366f1',
    dependsOn: [], outputTypes: [] },
  // Phase 2: 数据采集
  { id: 'collector', label: '信息采集', icon: '🔍', color: '#3b82f6',
    dependsOn: ['intent'], outputTypes: ['SourceInfo', 'WebPage'] },
  { id: 'enricher', label: '数据清洗', icon: '🧹', color: '#0ea5e9',
    dependsOn: ['collector'], outputTypes: [] },
  // Phase 3: 并行分析
  { id: 'feature_analysis', label: '功能分析', icon: '⚡', color: '#8b5cf6',
    dependsOn: ['enricher'], outputTypes: ['FeatureNode'] },
  { id: 'pricing_analysis', label: '定价分析', icon: '💰', color: '#f59e0b',
    dependsOn: ['enricher'], outputTypes: ['PricingModel', 'PricingData'] },
  { id: 'sentiment_analysis', label: '口碑分析', icon: '💬', color: '#ec4899',
    dependsOn: ['enricher'], outputTypes: ['SentimentNode'] },
  { id: 'market_position', label: '市场定位', icon: '📍', color: '#06b6d4',
    dependsOn: ['enricher'], outputTypes: ['MarketPosition'] },
  // Phase 4: 综合报告
  { id: 'cross_review', label: '交叉审查', icon: '🔀', color: '#14b8a6',
    dependsOn: ['feature_analysis','pricing_analysis','sentiment_analysis','market_position'], outputTypes: [] },
  { id: 'report', label: '报告生成', icon: '📝', color: '#10b981',
    dependsOn: ['cross_review'], outputTypes: ['SWOTNode', 'ScoringNode', 'ReportSection'] },
  // Phase 5: 质量校核
  { id: 'qa_fact', label: '事实校验', icon: '🔎', color: '#f97316',
    dependsOn: ['report'], outputTypes: [] },
  { id: 'qa_logic', label: '逻辑校验', icon: '🌳', color: '#ef4444',
    dependsOn: ['qa_fact'], outputTypes: [] },
];

const AGENT_ZH: Record<string, string> = {
  Orchestrator: '意图理解', Collector: '信息采集', Analyst: '分析师', ReportGenerator: '报告生成', QA: '质量校核',
};

const PHASE_EN: Record<string, string> = {
  '阶段一：意图理解': 'Intent Understanding',
  '阶段二：数据采集与清洗': 'Collection & Enrichment',
  '阶段三：多维度并行分析': 'Parallel Analysis',
  '阶段四：交叉审查与报告生成': 'Review & Report',
  '阶段五：双重质量校核': 'Quality Assurance',
};

const STATE_CONFIG: Record<string, { icon: string; label: string; className: string }> = {
  completed: { icon: '✅', label: '已完成', className: 'border-green-300 bg-green-50' },
  running: { icon: '🔄', label: '运行中', className: 'border-blue-300 bg-blue-50 animate-pulse' },
  failed: { icon: '❌', label: '失败', className: 'border-red-300 bg-red-50' },
  pending: { icon: '⏳', label: '等待中', className: 'border-slate-200 bg-slate-50/50 opacity-50' },
  degraded: { icon: '⚠️', label: '降级', className: 'border-amber-300 bg-amber-50' },
};

// ── 组件 ──
export default function Monitor() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const isDemo = searchParams.get('demo') === 'true';
  const demoTaskId = searchParams.get('task') || id || '';

  const wsResult = useWebSocket(isDemo ? '' : (id || ''));
  const demoResult = useDemoSimulation(isDemo ? demoTaskId : '');
  const { events, connectionStatus } = isDemo ? demoResult : wsResult;
  const { setWsConnected } = useTaskContext();
  const { toast } = useToast();

  const [agentStates, setAgentStates] = useState<Record<string, NodeState>>(() => {
    const init: Record<string, NodeState> = {};
    PIPELINE.forEach(a => { init[a.id] = 'pending'; });
    return init;
  });
  const [logs, setLogs] = useState<string[]>([]);
  const [nodeCounts, setNodeCounts] = useState<Record<string, number>>({});
  const processedCount = useRef(0);
  const completionNotified = useRef(false);

  useEffect(() => {
    setWsConnected(connectionStatus === 'connected');
    return () => { setWsConnected(false); };
  }, [connectionStatus, setWsConnected]);

  // 加载实际节点数
  useEffect(() => {
    const taskId = isDemo ? demoTaskId : id;
    if (!taskId) return;
    fetch(`/api/report/${taskId}/analytics`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d?.source_stats?.details) return;
        const counts: Record<string, number> = {};
        for (const item of d.source_stats.details) {
          counts[item.type] = item.count;
        }
        setNodeCounts(counts);
      })
      .catch(() => {});
  }, [isDemo, demoTaskId, id]);

  // 处理 WS / Demo 事件
  useEffect(() => {
    const newEvents = events.slice(processedCount.current);
    if (newEvents.length === 0) return;
    for (const raw of newEvents) {
      const evt = raw as WSEvent;
      if (!evt?.event) continue;
      if (evt.event === 'node_state_change' || evt.event === 'node_completed') {
        const state = evt.event === 'node_completed' ? 'completed' : (evt.state as NodeState);
        setAgentStates(prev => {
          const next = { ...prev };
          if (evt.node_id) next[evt.node_id] = state;
          return next;
        });
      }
      if (evt.event === 'agent_log') {
        const le = evt as { agent_type: string; step: number; phase: string; summary: string };
        const zhName = AGENT_ZH[le.agent_type] || le.agent_type;
        setLogs(prev => [...prev.slice(-99), `[${zhName}] · 第${le.step}步 · ${le.phase}：${le.summary}`]);
      }
    }
    processedCount.current = events.length;
  }, [events]);

  const completed = Object.values(agentStates).filter(s => s === 'completed').length;
  const total = PIPELINE.length;
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  // 自动跳转
  useEffect(() => {
    if (completionNotified.current || total === 0) return;
    if (Object.values(agentStates).every(s => s === 'completed')) {
      completionNotified.current = true;
      toast('分析完成，跳转报告...', 'success');
      if (isDemo) setTimeout(() => navigate(`/task/${demoTaskId}/report?demo=true&task=${demoTaskId}`), 3000);
    }
  }, [agentStates, isDemo, demoTaskId, navigate, toast, total]);

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col animate-pageEnter bg-surface-container/30">
      {/* ── Top Bar ── */}
      <div className="shrink-0 px-5 py-3 border-b border-border-subtle bg-surface">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="font-headline text-sm font-semibold text-on-surface">分析进度</h1>
          {isDemo && <span className="rounded-full bg-gradient-to-r from-violet-500 to-blue-500 px-2 py-0.5 text-[10px] font-semibold text-white">演示</span>}
          <div className="flex items-center gap-3 text-xs text-on-surface-variant ml-auto">
            <span className="font-semibold text-on-surface">{completed}/{total} 完成</span>
            <span className="text-slate-300">|</span>
            {(() => {
              const l1 = (nodeCounts['SourceInfo']||0)+(nodeCounts['WebPage']||0);
              const l2 = (nodeCounts['FeatureNode']||0)+(nodeCounts['SentimentNode']||0)+(nodeCounts['PricingModel']||0)+(nodeCounts['PricingData']||0)+(nodeCounts['MarketPosition']||0);
              const l3 = (nodeCounts['SWOTNode']||0)+(nodeCounts['ScoringNode']||0)+(nodeCounts['ReportSection']||0);
              return <><span>{(l1+l2+l3).toLocaleString()} 节点</span><span className="text-slate-300 ml-2 mr-2">|</span><span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-300" />{l1}</span><span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-300" />{l2}</span><span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-300" />{l3}</span></>;
            })()}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-2 rounded-full bg-surface-container-highest overflow-hidden">
            <div className="h-full rounded-full transition-all duration-1000 ease-out bg-gradient-to-r from-blue-500 to-emerald-500"
              style={{ width: `${Math.max(progress, 4)}%` }} />
          </div>
          <span className="text-xs font-bold text-on-surface min-w-[3ch]">{progress}%</span>
        </div>
      </div>

      {/* ── Main: Pipeline (left) + Stats Panel (right) ── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Pipeline */}
        <div className="flex-1 overflow-auto p-4">
          <div className="flex items-start gap-0 min-w-max">
            <PhaseColumn phase="阶段一：意图理解" phaseEn="Intent" agents={PIPELINE.filter(a => a.id === 'intent')} agentStates={agentStates} nodeCounts={nodeCounts} />
            <FlowArrowH active={agentStates.intent === 'completed'} />
            <PhaseColumn phase="阶段二：采集与清洗" phaseEn="Collection" agents={PIPELINE.filter(a => a.id === 'collector' || a.id === 'enricher')} agentStates={agentStates} nodeCounts={nodeCounts} />
            <FlowArrowH active={agentStates.enricher === 'completed'} />
            <PhaseColumn phase="阶段三：并行分析" phaseEn="Analysis" agents={PIPELINE.filter(a => ['feature_analysis','pricing_analysis','sentiment_analysis','market_position'].includes(a.id))} agentStates={agentStates} nodeCounts={nodeCounts} />
            <FlowArrowH active={['feature_analysis','pricing_analysis','sentiment_analysis','market_position'].every(id => agentStates[id] === 'completed')} />
            <PhaseColumn phase="阶段四：审查与报告" phaseEn="Review & Report" agents={PIPELINE.filter(a => a.id === 'cross_review' || a.id === 'report')} agentStates={agentStates} nodeCounts={nodeCounts} />
            <FlowArrowH active={agentStates.report === 'completed'} />
            <PhaseColumn phase="阶段五：质量校核" phaseEn="QA" agents={PIPELINE.filter(a => a.id === 'qa_fact' || a.id === 'qa_logic')} agentStates={agentStates} nodeCounts={nodeCounts} />
          </div>
        </div>

        {/* Right: Stats Panel */}
        <StatsPanel agentStates={agentStates} nodeCounts={nodeCounts} logs={logs} />
      </div>

      {/* ── Bottom: Log Stream ── */}
      <div className="shrink-0 border-t border-border-subtle bg-surface px-5 py-3 max-h-36 overflow-y-auto">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-on-surface-variant">执行日志</span>
          <span className="text-[11px] text-on-surface-variant/30">({logs.length} 条)</span>
        </div>
        <div className="space-y-1">
          {logs.length === 0 && <p className="text-xs text-on-surface-variant/30">等待 Agent 启动...</p>}
          {logs.slice(-8).map((l, i) => (
            <p key={i} className="text-[11px] text-on-surface-variant/50 truncate hover:text-on-surface-variant transition-colors">{l}</p>
          ))}
        </div>
      </div>

    </div>
  );
}

// ── 水平阶段列 ──
function PhaseColumn({ phase, phaseEn, agents, agentStates, nodeCounts }: {
  phase: string; phaseEn: string;
  agents: PipelineAgent[];
  agentStates: Record<string, NodeState>;
  nodeCounts: Record<string, number>;
}) {
  const allDone = agents.every(a => agentStates[a.id] === 'completed');
  const anyRunning = agents.some(a => agentStates[a.id] === 'running');

  return (
    <div className={`flex flex-col rounded-xl border-2 transition-all duration-700 ${allDone ? 'border-green-200 bg-green-50/20' : anyRunning ? 'border-blue-200 bg-blue-50/10' : 'border-slate-200 bg-white'}`}
      style={{ width: 280, minWidth: 280 }}>
      {/* Phase header */}
      <div className="px-4 pt-3 pb-2 border-b border-slate-100">
        <p className="text-xs font-semibold text-slate-600">{phase}</p>
        <p className="text-[10px] text-slate-400">{phaseEn}</p>
      </div>
      {/* Agent cards */}
      <div className="flex-1 p-2 space-y-2">
        {agents.map(a => {
          const state = agentStates[a.id] || 'pending';
          const cfg = STATE_CONFIG[state] || STATE_CONFIG.pending;
          const outputCounts: { label: string; count: number }[] = [];
          for (const ot of a.outputTypes) {
            const c = nodeCounts[ot];
            if (c !== undefined && c > 0) outputCounts.push({ label: NODE_TYPE_ZH[ot] || ot, count: c });
          }

          return (
            <div key={a.id} className={`rounded-lg border px-4 py-3 transition-all duration-500 ${cfg.className} ${state === 'running' ? 'shadow-lg shadow-blue-200/50 scale-[1.02]' : ''}`}>
              <div className="flex items-center gap-2.5 mb-2">
                <span className="text-xl flex-shrink-0">{a.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-slate-800 leading-tight truncate">{a.label}</p>
                  <p className="text-[10px] text-slate-400 leading-tight">{a.id}</p>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${state === 'completed' ? 'bg-green-100 text-green-700' : state === 'running' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>
                  {cfg.label}
                </span>
                {outputCounts.length > 0 && (
                  <span className="text-[11px] font-bold text-slate-500">{outputCounts.map(c => c.count).join('/')}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 横向连接箭头 ──
function FlowArrowH({ active }: { active: boolean }) {
  return (
    <div className="flex items-center justify-center flex-shrink-0" style={{ width: 40 }}>
      <div className="flex items-center">
        <div className={`w-6 h-0.5 transition-all duration-1000 ${active ? 'bg-gradient-to-r from-blue-400 to-violet-400' : 'bg-slate-200'}`} />
        <div className={`w-0 h-0 border-t-[5px] border-t-transparent border-b-[5px] border-b-transparent border-l-[7px] transition-all duration-1000 ${active ? 'border-l-violet-400' : 'border-l-slate-300'}`} />
      </div>
    </div>
  );
}

// ── 右侧统计面板 ──
function StatsPanel({ agentStates, nodeCounts, logs }: {
  agentStates: Record<string, NodeState>;
  nodeCounts: Record<string, number>;
  logs: string[];
}) {
  const completed = Object.values(agentStates).filter(s => s === 'completed').length;
  const total = Object.keys(agentStates).length;
  const l1 = (nodeCounts['SourceInfo']||0)+(nodeCounts['WebPage']||0);
  const l2 = (nodeCounts['FeatureNode']||0)+(nodeCounts['SentimentNode']||0)+(nodeCounts['PricingModel']||0)+(nodeCounts['PricingData']||0)+(nodeCounts['MarketPosition']||0);
  const l3 = (nodeCounts['SWOTNode']||0)+(nodeCounts['ScoringNode']||0)+(nodeCounts['ReportSection']||0);

  return (
    <div className="w-60 shrink-0 border-l border-border-subtle bg-surface-container/30 p-4 flex flex-col gap-5 overflow-y-auto">
      {/* 进度 */}
      <div>
        <p className="text-[11px] font-semibold text-slate-400 mb-2.5 tracking-wide">任务概览</p>
        <div className="space-y-2.5">
          <div className="flex justify-between text-sm"><span className="text-slate-500">进度</span><span className="font-bold text-slate-700">{completed}/{total}</span></div>
          <div className="flex justify-between text-sm"><span className="text-slate-500">节点</span><span className="font-bold text-slate-700">{(l1+l2+l3).toLocaleString()}</span></div>
        </div>
      </div>
      {/* 分层 */}
      <div>
        <p className="text-[11px] font-semibold text-slate-400 mb-2.5 tracking-wide">图谱分层</p>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm"><span className="w-2.5 h-2.5 rounded-full bg-blue-300" /><span className="text-slate-500 flex-1">原始数据</span><span className="font-bold text-slate-700">{l1.toLocaleString()}</span></div>
          <div className="flex items-center gap-2 text-sm"><span className="w-2.5 h-2.5 rounded-full bg-purple-300" /><span className="text-slate-500 flex-1">分析结果</span><span className="font-bold text-slate-700">{l2.toLocaleString()}</span></div>
          <div className="flex items-center gap-2 text-sm"><span className="w-2.5 h-2.5 rounded-full bg-emerald-300" /><span className="text-slate-500 flex-1">报告输出</span><span className="font-bold text-slate-700">{l3.toLocaleString()}</span></div>
        </div>
      </div>
      {/* 最近日志 */}
      <div className="flex-1 min-h-0">
        <p className="text-[11px] font-semibold text-slate-400 mb-2.5 tracking-wide">最近动态</p>
        <div className="space-y-1.5">
          {logs.slice(-5).reverse().map((l, i) => (
            <p key={i} className="text-xs text-slate-500 leading-relaxed truncate">{l}</p>
          ))}
        </div>
      </div>
    </div>
  );
}

const NODE_TYPE_ZH: Record<string, string> = {
  SourceInfo: '来源链接', WebPage: '网页内容',
  FeatureNode: '功能特征', SentimentNode: '用户口碑',
  PricingModel: '定价模型', PricingData: '定价明细',
  MarketPosition: '市场定位', SWOTNode: 'SWOT分析',
  ScoringNode: '维度评分', ReportSection: '报告章节',
};
