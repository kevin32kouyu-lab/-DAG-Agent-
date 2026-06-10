// 这个文件集中管理图表配色，保证报告页和导出 PDF 的颜色一致。

export const COLORS = {
  // Product series — consulting-style, distinct, print-safe
  product: ['#1d4ed8', '#0f766e', '#7c3aed', '#c2410c', '#be123c', '#4b5563'],

  // Semantic
  positive: '#15803d',
  negative: '#b91c1c',
  neutral: '#64748b',

  // Maturity ordinal colors
  maturity: {
    experimental: '#d97706',
    beta: '#2563eb',
    ga: '#15803d',
    deprecated: '#b91c1c',
    unknown: '#64748b',
  } as Record<string, string>,

  // Differentiation ordinal colors
  differentiation: {
    disadvantage: '#dc2626',
    parity: '#94a3b8',
    advantage: '#059669',
    unique: '#7c3aed',
    unknown: '#cbd5e1',
  } as Record<string, string>,

  // Differentiation labels (Chinese)
  differentiationLabel: {
    disadvantage: '落后',
    parity: '持平',
    advantage: '领先',
    unique: '独家',
    unknown: '—',
  } as Record<string, string>,

  // Category Chinese labels
  categoryLabel: {
    'AI': 'AI 能力',
    'Collaboration': '协作',
    'API': '开放 API',
    'Analytics': '数据分析',
    'Integration': '集成',
    'Mobile': '移动端',
    'Security': '安全合规',
    'UI': '界面体验',
    'Other': '其他',
  } as Record<string, string>,

  // Chart chrome
  grid: '#e2e8f0',
  axis: '#64748b',
  text: '#334155',
  background: '#ffffff',
  tooltipBg: '#ffffff',
  tooltipBorder: '#cbd5e1',
} as const;

export const CHART_DEFAULTS = {
  isAnimationActive: false,
};

/** Shared tooltip style for all Recharts charts */
export const tooltipStyle = {
  contentStyle: {
    background: COLORS.tooltipBg,
    border: `1px solid ${COLORS.tooltipBorder}`,
    borderRadius: '8px',
    fontSize: '13px',
    fontFamily: 'system-ui, sans-serif',
    color: '#0f172a',
    padding: '8px 12px',
  },
  labelStyle: { color: '#475569', marginBottom: '4px' },
};

/** Shared legend wrapper style */
export const legendStyle = {
  wrapperStyle: {
    fontFamily: 'system-ui, sans-serif',
    fontSize: '12px',
    color: '#475569',
    paddingTop: '12px',
  },
};
