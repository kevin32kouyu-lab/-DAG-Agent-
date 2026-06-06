// 这个组件统一展示任务和 DAG 节点状态。

import type { NodeState } from '../types';

interface StatusBadgeProps {
  status: NodeState | string;
  label?: string;
  pulse?: boolean;
}

const STATUS_CONFIG: Record<string, { label: string; classes: string }> = {
  completed: { label: '✓ 完成', classes: 'text-green-700 bg-green-50 border-green-200' },
  running:   { label: '◐ 运行中', classes: 'text-amber-700 bg-amber-50 border-amber-200' },
  failed:    { label: '✕ 失败', classes: 'text-red-700 bg-red-50 border-red-200' },
  pending:   { label: '○ 等待', classes: 'text-slate-500 bg-slate-50 border-slate-200' },
  ready:     { label: '◉ 就绪', classes: 'text-blue-700 bg-blue-50 border-blue-200' },
  degraded:  { label: '⚠ 降级', classes: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
  planning:  { label: '◌ 规划中', classes: 'text-teal-700 bg-teal-50 border-teal-200' },
};

export default function StatusBadge({ status, label, pulse }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, classes: 'text-slate-500 bg-slate-50 border-slate-200' };
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs ${config.classes}`}>
      {pulse && status === 'running' && (
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
      )}
      {label ?? config.label}
    </span>
  );
}

export function StatusDot({ state }: { state: NodeState | string }) {
  const colors: Record<string, string> = {
    completed: 'bg-green-500',
    running: 'bg-amber-500 animate-pulse',
    failed: 'bg-red-500',
    pending: 'bg-gray-600',
    ready: 'bg-blue-500',
    degraded: 'bg-yellow-600',
    planning: 'bg-teal-500 animate-pulse',
  };
  return <span className={`w-2 h-2 rounded-full ${colors[state] || 'bg-gray-600'}`} />;
}
