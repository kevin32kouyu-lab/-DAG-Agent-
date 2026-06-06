import {
  BarChart as RechartsBar, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { COLORS, CHART_DEFAULTS, tooltipStyle, legendStyle } from './chartTheme';

interface BarChartProps {
  data: Record<string, unknown>[];
  dataKeys: string[];
  xAxisKey: string;
  products: string[];
  layout?: 'vertical' | 'horizontal';
  height?: number;
}

export default function BarChart({
  data, dataKeys, xAxisKey, layout, height,
}: BarChartProps) {
  if (!data || data.length === 0) return null;

  const isVertical = layout === 'vertical';

  return (
    <ResponsiveContainer width="100%" height={height || 320}>
      <RechartsBar data={data} layout={layout} {...CHART_DEFAULTS}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
        {isVertical ? (
          <>
            <XAxis type="number" tick={{ fill: COLORS.axis, fontSize: 11 }} />
            <YAxis type="category" dataKey={xAxisKey} tick={{ fill: COLORS.text, fontSize: 11 }} width={120} />
          </>
        ) : (
          <>
            <XAxis dataKey={xAxisKey} tick={{ fill: COLORS.text, fontSize: 11 }} />
            <YAxis tick={{ fill: COLORS.axis, fontSize: 11 }} />
          </>
        )}
        <Tooltip {...tooltipStyle} />
        {dataKeys.map((key, i) => (
          <Bar
            key={key}
            dataKey={key}
            fill={COLORS.product[i % COLORS.product.length]}
            radius={[4, 4, 0, 0]}
          />
        ))}
        {dataKeys.length > 1 && <Legend {...legendStyle} />}
      </RechartsBar>
    </ResponsiveContainer>
  );
}
