import { useState } from 'react';
import type { StepTrace } from '../types';

interface TracePanelProps {
  nodeId: string;
  agentType?: string;
  stepTraces: StepTrace[];
  duration?: string;
  cost?: number;
}

const PHASE_LABELS: Record<string, string> = {
  Observe: 'Observe',
  Think: 'Think',
  Act: 'Act',
  Finalize: 'Finalize',
};

const PHASE_COLORS: Record<string, string> = {
  Observe: 'border-l-gray-600',
  Think: 'border-l-blue-500',
  Act: 'border-l-amber-500',
  Finalize: 'border-l-green-500',
};

function CollapsibleText({ text, label }: { text: string; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="text-xs text-cyan-400 hover:text-cyan-300 font-mono"
      >
        [查看完整 {label}]
      </button>
      {open && (
        <pre className="mt-1 p-2 bg-gray-950 rounded border border-gray-800 text-xs text-gray-400 font-mono whitespace-pre-wrap max-h-64 overflow-auto">
          {text}
        </pre>
      )}
    </div>
  );
}

export default function TracePanel({ nodeId, agentType, stepTraces, duration, cost }: TracePanelProps) {
  const totalTokens = stepTraces.reduce((s, st) => s + (st.tokens || 0), 0);
  const totalCost = cost ?? stepTraces.reduce((s, st) => s + (st.cost || 0), 0);

  if (!stepTraces || stepTraces.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <p className="text-gray-600 font-mono text-xs">Agent 决策轨迹不可用（审计日志未启用）</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* header */}
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-300">Agent 决策轨迹: {agentType || 'Unknown'}</h4>
          <p className="text-xs text-gray-600 font-mono mt-0.5">节点: {nodeId} · 总步数: {stepTraces.length} 步</p>
        </div>
        {duration && <span className="text-xs text-gray-500 font-mono">{duration}</span>}
      </div>

      {/* steps */}
      <div className="p-4 space-y-0">
        {stepTraces.map((st, i) => (
          <div key={i} className={`border-l-2 ${PHASE_COLORS[st.phase] || 'border-l-gray-700'} pl-4 py-1`}>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 font-mono">Step {st.step}</span>
              <span className="text-xs text-gray-400 font-mono">── {PHASE_LABELS[st.phase] || st.phase} ──</span>
            </div>

            {/* Observe data */}
            {st.phase === 'Observe' && st.observation_summary && (
              <p className="text-xs text-gray-500 mt-0.5">{st.observation_summary}</p>
            )}

            {/* Think reasoning */}
            {st.phase === 'Think' && (
              <div className="mt-1 space-y-1">
                {st.reasoning && (
                  <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">
                    {st.reasoning}
                  </p>
                )}
                {st.confidence !== undefined && (
                  <span className="text-xs text-gray-600 font-mono">
                    置信度: {(st.confidence * 100).toFixed(0)}%
                  </span>
                )}
                {st.prompt_snapshot && <CollapsibleText text={st.prompt_snapshot} label="Prompt" />}
                {st.response_snapshot && <CollapsibleText text={st.response_snapshot} label="Response" />}
              </div>
            )}

            {/* Act details */}
            {st.phase === 'Act' && (
              <div className="mt-0.5 text-xs text-gray-500 font-mono space-y-0.5">
                {st.action && <span>工具: {st.action}</span>}
                {st.action_params && <div>参数: {JSON.stringify(st.action_params)}</div>}
                {st.action_result_summary && <div>结果: {st.action_result_summary}</div>}
              </div>
            )}

            {/* Finalize output */}
            {st.phase === 'Finalize' && (
              <div className="mt-0.5 text-xs text-gray-500 font-mono space-y-0.5">
                {st.nodes_created && st.nodes_created.length > 0 && (
                  <div>创建节点: {st.nodes_created.length} 个</div>
                )}
                {st.edges_created && st.edges_created.length > 0 && (
                  <div>创建边: {st.edges_created.length} 条</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* footer */}
      <div className="px-4 py-2 border-t border-gray-800 flex items-center justify-between font-mono text-xs">
        <span className="text-gray-600">总成本:</span>
        <span className="text-gray-500">
          Token {totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens}
          {' '}| ${totalCost.toFixed(2)}
          {duration && ` | ${duration}`}
        </span>
      </div>
    </div>
  );
}
