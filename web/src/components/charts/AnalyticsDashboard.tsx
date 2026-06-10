// 报告仪表盘 v2 — 精简为 3 张核心图 + 2 个信息卡片
// 删除: 雷达图 (评分无区分度) / 价值分横柱 (无解释性) / TechStack (Demo 无价值)

import { useState, useEffect } from 'react';
import LoadingSkeleton from '../LoadingSkeleton';
import EmptyState from '../EmptyState';
import ChartCard from './ChartCard';
import BarChart from './BarChart';
import FeatureHeatmap from './FeatureHeatmap';
import SWOTQuadrant from './SWOTQuadrant';
import type { AnalyticsResponse } from '../../types';

export default function AnalyticsDashboard({ taskId }: { taskId: string }) {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    fetch(`/api/report/${taskId}/analytics`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(nextData => {
        if (ignore) return;
        setData(nextData);
        setError('');
      })
      .catch(e => {
        if (!ignore) setError(e.message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => { ignore = true; };
  }, [taskId]);

  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8">
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error) {
    return <EmptyState icon="⚠" title="图表加载失败" description={error} />;
  }

  if (!data) return null;

  const sourceLabel =
    data.data_source === 'report_fallback'
      ? '报告推断'
      : data.data_source === 'structured'
        ? '结构化数据'
        : '暂无数据';

  const hasAnyData =
    data.products.length > 0 &&
    (data.features.features.length > 0 ||
      data.sentiment.topics.length > 0 ||
      data.pricing.plans.length > 0 ||
      data.swot.length > 0);

  if (!hasAnyData) {
    return (
      <EmptyState
        icon="📊"
        title="暂无图表数据"
        description="分析任务尚未产生足够的结构化数据，请等待所有 Agent 完成分析"
      />
    );
  }

  // ── Sentiment bar data (with Chinese topic labels) ──
  const TOPIC_ZH: Record<string, string> = {
    pricing: '价格', usability: '易用性', performance: '性能',
    features: '功能', support: '支持', onboarding: '上手体验',
    overall: '综合', security: '安全', privacy: '隐私',
  };
  const sentimentKeys =
    data.sentiment.products.length > 0
      ? data.sentiment.products.map(p => `${p}_score`)
      : [];
  const sentimentData = data.sentiment.topics.map(t => {
    const row: Record<string, unknown> = { topic: TOPIC_ZH[t.topic] || t.topic };
    for (const k of sentimentKeys) row[k] = t[k] ?? 0;
    return row;
  });

  // ── Pricing table data ──
  // 按方案档位分组: Free / Starter / Pro / Business / Enterprise
  const TIER_ORDER = ['Free', 'Starter', 'Pro', 'Business', 'Enterprise'];
  const pricingByTier = new Map<string, Map<string, { price: number; currency: string; billing: string }>>();
  for (const plan of data.pricing.plans) {
    const tier = plan.plan_name;
    if (!pricingByTier.has(tier)) pricingByTier.set(tier, new Map());
    pricingByTier.get(tier)!.set(plan.product, {
      price: plan.price,
      currency: (plan as Record<string, unknown>).currency as string || 'USD',
      billing: plan.billing_cycle,
    });
  }
  const pricingTiers = TIER_ORDER.filter(t => pricingByTier.has(t));
  // 追加非标准档位
  for (const [tier] of pricingByTier) {
    if (!pricingTiers.includes(tier)) pricingTiers.push(tier);
  }

  // ── Data source summary ──
  const sourceParts: string[] = [];
  if (data.source_stats?.details) {
    for (const d of data.source_stats.details) {
      const label = NODE_TYPE_LABELS[d.type] || d.type;
      sourceParts.push(`${d.count} ${label}`);
    }
  }

  return (
    <div className="space-y-4 animate-fadeIn">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-950">分析仪表盘</span>
        <span className="text-xs text-slate-500">
          {data.products.length} 产品
        </span>
        <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] text-slate-500">
          {sourceLabel}
        </span>
      </div>

      {data.warnings && data.warnings.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {data.warnings[0]}
        </div>
      )}

      {/* ── Section 1: 核心发现 (Insight Cards) ── */}
      {data.insights && data.insights.length > 0 && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {data.insights.map(ins => (
            <div
              key={ins.product}
              className="rounded-lg border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-4"
            >
              <h4 className="text-sm font-semibold text-slate-900 mb-2">{ins.product}</h4>
              <ul className="space-y-1.5">
                {ins.items.slice(0, 3).map((item, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-slate-600 leading-relaxed">
                    <span className="mt-0.5 flex-shrink-0">{item.icon}</span>
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* ── Section 2: 用户情感 + 产品定位 ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="用户情感分析"
          subtitle="用户口碑 · Sentiment"
          icon="💬"
          isEmpty={data.sentiment.topics.length === 0}
          emptyMessage="该场景暂未采集到足够用户反馈数据，可重新运行 Sentiment Analyzer 采集开发者社区评论"
        >
          <BarChart
            data={sentimentData}
            dataKeys={sentimentKeys}
            xAxisKey="topic"
            products={data.sentiment.products}
            height={280}
          />
        </ChartCard>

        <ChartCard
          title="产品定位速览"
          subtitle="产品定位 · Positioning"
          icon="📍"
          isEmpty={!data.market_position || data.market_position.length === 0}
          emptyMessage="暂无定位数据"
        >
          <MarketPositionTable data={data.market_position || []} />
        </ChartCard>
      </div>

      {/* ── Section 3: 差异化能力对比（独立整行，横向滚动）── */}
      <ChartCard
        title="差异化能力对比"
        subtitle="差异化对比 · Differentiation"
        icon="⚡"
        isEmpty={data.features.features.length === 0}
        emptyMessage="暂无功能分析数据"
      >
        <FeatureHeatmap data={data.features} mode="differentiation" />
      </ChartCard>

      {/* ── Section 3: 定价对照表 + SWOT 条目 ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title="定价档位对照"
          subtitle="定价档位 · Pricing"
          icon="💰"
          isEmpty={data.pricing.plans.length === 0}
          emptyMessage="暂无定价数据"
        >
          <PricingTable tiers={pricingTiers} byTier={pricingByTier} products={data.products} />
        </ChartCard>

        <ChartCard
          title="SWOT 关键条目"
          subtitle="战略分析 · SWOT"
          icon="🎯"
          isEmpty={data.swot.length === 0}
          emptyMessage="暂无 SWOT 数据"
        >
          <SWOTQuadrant data={data.swot} products={data.products} />
        </ChartCard>
      </div>

      {/* ── Footer: 数据来源 ── */}
      {sourceParts.length > 0 && (
        <div className="rounded-lg border border-slate-100 bg-slate-50/50 px-4 py-3 text-xs text-slate-500 flex items-center gap-2">
          <span className="font-medium text-slate-600">📦 数据来源:</span>
          <span>{sourceParts.join(' · ')}</span>
          <span className="text-slate-400">({data.source_stats?.total_nodes} 节点)</span>
        </div>
      )}
    </div>
  );
}

// ── 定价对照表（替代柱状图）──
function PricingTable({
  tiers,
  byTier,
  products,
}: {
  tiers: string[];
  byTier: Map<string, Map<string, { price: number; currency: string; billing: string }>>;
  products: string[];
}) {
  if (tiers.length === 0) return null;

  const formatPrice = (p: { price: number; currency: string; billing: string }) => {
    if (p.price === 0) return '免费';
    const symbol = p.currency === 'CNY' ? '¥' : '$';
    const per = p.billing === 'yearly' ? '/年' : '/月';
    return `${symbol}${p.price.toLocaleString()}${per}`;
  };
}

// ── 产品定位速览（紧凑卡片）──
function MarketPositionTable({ data }: { data: { product: string; positioning: string; gtm_strategy: string; target_audience: string }[] }) {
  if (!data || data.length === 0) return null;

  const GTM_MAP: Record<string, { label: string; color: string }> = {
    'PLG': { label: '产品驱动', color: 'bg-emerald-100 text-emerald-700' },
    'sales-led': { label: '销售驱动', color: 'bg-amber-100 text-amber-700' },
    'channel': { label: '渠道驱动', color: 'bg-blue-100 text-blue-700' },
    'community': { label: '社区驱动', color: 'bg-purple-100 text-purple-700' },
  };

  return (
    <div className="space-y-2 flex flex-col justify-center" style={{ minHeight: 280 }}>
      {data.map(d => (
        <div key={d.product} className="rounded-lg border border-slate-100 bg-white px-3 py-2.5 flex-1 flex flex-col justify-center">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-xs font-semibold text-slate-800">{d.product}</span>
            <span className="text-[11px] text-slate-500 truncate" title={d.positioning}>
              · {d.positioning || '—'}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-slate-500 flex-wrap">
            {d.gtm_strategy && d.gtm_strategy.split(',').map((s: string) => {
              const tag = s.trim();
              const m = GTM_MAP[tag] || { label: tag, color: 'bg-slate-100 text-slate-600' };
              return (
                <span key={tag} className={`inline-block px-1.5 py-0.5 rounded font-medium ${m.color}`}>
                  {m.label}
                </span>
              );
            })}
            {d.target_audience && (
              <>
                <span className="text-slate-300">·</span>
                <span className="truncate max-w-[120px]" title={d.target_audience}>
                  {d.target_audience.length > 30 ? d.target_audience.slice(0, 30) + '…' : d.target_audience}
                </span>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b-2 border-slate-200">
            <th className="text-left py-2 px-2 font-semibold text-slate-600">档位</th>
            {products.map(p => (
              <th key={p} className="text-center py-2 px-2 font-semibold text-slate-700">{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tiers.map(tier => (
            <tr key={tier} className="border-b border-slate-100 hover:bg-slate-50">
              <td className="py-2 px-2 font-medium text-slate-700">
                <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                  tier === 'Free' ? 'bg-green-100 text-green-700' :
                  tier === 'Enterprise' ? 'bg-purple-100 text-purple-700' :
                  'bg-blue-50 text-blue-700'
                }`}>
                  {tier}
                </span>
              </td>
              {products.map(p => {
                const cell = byTier.get(tier)?.get(p);
                return (
                  <td key={p} className="text-center py-2 px-2 text-slate-600">
                    {cell ? (
                      <span className={cell.price === 0 ? 'text-green-600 font-medium' : ''}>
                        {formatPrice(cell)}
                      </span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── 节点类型中文标签 ──
const NODE_TYPE_LABELS: Record<string, string> = {
  SourceInfo: '来源链接',
  WebPage: '网页',
  FeatureNode: '功能',
  SentimentNode: '情感',
  PricingModel: '定价模型',
  PricingData: '定价明细',
  SWOTNode: 'SWOT',
  MarketPosition: '市场定位',
  TechStack: '技术栈',
  ScoringNode: '评分',
  ReportSection: '报告章节',
  Product: '产品',
};
