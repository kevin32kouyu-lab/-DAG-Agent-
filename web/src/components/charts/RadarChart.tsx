import {
  Radar, RadarChart as RechartsRadar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip, Legend,
} from 'recharts';
import { COLORS, CHART_DEFAULTS, tooltipStyle, legendStyle } from './chartTheme';
import type { ScoringDatum } from '../../types';

interface RadarChartProps {
  data: ScoringDatum[];
  products: string[];
}

export default function RadarChart({ data, products }: RadarChartProps) {
  // pivot: ScoringDatum[] → { dimension: string, ProductA: number, ProductB: number, ... }
  const dimSet = new Map<string, Record<string, number | string>>();
  for (const d of data) {
    if (!dimSet.has(d.dimension)) {
      dimSet.set(d.dimension, { dimension: d.dimension });
    }
    dimSet.get(d.dimension)![d.product] = d.score;
  }
  const chartData = [...dimSet.values()];

  if (chartData.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={360}>
      <RechartsRadar data={chartData} {...CHART_DEFAULTS}>
        <PolarGrid stroke={COLORS.grid} />
        <PolarAngleAxis dataKey="dimension" tick={{ fill: COLORS.text, fontSize: 12 }} />
        <PolarRadiusAxis angle={30} tick={{ fill: COLORS.axis, fontSize: 10 }} />
        <Tooltip {...tooltipStyle} />
        {products.map((p, i) => (
          <Radar
            key={p}
            name={p}
            dataKey={p}
            stroke={COLORS.product[i % COLORS.product.length]}
            fill={COLORS.product[i % COLORS.product.length]}
            fillOpacity={0.15}
            strokeWidth={2}
          />
        ))}
        {products.length > 1 && <Legend {...legendStyle} />}
      </RechartsRadar>
    </ResponsiveContainer>
  );
}
