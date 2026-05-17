// Shared chart theme — hex values only (no CSS variables) for html2pdf compatibility

export const COLORS = {
  // Product series — distinct, print-safe
  product: ['#22d3ee', '#a78bfa', '#f472b6', '#fbbf24', '#34d399', '#fb923c'],

  // Semantic
  positive: '#22c55e',
  negative: '#ef4444',
  neutral: '#94a3b8',

  // Maturity ordinal colors
  maturity: {
    experimental: '#fbbf24',
    beta: '#60a5fa',
    ga: '#22c55e',
    deprecated: '#ef4444',
    unknown: '#64748b',
  } as Record<string, string>,

  // Differentiation ordinal colors
  differentiation: {
    disadvantage: '#ef4444',
    parity: '#94a3b8',
    advantage: '#22d3ee',
    unique: '#a78bfa',
    unknown: '#64748b',
  } as Record<string, string>,

  // Chart chrome
  grid: '#1e293b',
  axis: '#64748b',
  text: '#94a3b8',
  background: '#0f172a',
  tooltipBg: '#1e293b',
  tooltipBorder: '#334155',
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
    fontFamily: "'JetBrains Mono', monospace",
    color: '#e2e8f0',
    padding: '8px 12px',
  },
  labelStyle: { color: '#94a3b8', marginBottom: '4px' },
};

/** Shared legend wrapper style */
export const legendStyle = {
  wrapperStyle: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '12px',
    color: '#94a3b8',
    paddingTop: '12px',
  },
};
