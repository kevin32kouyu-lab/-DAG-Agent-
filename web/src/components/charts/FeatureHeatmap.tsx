// 差异化对比矩阵 v2 — 横向转置布局，产品做行、能力做列
// 3 行 × N 列，横向滚动，解决纵向太长的问题

import { COLORS } from './chartTheme';
import type { FeatureAnalytics } from '../../types';

interface FeatureHeatmapProps {
  data: FeatureAnalytics;
  mode: 'maturity' | 'differentiation';
}

const DIFF_LABELS: Record<string, string> = COLORS.differentiationLabel;
const DIFF_COLORS: Record<string, string> = COLORS.differentiation;
const CAT_LABELS: Record<string, string> = COLORS.categoryLabel;

export default function FeatureHeatmap({ data, mode }: FeatureHeatmapProps) {
  const { products, features } = data;
  if (products.length === 0 || features.length === 0) return null;

  const isDiff = mode === 'differentiation';
  const colorMap = isDiff ? DIFF_COLORS : COLORS.maturity;

  // Group by category
  const grouped = new Map<string, typeof features>();
  for (const f of features) {
    const cat = f.category || 'Other';
    if (!grouped.has(cat)) grouped.set(cat, []);
    grouped.get(cat)!.push(f);
  }

  const catOrder = ['AI', 'Collaboration', 'API', 'Integration', 'Analytics', 'Security', 'Mobile', 'UI'];
  const sortedCats = [...grouped.keys()].sort((a, b) => {
    const ai = catOrder.indexOf(a), bi = catOrder.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  // 收集所有 feature 信息（按分组顺序），每个 feature 有 name/category/每个产品的值
  const allFeatures: { name: string; category: string; values: Record<string, string> }[] = [];
  for (const cat of sortedCats) {
    for (const f of grouped.get(cat)!) {
      const values: Record<string, string> = {};
      for (const p of products) {
        const key = `${p}_${mode}`;
        const raw = (f[key] || '').toLowerCase();
        values[p] = raw || (isDiff ? 'parity' : 'unknown');
      }
      allFeatures.push({ name: f.feature_name, category: cat, values });
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse" style={{ minWidth: products.length * 80 + 160 }}>
        <thead>
          {/* Category spacer row */}
          <tr>
            <th className="sticky left-0 bg-white z-10" style={{ width: 140, minWidth: 140 }} />
            {sortedCats.map(cat => {
              const count = grouped.get(cat)!.length;
              return (
                <th key={cat} colSpan={count} className="text-left align-bottom pb-1 px-2" style={{ borderBottom: '2px solid #e2e8f0' }}>
                  <span className="text-[10px] font-semibold text-slate-400 tracking-wider uppercase">
                    {CAT_LABELS[cat] || cat}
                  </span>
                </th>
              );
            })}
          </tr>
          {/* Feature name row */}
          <tr>
            <th className="sticky left-0 bg-white z-10 text-left py-2 pr-3" style={{ borderBottom: '2px solid #cbd5e1', color: '#475569', fontWeight: 600, fontSize: '11px' }}>
              {isDiff ? '能力维度' : 'Feature'}
            </th>
            {allFeatures.map(f => (
              <th key={f.name} className="text-center px-1 py-2" style={{ borderBottom: '2px solid #cbd5e1', color: '#64748b', fontWeight: 500, fontSize: '10px', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={f.name}
              >
                {f.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {products.map((p, pi) => (
            <tr key={p} className={pi < products.length - 1 ? 'border-b border-slate-100' : ''}>
              <td className="sticky left-0 bg-white z-10 py-2 pr-3 font-semibold text-slate-700 text-[11px]" style={{ borderRight: pi < products.length - 1 ? 'none' : 'none' }}>
                {p}
              </td>
              {allFeatures.map(f => {
                const raw = f.values[p];
                const bg = colorMap[raw] || colorMap.unknown;
                const label = isDiff ? (DIFF_LABELS[raw] || raw) : raw;
                const needsWhiteText = ['#dc2626', '#059669', '#7c3aed'].includes(bg);
                return (
                  <td key={f.name} className="text-center py-1.5 px-0.5">
                    <span
                      className="inline-block min-w-[32px] px-1.5 py-0.5 rounded text-[9px] font-semibold"
                      style={{ background: bg, color: needsWhiteText ? '#fff' : '#334155' }}
                      title={`${p} · ${f.name}: ${label}`}
                    >
                      {label}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {/* Legend */}
      {isDiff && (
        <div className="flex items-center gap-3 mt-3 pt-2 border-t border-slate-100">
          <span className="text-[10px] text-slate-400">图例:</span>
          {(['unique', 'advantage', 'parity', 'disadvantage'] as const).map(k => (
            <span key={k} className="flex items-center gap-1 text-[10px] text-slate-500">
              <span className="inline-block w-3 h-3 rounded" style={{ background: DIFF_COLORS[k] }} />
              {DIFF_LABELS[k]}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
