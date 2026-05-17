import type { SWOTDatum } from '../../types';

interface SWOTQuadrantProps {
  data: SWOTDatum[];
  products: string[];
}

const quadrants = [
  { key: 'strengths_count' as const, label: '优势 Strengths', color: '#22c55e', bg: 'rgba(34,197,94,0.08)' },
  { key: 'weaknesses_count' as const, label: '劣势 Weaknesses', color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
  { key: 'opportunities_count' as const, label: '机会 Opportunities', color: '#3b82f6', bg: 'rgba(59,130,246,0.08)' },
  { key: 'threats_count' as const, label: '威胁 Threats', color: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
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
            className="rounded-xl p-4 border border-gray-800/40"
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
            <div className="h-2 bg-gray-800/40 rounded-full overflow-hidden">
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
                    <span className="text-gray-500">{d.product}</span>
                    <span className="text-gray-300 font-mono">{d[q.key]}</span>
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
