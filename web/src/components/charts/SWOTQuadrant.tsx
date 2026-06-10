// SWOT 条目展示 — 替代纯计数卡片，展示实际 S/W/O/T 内容
// 每个象限最多展示 3 条，按产品分列

import { useState } from 'react';
import type { SWOTDatum } from '../../types';

interface SWOTQuadrantProps {
  data: SWOTDatum[];
  products: string[];
}

const QUADRANTS = [
  { key: 'strengths' as const, countKey: 'strengths_count' as const, label: '优势', color: '#15803d', bg: '#f0fdf4', icon: '✅' },
  { key: 'weaknesses' as const, countKey: 'weaknesses_count' as const, label: '劣势', color: '#b91c1c', bg: '#fef2f2', icon: '⚠️' },
  { key: 'opportunities' as const, countKey: 'opportunities_count' as const, label: '机会', color: '#1d4ed8', bg: '#eff6ff', icon: '🚀' },
  { key: 'threats' as const, countKey: 'threats_count' as const, label: '威胁', color: '#c2410c', bg: '#fff7ed', icon: '🔴' },
];

export default function SWOTQuadrant({ data, products }: SWOTQuadrantProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (!data || data.length === 0) return null;

  const toggle = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  // 收集所有产品在某象限下的条目
  const collectItems = (quadKey: string): { product: string; text: string }[] => {
    const items: { product: string; text: string }[] = [];
    for (const d of data) {
      const arr = (d as Record<string, unknown>)[quadKey] as string[] || [];
      for (const item of arr) items.push({ product: d.product, text: item });
    }
    return items;
  };

  return (
    <div className="space-y-2">
      {QUADRANTS.map(q => {
        const items = collectItems(q.key);
        const totalCount = data.reduce((sum, d) => sum + d[q.countKey], 0);
        const isExpanded = expanded.has(q.key);

        return (
          <div key={q.key} className="rounded-lg border border-slate-200 overflow-hidden" style={{ background: q.bg }}>
            {/* Header — click to expand */}
            <button
              onClick={() => toggle(q.key)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:opacity-80 transition-opacity"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm">{q.icon}</span>
                <span className="text-xs font-semibold" style={{ color: q.color }}>{q.label}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-500">{totalCount} 条</span>
                <span className="text-[10px] text-slate-400">{isExpanded ? '▲' : '▼'}</span>
              </div>
            </button>

            {/* Items — show when expanded */}
            {isExpanded && items.length > 0 && (
              <div className="px-4 pb-3 space-y-1.5">
                {items.slice(0, 8).map((item, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px] leading-relaxed">
                    <span className="mt-0.5 flex-shrink-0 font-mono text-[10px] rounded bg-white/60 px-1 py-0.5 text-slate-500">
                      {item.product}
                    </span>
                    <span className="text-slate-700">{item.text}</span>
                  </div>
                ))}
                {items.length > 8 && (
                  <p className="text-[10px] text-slate-400 pl-2">...还有 {items.length - 8} 条</p>
                )}
              </div>
            )}

            {/* Per-product count breakdown (always visible) */}
            {products.length > 1 && (
              <div className="flex items-center gap-3 px-4 pb-2">
                {data.map(d => (
                  <span key={d.product} className="text-[10px] text-slate-500">
                    {d.product}: <span className="font-mono text-slate-700">{d[q.countKey]}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
