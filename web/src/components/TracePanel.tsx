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
        className="text-xs font-medium text-teal-700 hover:text-teal-900"
      >
        [查看完整 {label}]
      </button>
      {open && (
        <pre className="mt-1 max-h-64 overflow-auto rounded border border-slate-200 bg-slate-50 p-2 font-mono text-xs text-slate-600 whitespace-pre-wrap">
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
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-xs text-slate-500">Agent 决策轨迹不可用（审计日志未启用）</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      {/* header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h4 className="text-sm font-medium text-slate-900">Agent 决策轨迹: {agentType || 'Unknown'}</h4>
          <p className="mt-0.5 text-xs text-slate-500">
            节点: <span className="font-mono">{nodeId}</span> · 总步数: <span className="font-mono">{stepTraces.length}</span> 步
          </p>
        </div>
        {duration && <span className="font-mono text-xs text-slate-500">{duration}</span>}
      </div>

      {/* steps */}
      <div className="p-4 space-y-0">
        {stepTraces.map((st, i) => (
          <div key={i} className={`border-l-2 ${PHASE_COLORS[st.phase] || 'border-l-gray-700'} pl-4 py-1`}>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-slate-500">Step {st.step}</span>
              <span className="text-xs text-slate-500">── {PHASE_LABELS[st.phase] || st.phase} ──</span>
            </div>

            {/* Observe data */}
            {st.phase === 'Observe' && st.observation_summary && (
              <p className="mt-0.5 text-xs text-slate-600">{st.observation_summary}</p>
            )}

            {/* Think reasoning */}
            {st.phase === 'Think' && (
              <div className="mt-1 space-y-1">
                {st.reasoning && (
                  <p className="text-xs leading-relaxed text-slate-600 line-clamp-3">
                    {st.reasoning}
                  </p>
                )}
                {st.confidence !== undefined && (
                  <span className="font-mono text-xs text-slate-500">
                    置信度: {(st.confidence * 100).toFixed(0)}%
                  </span>
                )}
                {st.prompt_snapshot && <CollapsibleText text={st.prompt_snapshot} label="Prompt" />}
                {st.response_snapshot && <CollapsibleText text={st.response_snapshot} label="Response" />}
              </div>
            )}

            {/* Act details */}
            {st.phase === 'Act' && (
              <div className="mt-0.5 space-y-0.5 text-xs text-slate-600">
                {st.action && <span>工具: <span className="font-mono">{st.action}</span></span>}
                {st.action_params && <div>参数: <span className="font-mono">{JSON.stringify(st.action_params)}</span></div>}
                {st.action_result_summary && <div>结果: {st.action_result_summary}</div>}
              </div>
            )}

            {/* Finalize output */}
            {st.phase === 'Finalize' && (
              <div className="mt-0.5 space-y-0.5 text-xs text-slate-600">
                {st.nodes_created && st.nodes_created.length > 0 && (
                  <div>创建节点: <span className="font-mono">{st.nodes_created.length}</span> 个</div>
                )}
                {st.edges_created && st.edges_created.length > 0 && (
                  <div>创建边: <span className="font-mono">{st.edges_created.length}</span> 条</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* footer */}
      <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-2 text-xs">
        <span className="text-slate-500">总成本:</span>
        <span className="font-mono text-slate-600">
          Token {totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens}
          {' '}| ${totalCost.toFixed(2)}
          {duration && ` | ${duration}`}
        </span>
      </div>
    </div>
  );
}
