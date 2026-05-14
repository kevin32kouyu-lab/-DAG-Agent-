import { StatusDot } from './StatusBadge';
import type { AgentState, NodeState } from '../types';

/* ---- agent type display name ---- */

const AGENT_NAMES: Record<string, string> = {
  Orchestrator: 'Orchestrator',
  SourceDiscovery: 'Source Discovery',
  Collector: 'Collector',
  DataEnricher: 'Data Enricher',
  FeatureAnalyzer: 'Feature Analyzer',
  SentimentAnalyzer: 'Sentiment Analyzer',
  PricingAnalyst: 'Pricing Analyst',
  TechStackAnalyzer: 'TechStack Analyzer',
  MarketPosition: 'Market Position',
  CrossReview: 'Cross-Review',
  SWOTSynthesizer: 'SWOT Synthesizer',
  Writer: 'Writer',
  QAFactCheck: 'QA #1 Fact Check',
  QALogicCheck: 'QA #2 Logic Check',
};

/* ---- progress bar helper ---- */

function ProgressBar({ pct }: { pct?: number }) {
  if (pct === undefined || pct < 0) return null;
  return (
    <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden mt-1">
      <div
        className="h-full bg-amber-500 rounded-full transition-all duration-700 animate-pulse"
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
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 hover:border-gray-700 transition-colors">
      {/* header */}
      <div className="flex items-center gap-2 mb-1">
        <StatusDot state={agent.state} />
        <span className="text-xs text-gray-500 font-mono uppercase">{stateLabel[agent.state]}</span>
        {agent.duration && (
          <span className="text-xs text-gray-600 font-mono ml-auto">{agent.duration}</span>
        )}
      </div>

      <div className="text-sm font-medium text-gray-200">{name}</div>

      {/* progress bar */}
      {agent.state === 'running' && <ProgressBar pct={agent.progress} />}

      {/* details */}
      {variant === 'detailed' && agent.outputSummary && (
        <div className="mt-1 text-xs text-gray-500 font-mono">{agent.outputSummary}</div>
      )}
      {variant === 'detailed' && agent.details && (
        <div className="text-xs text-gray-600 font-mono mt-0.5">{agent.details}</div>
      )}

      {/* compact output */}
      {variant === 'compact' && agent.outputSummary && (
        <div className="text-xs text-gray-500 font-mono mt-1 truncate">{agent.outputSummary}</div>
      )}

      {/* cost */}
      {agent.cost !== undefined && (
        <div className="text-xs text-gray-600 font-mono mt-1">${agent.cost.toFixed(4)}</div>
      )}
    </div>
  );
}

export { AGENT_NAMES };
