import { useState, useEffect } from 'react';
import LoadingSkeleton from '../LoadingSkeleton';
import EmptyState from '../EmptyState';
import ChartCard from './ChartCard';
import RadarChart from './RadarChart';
import BarChart from './BarChart';
import FeatureHeatmap from './FeatureHeatmap';
import SWOTQuadrant from './SWOTQuadrant';
import type { AnalyticsResponse } from '../../types';

export default function AnalyticsDashboard({ taskId }: { taskId: string }) {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    fetch(`/api/report/${taskId}/analytics`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  if (loading) {
    return (
      <div className="bg-gray-900/50 border border-gray-800/50 rounded-2xl p-8">
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState icon="⚠" title="图表加载失败" description={error} />
    );
  }

  if (!data) return null;

  const hasAnyData = data.products.length > 0 && (
    data.scoring.length > 0 ||
    data.features.features.length > 0 ||
    data.sentiment.topics.length > 0 ||
    data.pricing.plans.length > 0 ||
    data.swot.length > 0
  );

  if (!hasAnyData) {
    return (
      <EmptyState
        icon="📊"
        title="暂无图表数据"
        description="分析任务尚未产生足够的结构化数据，请等待所有 Agent 完成分析"
      />
    );
  }

  // Build sentiment bar data from products
  const sentimentKeys = data.sentiment.products.length > 0
    ? data.sentiment.products.map(p => `${p}_score`)
    : [];
  const sentimentData = data.sentiment.topics.map(t => {
    const row: Record<string, unknown> = { topic: t.topic };
    for (const k of sentimentKeys) row[k] = t[k] ?? 0;
    return row;
  });

  // Build pricing bar data
  const pricingKeys = data.products.length > 0 ? data.products : [];
  const pricingByPlan = new Map<string, Record<string, unknown>>();
  for (const plan of data.pricing.plans) {
    const key = plan.plan_name || plan.product;
    if (!pricingByPlan.has(key)) {
      pricingByPlan.set(key, { plan_name: key });
    }
    pricingByPlan.get(key)![plan.product] = plan.price;
  }

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold text-gray-200">📊 分析仪表盘</span>
        <span className="text-xs text-gray-600 font-mono">
          {data.products.length} 产品 · {data.scoring.length > 0 ? `${new Set(data.scoring.map(s => s.dimension)).size} 维度` : ''}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Radar — dimension scoring */}
        <ChartCard
          title="维度评分对比"
          subtitle="Radar"
          icon="🎯"
          isEmpty={data.scoring.length === 0}
          emptyMessage="暂无评分数据"
        >
          <RadarChart data={data.scoring} products={data.products} />
        </ChartCard>

        {/* Sentiment bar chart */}
        <ChartCard
          title="用户情感分析"
          subtitle="Sentiment Score"
          icon="💬"
          isEmpty={data.sentiment.topics.length === 0}
          emptyMessage="暂无情感数据"
        >
          <BarChart
            data={sentimentData}
            dataKeys={sentimentKeys}
            xAxisKey="topic"
            products={data.sentiment.products}
            height={360}
          />
        </ChartCard>

        {/* Feature heatmap — maturity */}
        <ChartCard
          title="功能成熟度矩阵"
          subtitle="Maturity Heatmap"
          icon="⚡"
          isEmpty={data.features.features.length === 0}
          emptyMessage="暂无功能分析数据"
        >
          <FeatureHeatmap data={data.features} mode="maturity" />
        </ChartCard>

        {/* SWOT quadrant */}
        <ChartCard
          title="SWOT 分析概览"
          subtitle="Quadrant"
          icon="🎯"
          isEmpty={data.swot.length === 0}
          emptyMessage="暂无 SWOT 数据"
        >
          <SWOTQuadrant data={data.swot} products={data.products} />
        </ChartCard>

        {/* Pricing bar chart */}
        <ChartCard
          title="定价方案对比"
          subtitle="Price Plans"
          icon="💰"
          isEmpty={data.pricing.plans.length === 0}
          emptyMessage="暂无定价数据"
        >
          <BarChart
            data={[...pricingByPlan.values()]}
            dataKeys={pricingKeys}
            xAxisKey="plan_name"
            products={pricingKeys}
            height={320}
          />
        </ChartCard>

        {/* Value score chart */}
        <ChartCard
          title="价值评分对比"
          subtitle="Value Score (0-1)"
          icon="📈"
          isEmpty={data.pricing.value_scores.length === 0}
          emptyMessage="暂无价值评分"
        >
          <BarChart
            data={data.pricing.value_scores as unknown as Record<string, unknown>[]}
            dataKeys={['value_score']}
            xAxisKey="product"
            products={data.products}
            height={320}
            layout="vertical"
          />
        </ChartCard>
      </div>
    </div>
  );
}
