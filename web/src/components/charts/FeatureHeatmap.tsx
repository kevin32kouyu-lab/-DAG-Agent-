import { COLORS } from './chartTheme';
import type { FeatureAnalytics } from '../../types';

interface FeatureHeatmapProps {
  data: FeatureAnalytics;
  mode: 'maturity' | 'differentiation';
}

export default function FeatureHeatmap({ data, mode }: FeatureHeatmapProps) {
  const { products, features } = data;
  if (products.length === 0 || features.length === 0) return null;

  const colorMap = mode === 'maturity' ? COLORS.maturity : COLORS.differentiation;

  // group features by category
  const grouped = new Map<string, typeof features>();
  for (const f of features) {
    const cat = f.category || 'Other';
    if (!grouped.has(cat)) grouped.set(cat, []);
    grouped.get(cat)!.push(f);
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="hm-header text-left">Feature</th>
            {products.map(p => (
              <th key={p} className="hm-header text-center">{p}</th>
            ))}
          </tr>
        </thead>
        {[...grouped.entries()].map(([cat, catFeatures]) => (
          <tbody key={cat}>
            <tr>
              <td colSpan={products.length + 1} className="pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                {cat}
              </td>
            </tr>
            {catFeatures.map(f => (
              <tr key={f.feature_name} className="border-b border-gray-800/30">
                <td className="hm-header text-left font-normal text-gray-400">{f.feature_name}</td>
                {products.map(p => {
                  const key = `${p}_${mode}`;
                  const val = (f[key] || 'unknown').toLowerCase();
                  const bg = colorMap[val] || colorMap.unknown;
                  return (
                    <td key={p} className="text-center py-1">
                      <span
                        className="inline-block px-2 py-0.5 rounded text-[11px] font-medium"
                        style={{ background: bg, color: bg === '#fbbf24' ? '#1e293b' : '#fff' }}
                      >
                        {val}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
