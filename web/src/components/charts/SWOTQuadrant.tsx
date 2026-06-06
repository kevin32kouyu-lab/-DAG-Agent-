// 这个组件汇总 SWOT 四象限数量，帮助快速判断报告结论分布。

import type { SWOTDatum } from '../../types';

interface SWOTQuadrantProps {
  data: SWOTDatum[];
  products: string[];
}

const quadrants = [
  { key: 'strengths_count' as const, label: '优势 Strengths', color: '#15803d', bg: '#f0fdf4' },
  { key: 'weaknesses_count' as const, label: '劣势 Weaknesses', color: '#b91c1c', bg: '#fef2f2' },
  { key: 'opportunities_count' as const, label: '机会 Opportunities', color: '#1d4ed8', bg: '#eff6ff' },
  { key: 'threats_count' as const, label: '威胁 Threats', color: '#c2410c', bg: '#fff7ed' },
];

export default function SWOTQuadrant({ data, products }: SWOTQuadrantProps) {
  if (!data || data.length === 0) return null;

  // aggregate across products per quadrant
  const totals = { strengths_count: 0, weaknesses_count: 0, opportunities_count: 0, threats_count: 0 };
  for (const d of data) {
    totals.strengths_count += d.strengths_count;
    totals.weaknesses_count += d.weaknesses_count;
    totals.opportunities_count += d.opportunities_count;
    totals.threats_count += d.threats_count;
  }
  const maxCount = Math.max(...Object.values(totals), 1);

  return (
    <div className="grid grid-cols-2 gap-3">
      {quadrants.map(q => {
        const count = totals[q.key];
        const pct = Math.round((count / maxCount) * 100);
        return (
          <div
            key={q.key}
            className="rounded-lg border border-slate-200 p-4"
            style={{ background: q.bg }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold" style={{ color: q.color }}>
                {q.label}
              </span>
              <span className="text-lg font-bold" style={{ color: q.color }}>
                {count}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/70">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: q.color }}
              />
            </div>
            {/* per-product breakdown */}
            {products.length > 1 && data.length > 0 && (
              <div className="mt-2 space-y-1">
                {data.map(d => (
                  <div key={d.product} className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">{d.product}</span>
                    <span className="font-mono text-slate-700">{d[q.key]}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
