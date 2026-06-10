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
  useLogScale?: boolean;
}

export default function BarChart({
  data, dataKeys, xAxisKey, layout, height, useLogScale,
}: BarChartProps) {
  if (!data || data.length === 0) return null;

  const isVertical = layout === 'vertical';

  // 对数刻度格式化
  const logTickFormatter = (value: number) => {
    if (value >= 100000) return `${(value / 1000).toFixed(0)}K`;
    if (value >= 10000) return `${(value / 1000).toFixed(1)}K`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return String(value);
  };

  // 如果启用 log scale，转换数据
  const chartData = useLogScale
    ? data.map(row => {
        const newRow: Record<string, unknown> = { ...row };
        for (const key of dataKeys) {
          const val = Number(row[key]);
          if (val > 0) newRow[key] = Math.log10(val);
          else newRow[key] = 0;
        }
        return newRow;
      })
    : data;

  return (
    <ResponsiveContainer width="100%" height={height || 320}>
      <RechartsBar data={chartData} layout={layout} {...CHART_DEFAULTS}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
        {isVertical ? (
          <>
            <XAxis type="number" tick={{ fill: COLORS.axis, fontSize: 11 }} />
            <YAxis type="category" dataKey={xAxisKey} tick={{ fill: COLORS.text, fontSize: 11 }} width={120} />
          </>
        ) : (
          <>
            <XAxis dataKey={xAxisKey} tick={{ fill: COLORS.text, fontSize: 11 }} />
            <YAxis
              tick={{ fill: COLORS.axis, fontSize: 11 }}
              tickFormatter={useLogScale ? logTickFormatter : undefined}
              label={useLogScale ? { value: 'log10(price)', position: 'insideLeft', style: { fontSize: 10, fill: COLORS.axis } } : undefined}
            />
          </>
        )}
        <Tooltip
          {...tooltipStyle}
          formatter={useLogScale ? (value: number) => [`10^${Number(value).toFixed(1)} = ${Math.round(10 ** Number(value)).toLocaleString()}`, ''] : undefined}
        />
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
