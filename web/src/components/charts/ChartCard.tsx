import type { ReactNode } from 'react';
import EmptyState from '../EmptyState';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  icon?: string;
  children: ReactNode;
  isEmpty?: boolean;
  emptyMessage?: string;
}

export default function ChartCard({
  title, subtitle, icon, children, isEmpty, emptyMessage,
}: ChartCardProps) {
  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-2xl overflow-hidden animate-slideUp">
      <div className="flex items-center gap-2 px-5 pt-4 pb-2">
        {icon && <span className="text-base">{icon}</span>}
        <h3 className="text-sm font-semibold text-gray-200">{title}</h3>
        {subtitle && (
          <span className="text-xs text-gray-600 font-mono">{subtitle}</span>
        )}
      </div>
      <div className="px-2 pb-3">
        {isEmpty ? (
          <div className="py-8">
            <EmptyState icon="📊" title={emptyMessage || '暂无数据'} />
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
