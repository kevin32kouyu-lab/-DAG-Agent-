// 这个组件提供报告页图表容器，让所有图表保持一致的浅色咨询风格。

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
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white animate-slideUp">
      <div className="flex items-center gap-2 px-5 pt-4 pb-2">
        {icon && <span className="text-base">{icon}</span>}
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
        {subtitle && (
          <span className="text-xs text-slate-500">{subtitle}</span>
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
