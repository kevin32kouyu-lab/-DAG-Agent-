import { StatusDot } from './StatusBadge';
import type { AgentState, NodeState } from '../types';

/* ---- agent type display name ---- */

const AGENT_NAMES: Record<string, string> = {
  Orchestrator: '编排器',
  Collector: '信息采集',
  Analyst: '分析师',
  ReportGenerator: '报告撰写',
  QA: '质检',
};

/* ---- progress bar helper ---- */

function ProgressBar({ pct }: { pct?: number }) {
  if (pct === undefined || pct < 0) return null;
  return (
    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
      <div
        className="h-full rounded-full bg-teal-700 transition-all duration-700 animate-pulse"
        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
      />
    </div>
  );
}

/* ---- props ---- */

interface AgentCardProps {
  agent: AgentState;
  variant?: 'compact' | 'detailed';
}

/* ---- component ---- */

export default function AgentCard({ agent, variant = 'compact' }: AgentCardProps) {
  const name = AGENT_NAMES[agent.agent_type] || agent.agent_type;
  const stateLabel: Record<NodeState, string> = {
    completed: '✓ 完成', running: '◐ 运行中', failed: '✕ 失败',
    pending: '○ 等待', ready: '◉ 就绪', degraded: '⚠ 降级',
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition-all hover:border-teal-200 active:scale-[0.98] animate-slideUp stagger-item">
      {/* header */}
      <div className="flex items-center gap-2 mb-1">
        <StatusDot state={agent.state} />
        <span className="text-xs uppercase text-slate-500">{stateLabel[agent.state]}</span>
        {agent.duration && (
          <span className="ml-auto font-mono text-xs text-slate-500">{agent.duration}</span>
        )}
      </div>

      <div className="text-sm font-medium text-slate-900">{name}</div>

      {/* progress bar */}
      {agent.state === 'running' && <ProgressBar pct={agent.progress} />}

      {/* details */}
      {variant === 'detailed' && agent.outputSummary && (
        <div className="mt-1 text-xs text-slate-600">{agent.outputSummary}</div>
      )}
      {variant === 'detailed' && agent.details && (
        <div className="mt-0.5 text-xs text-slate-500">{agent.details}</div>
      )}

      {/* compact output */}
      {variant === 'compact' && agent.outputSummary && (
        <div className="mt-1 truncate text-xs text-slate-600">{agent.outputSummary}</div>
      )}

      {/* cost */}
      {agent.cost !== undefined && (
        <div className="mt-1 font-mono text-xs text-slate-500">${agent.cost.toFixed(4)}</div>
      )}
    </div>
  );
}

export { AGENT_NAMES };
