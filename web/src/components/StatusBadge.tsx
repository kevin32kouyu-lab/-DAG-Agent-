import type { NodeState } from '../types';

interface StatusBadgeProps {
  status: NodeState | string;
  label?: string;
  pulse?: boolean;
}

const STATUS_CONFIG: Record<string, { label: string; classes: string }> = {
  completed: { label: '✓ 完成', classes: 'text-green-400 bg-green-400/10 border-green-400/30' },
  running:   { label: '◐ 运行中', classes: 'text-amber-400 bg-amber-400/10 border-amber-400/30' },
  failed:    { label: '✕ 失败', classes: 'text-red-400 bg-red-400/10 border-red-400/30' },
  pending:   { label: '○ 等待', classes: 'text-gray-500 bg-gray-500/10 border-gray-500/30' },
  ready:     { label: '◉ 就绪', classes: 'text-blue-400 bg-blue-400/10 border-blue-400/30' },
  degraded:  { label: '⚠ 降级', classes: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30' },
};

export default function StatusBadge({ status, label, pulse }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, classes: 'text-gray-500 bg-gray-500/10 border-gray-500/30' };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-mono ${config.classes}`}>
      {pulse && status === 'running' && (
        <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
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
  };
  return <span className={`w-2 h-2 rounded-full ${colors[state] || 'bg-gray-600'}`} />;
}
