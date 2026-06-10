import { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import EmptyState from '../components/EmptyState';
import LoadingSkeleton from '../components/LoadingSkeleton';

interface SourceNode {
  id: string; url?: string; domain?: string; label: string;
  credibility_score?: number; snippet?: string; node_type: string; layer: number;
  product?: string; confidence?: number;
}
interface EvidenceEdge { source_id: string; target_id: string; edge_type: string; }

function credBadge(s: number) {
  const pct = Math.round(s * 100);
  if (s >= 0.8) return { text: `${pct}%`, cls: 'bg-emerald-500' };
  if (s >= 0.6) return { text: `${pct}%`, cls: 'bg-emerald-400' };
  if (s >= 0.5) return { text: `${pct}%`, cls: 'bg-amber-400' };
  if (s >= 0.3) return { text: `${pct}%`, cls: 'bg-orange-400' };
  return { text: `${pct}%`, cls: 'bg-red-400' };
}

const NODE_ICONS: Record<string, string> = {
  SourceInfo: '🔗', WebPage: '📄', FeatureNode: '⚡', SentimentNode: '💬',
  PricingModel: '💰', PricingData: '💵', MarketPosition: '📍',
  SWOTNode: '🎯', ScoringNode: '📊', ReportSection: '📝', Product: '🏷️',
};
const NODE_ZH: Record<string, string> = {
  SourceInfo: '来源链接', WebPage: '网页内容', FeatureNode: '功能特征',
  SentimentNode: '用户口碑', PricingModel: '定价模型', PricingData: '定价明细',
  MarketPosition: '市场定位', SWOTNode: 'SWOT 分析', ScoringNode: '维度评分',
  ReportSection: '报告章节', Product: '产品',
};
const LAYER_ZH = ['', '原始数据', '分析结果', '报告输出'];

type Tab = 'sources' | 'evidence';

export default function Sources() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const isDemo = searchParams.get('demo') === 'true';
  const taskId = isDemo ? (searchParams.get('task') || id || '') : (id || '');

  const [allNodes, setAllNodes] = useState<SourceNode[]>([]);
  const [edges, setEdges] = useState<EvidenceEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [layerFilter, setLayerFilter] = useState<number | 'all'>('all');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [tab, setTab] = useState<Tab>('sources');

  useEffect(() => {
    if (!taskId) return;
    let ignore = false;
    fetch(`/api/sources/${taskId}`)
      .then(r => r.json())
      .then(data => {
        if (ignore) return;
        setAllNodes(data.sources || []);
        setEdges(data.edges || []);
      })
      .catch(() => {})
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [taskId]);

  const filtered = layerFilter === 'all' ? allNodes : allNodes.filter(n => n.layer === layerFilter);
  const l1 = allNodes.filter(n => n.layer === 1);
  const l2 = allNodes.filter(n => n.layer === 2);
  const l3 = allNodes.filter(n => n.layer === 3);
  const layerColors = ['', '#3b82f6', '#8b5cf6', '#10b981'];

  if (loading) return <div className="max-w-6xl mx-auto px-8 py-10"><LoadingSkeleton lines={10} /></div>;

  return (
    <div className="max-w-6xl mx-auto px-8 py-8 animate-pageEnter">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-xs font-semibold text-primary/70 mb-1">来源追溯 · Data Provenance</p>
          <h1 className="font-headline text-2xl font-semibold text-on-surface">资料来源与证据追溯</h1>
          <p className="mt-1 text-sm text-on-surface-variant">验证来源可靠性，追溯从数据到结论的完整路径。</p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="rounded-lg bg-surface-container px-3 py-1.5 font-medium">{allNodes.length} 节点</span>
          <span className="rounded-lg bg-surface-container px-3 py-1.5 font-medium">{edges.length} 关联</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-surface-container rounded-lg p-1 w-fit">
        {[
          { key: 'sources' as Tab, label: '数据来源', en: 'Sources', icon: '📋' },
          { key: 'evidence' as Tab, label: '证据追溯', en: 'Evidence', icon: '🔗' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              tab === t.key ? 'bg-surface text-on-surface shadow-sm' : 'text-on-surface-variant hover:text-on-surface'
            }`}>
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab: Sources ── */}
      {tab === 'sources' && (
        <>
          <div className="flex gap-2 mb-4">
            {[
              { key: 'all' as const, label: `全部 (${allNodes.length})` },
              { key: 1, label: `原始数据 (${l1.length})` },
              { key: 2, label: `分析结果 (${l2.length})` },
              { key: 3, label: `报告输出 (${l3.length})` },
            ].map(opt => (
              <button key={opt.key} onClick={() => setLayerFilter(opt.key)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  layerFilter === opt.key ? 'bg-primary text-white' : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                }`}>
                {opt.label}
              </button>
            ))}
          </div>

          {filtered.length === 0 && <EmptyState icon="📋" title="暂无来源" description="当前任务未产出数据" />}

          <div className="space-y-1.5">
            {filtered.slice(0, 200).map(src => {
              const cred = credBadge(src.credibility_score ?? 0.5);
              const isExp = expanded.has(src.id);
              const icon = NODE_ICONS[src.node_type] || '📌';
              const typeZh = NODE_ZH[src.node_type] || src.node_type;
              return (
                <div key={src.id} className="rounded-lg border border-border-subtle bg-surface overflow-hidden">
                  <button onClick={() => setExpanded(prev => { const n = new Set(prev); n.has(src.id) ? n.delete(src.id) : n.add(src.id); return n; })}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-container/50 transition-colors">
                    <span className="text-base flex-shrink-0">{icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-on-surface truncate">{src.label || src.url || src.id}</div>
                      {src.url && <div className="text-[11px] text-on-surface-variant/50 truncate mt-0.5">{src.url}</div>}
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium text-white ${cred.cls}`}>{cred.text}</span>
                    <span className="text-[10px] text-on-surface-variant/40 font-medium">{LAYER_ZH[src.layer]}</span>
                    <span className="text-on-surface-variant/30 text-sm">{isExp ? '▲' : '▼'}</span>
                  </button>
                  {isExp && (
                    <div className="border-t border-border-subtle bg-surface-container/20 px-4 py-3">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div><span className="text-on-surface-variant/60">域名：</span><span>{src.domain || '—'}</span></div>
                        <div><span className="text-on-surface-variant/60">可信度：</span><span className="font-semibold">{Math.round((src.credibility_score ?? 0.5) * 100)}%</span></div>
                        <div><span className="text-on-surface-variant/60">类型：</span><span>{typeZh}</span></div>
                        <div><span className="text-on-surface-variant/60">层级：</span><span>{LAYER_ZH[src.layer]}</span></div>
                      </div>
                      {src.snippet && <p className="mt-2 text-xs text-on-surface-variant/60 italic">「{src.snippet.slice(0, 300)}」</p>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ── Tab: Evidence ── */}
      {tab === 'evidence' && (
        <>
          {allNodes.length === 0 ? <EmptyState icon="🔗" title="暂无证据链" description="当前任务未产出数据" /> : (
            <>
              <div className="grid grid-cols-3 gap-5 mb-6">
                {[1, 2, 3].map(li => {
                  const lnodes = allNodes.filter(n => n.layer === li);
                  return (
                    <div key={li} className="rounded-xl border border-border-subtle bg-surface overflow-hidden">
                      <div className="px-4 py-3 border-b border-border-subtle flex items-center gap-2" style={{ borderLeft: `4px solid ${layerColors[li]}` }}>
                        <span className="font-headline text-sm font-semibold">{LAYER_ZH[li]}</span>
                        <span className="text-xs text-on-surface-variant">Layer {li}</span>
                        <span className="ml-auto rounded-full bg-surface-container px-2 py-0.5 text-[11px] font-medium">{lnodes.length}</span>
                      </div>
                      <div className="divide-y divide-border-subtle max-h-[55vh] overflow-y-auto">
                        {lnodes.slice(0, 30).map(n => (
                          <div key={n.id} className="px-4 py-2.5 hover:bg-surface-container/50 transition-colors">
                            <div className="text-xs font-medium text-on-surface truncate">{n.label}</div>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-[10px] text-on-surface-variant/50">{NODE_ZH[n.node_type] || n.node_type}</span>
                              {n.product && <span className="text-[10px] text-primary/70 font-medium">{n.product}</span>}
                              {n.confidence !== undefined && (
                                <span className={`text-[10px] font-medium ${n.confidence >= 0.7 ? 'text-emerald-600' : n.confidence >= 0.4 ? 'text-amber-600' : 'text-red-500'}`}>
                                  {Math.round(n.confidence * 100)}%
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {l3.length > 0 && (
                <div className="mt-6 rounded-xl border border-border-subtle bg-surface p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-base">💡</span>
                    <span className="font-headline text-sm font-semibold">核心结论</span>
                  </div>
                  <div className="space-y-2">
                    {l3.slice(0, 5).map(n => (
                      <div key={n.id} className="flex items-start gap-2 text-sm text-on-surface-variant">
                        <span className="mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full" style={{ background: layerColors[3] }} />
                        <span>{n.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
