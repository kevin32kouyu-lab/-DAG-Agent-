interface ConfidenceBarProps {
  value: number;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export default function ConfidenceBar({ value, showLabel = true, size = 'md' }: ConfidenceBarProps) {
  const pct = Math.min(100, Math.max(0, Math.round(value * 100)));
  const colorClass = pct >= 80 ? 'bg-green-600' : pct >= 60 ? 'bg-amber-500' : 'bg-red-600';
  const textColor = pct >= 80 ? 'text-green-700' : pct >= 60 ? 'text-amber-700' : 'text-red-700';
  const height = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-3' : 'h-2';

  const labelSizes: Record<string, string> = {
    sm: 'text-xs', md: 'text-sm', lg: 'text-lg font-bold',
  };

  return (
    <div className="flex items-center gap-2">
      <div className={`flex-1 rounded-full bg-slate-200 ${height} overflow-hidden`}>
        <div
          className={`${height} rounded-full ${colorClass} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className={`${labelSizes[size]} ${textColor} font-mono tabular-nums w-10 text-right`}>
          {pct}%
        </span>
      )}
    </div>
  );
}
