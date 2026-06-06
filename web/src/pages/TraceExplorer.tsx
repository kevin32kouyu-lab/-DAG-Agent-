import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import ConfidenceBar from '../components/ConfidenceBar';
import TracePanel from '../components/TracePanel';
import EmptyState from '../components/EmptyState';
import Spinner from '../components/Spinner';
import type { TraceResponse, StepTrace } from '../types';

/* ---- layer coloring ---- */

function layerColor(nodeType: string): string {
  if (['SourceInfo', 'WebPage', 'ReviewEntry', 'PricingData', 'NewsArticle', 'MetricData', 'SocialPost', 'ProductNode'].includes(nodeType))
    return 'text-slate-500';
  if (['FeatureNode', 'FeatureMatrix', 'SentimentNode', 'PricingModel', 'TechStack', 'MarketPositionNode', 'CrossReviewFlag'].includes(nodeType))
    return 'text-blue-700';
  if (['SWOTNode', 'ScoringNode', 'InsightNode', 'ReportSection'].includes(nodeType))
    return 'text-teal-700';
  return 'text-slate-500';
}

function layerBadge(nodeType: string): string {
  if (['SourceInfo', 'WebPage', 'ReviewEntry', 'PricingData', 'NewsArticle', 'MetricData', 'SocialPost', 'ProductNode'].includes(nodeType))
    return 'L1';
  if (['FeatureNode', 'FeatureMatrix', 'SentimentNode', 'PricingModel', 'TechStack', 'MarketPositionNode', 'CrossReviewFlag'].includes(nodeType))
    return 'L2';
  if (['SWOTNode', 'ScoringNode', 'InsightNode', 'ReportSection'].includes(nodeType))
    return 'L3';
  return '';
}

function formatContradiction(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const evidence = record.evidence;
    if (evidence && typeof evidence === 'object') {
      const label = (evidence as Record<string, unknown>).label;
      if (typeof label === 'string') return label;
    }
    if (typeof record.detail === 'string') return record.detail;
  }
  return JSON.stringify(value);
}

function readNodeId(node: Record<string, unknown>): string {
  return String(node.id || node.node_id || '');
}

function readNumber(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

async function fetchTrace(taskId: string | undefined, insightId: string): Promise<TraceResponse> {
  if (!taskId) throw new Error('任务 ID 缺失');
  const resp = await fetch(`/api/trace/${taskId}/${insightId}?include_steps=true`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

/* ---- component ---- */

export default function TraceExplorer() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const initialInsightId = searchParams.get('insight') || '';

  const [insightId, setInsightId] = useState(initialInsightId);
  const [data, setData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(initialInsightId));
  const [error, setError] = useState('');

  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [agentFilter, setAgentFilter] = useState('all');
  const [layerFilter, setLayerFilter] = useState<number | 'all'>('all');
  const [searchText, setSearchText] = useState('');
  const [showDetail, setShowDetail] = useState(false);

  const searchTrace = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError('');
    setData(null);
    setSelectedNodeId(null);
    try {
      setData(await fetchTrace(id, q));
    } catch (err) {
      setError(err instanceof Error ? err.message : '查询失败');
    } finally {
      setLoading(false);
    }
  }, [id]);

  const doSearch = useCallback(async (sid?: string) => {
    await searchTrace(sid || insightId);
  }, [insightId, searchTrace]);

  /* auto-search from URL query param */
  useEffect(() => {
    const qInsight = searchParams.get('insight');
    if (!qInsight) return;
    let ignore = false;
    fetchTrace(id, qInsight)
      .then(json => {
        if (ignore) return;
        setData(json);
        setError('');
      })
      .catch(err => {
        if (!ignore) setError(err instanceof Error ? err.message : '查询失败');
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => { ignore = true; };
  }, [id, searchParams]);

  /* filters */
  const chain = useMemo(() => data?.chain ?? [], [data]);

  const agentTypes = useMemo(() => {
    const types = new Set<string>();
    chain.forEach(e => {
      const a = e.node?.agent_type || e.node?.created_by;
      if (a) types.add(a as string);
    });
    return Array.from(types).sort();
  }, [chain]);

  const filteredChain = useMemo(() => {
    return chain.filter(e => {
      const node = e.node || {};
      const agent = (node.agent_type || node.created_by || '') as string;
      const ntype = (node.node_type || '') as string;
      const label = (node.label || node.id || '') as string;

      if (agentFilter !== 'all' && agent !== agentFilter) return false;
      if (layerFilter !== 'all') {
        const lb = layerBadge(ntype);
        if (lb !== `L${layerFilter}`) return false;
      }
      if (searchText && !label.toLowerCase().includes(searchText.toLowerCase())
        && !JSON.stringify(node).toLowerCase().includes(searchText.toLowerCase())) return false;
      return true;
    });
  }, [chain, agentFilter, layerFilter, searchText]);

  /* selection */
  const selectedEntry = selectedNodeId ? chain.find(e => readNodeId(e.node) === selectedNodeId) : null;
  const selectedNode = selectedEntry?.node;
  const selectedConfidence = selectedNode ? readNumber(selectedNode.confidence) : null;
  const stepTraces: StepTrace[] = selectedNodeId && data?.step_traces?.[selectedNodeId]
    ? data.step_traces[selectedNodeId]
    : [];

  const toggleNode = (nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const selectNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setShowDetail(true);
  };

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6 animate-pageEnter">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-950">溯源探索器</h1>
        <p className="mt-1 text-sm text-slate-500">任务: <span className="font-mono">{id}</span></p>
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <input
          value={insightId}
          onChange={e => setInsightId(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') doSearch(); }}
          placeholder="输入 Insight ID 或节点 ID..."
          className="flex-1 rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-teal-700"
        />
        <button
          onClick={() => doSearch()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded bg-teal-700 px-4 py-2 text-sm font-medium text-white transition-all hover:bg-teal-800 active:scale-95 disabled:bg-slate-300"
        >
          {loading && <Spinner size="sm" />}
          {loading ? '搜索中...' : '搜索'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {/* Confidence bar */}
      {data?.confidence !== null && data?.confidence !== undefined && (
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-500">置信度:</span>
          <div className="flex-1 max-w-xs">
            <ConfidenceBar value={data.confidence} size="lg" />
          </div>
          {data.confidence_breakdown && (
            <span className="text-xs text-slate-500">
              (支持: {data.confidence_breakdown.supporting_count}
              | 矛盾: {data.confidence_breakdown.contradicting_count}
              | 来源: {data.confidence_breakdown.total_sources})
            </span>
          )}
        </div>
      )}

      {/* Insight text */}
      {data?.insight && (
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-sm text-slate-700">{data.insight}</p>
        </div>
      )}

      {/* Filters */}
      {chain.length > 0 && (
        <div className="flex gap-3 flex-wrap items-center">
          <select
            value={agentFilter}
            onChange={e => setAgentFilter(e.target.value)}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600 outline-none focus:border-teal-700"
          >
            <option value="all">全部 Agent</option>
            {agentTypes.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <select
            value={layerFilter}
            onChange={e => setLayerFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600 outline-none focus:border-teal-700"
          >
            <option value="all">全部层级</option>
            <option value="1">Layer 1 (原始数据)</option>
            <option value="2">Layer 2 (分析层)</option>
            <option value="3">Layer 3 (综合层)</option>
          </select>
          <input
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            placeholder="搜索..."
            className="w-40 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 outline-none placeholder:text-slate-400 focus:border-teal-700"
          />
        </div>
      )}

      {/* Main content: tree + detail panel */}
      <div className="flex gap-4">
        {/* Trace tree */}
        <div data-testid="trace-tree-panel" className={`${showDetail && selectedNode ? 'w-1/2' : 'w-full'} space-y-0.5 rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-all`}>
          {loading && (
            <div className="py-8 text-center text-sm text-slate-500">加载溯源链...</div>
          )}
          {!loading && filteredChain.length === 0 && !data && (
            <EmptyState icon="🔍" title="输入 Insight ID 开始溯源" description="例如: insight_42" />
          )}
          {!loading && filteredChain.length === 0 && data && (
            <EmptyState icon="📭" title="无匹配节点" description="调整筛选条件" />
          )}

          {filteredChain.map((entry, i) => {
            const node = (entry.node || {}) as Record<string, unknown>;
            const nodeId = String(node.id || node.node_id || `tree-${i}`);
            const nodeType = String(node.node_type || 'Node');
            const label = String(node.label || node.id || node.node_id || '');
            const agent = String(node.created_by || node.agent_type || '');
            const expanded = expandedNodes.has(nodeId);
            const selected = selectedNodeId === nodeId;

            return (
              <div key={i} style={{ paddingLeft: `${entry.depth * 20}px` }}>
                <button
                  onClick={() => toggleNode(nodeId)}
                  onDoubleClick={() => selectNode(nodeId)}
                  className={`flex items-center gap-1.5 py-1 px-1.5 rounded w-full text-left group hover:bg-slate-50 ${
                    selected ? 'border border-teal-200 bg-teal-50' : ''
                  }`}
                >
                  <span className="w-3.5 flex-shrink-0 font-mono text-xs text-slate-400">
                    {expanded ? '▾' : '▸'}
                  </span>
                  <span className="flex-shrink-0 rounded bg-slate-100 px-1 font-mono text-[10px] text-slate-500">
                    {layerBadge(nodeType)}
                  </span>
                  <span className={`flex-shrink-0 font-mono text-xs uppercase ${layerColor(nodeType)}`}>
                    {nodeType}
                  </span>
                  <span className="flex-1 truncate text-xs text-slate-700">{label}</span>
                  {agent && <span className="hidden flex-shrink-0 font-mono text-[10px] text-slate-400 sm:inline">[{agent}]</span>}
                  <span
                    onClick={(e) => { e.stopPropagation(); selectNode(nodeId); }}
                    className="hidden flex-shrink-0 text-[10px] font-medium text-teal-700 hover:text-teal-900 group-hover:inline"
                  >
                    详情
                  </span>
                </button>

                {expanded && (
                  <div className="ml-8 mt-0.5 mb-1 rounded border border-slate-200 bg-slate-50 p-2">
                    <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-600">
                      {JSON.stringify(node, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Detail panel */}
        {showDetail && selectedNode && (
          <div className="w-1/2 space-y-3">
            {/* Node info */}
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-slate-900">节点详情</h3>
                <button onClick={() => setShowDetail(false)} className="text-xs text-slate-500 hover:text-slate-900">
                  关闭
                </button>
              </div>
              <dl className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <dt className="text-slate-500">节点类型</dt>
                  <dd className="font-mono text-slate-700">{String(selectedNode.node_type || '-')}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Agent</dt>
                  <dd className="font-mono text-slate-700">{String(selectedNode.agent_type || selectedNode.created_by || '-')}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">节点 ID</dt>
                  <dd className="ml-2 truncate font-mono text-slate-500">{String(selectedNode.id || '-')}</dd>
                </div>
                {selectedConfidence !== null && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">置信度</dt>
                    <dd className="font-mono text-slate-700">{Math.round(selectedConfidence * 100)}%</dd>
                  </div>
                )}
              </dl>
            </div>

            {/* StepTrace panel */}
            {stepTraces.length > 0 && (
              <TracePanel
                nodeId={selectedNodeId!}
                agentType={String(selectedNode.agent_type || selectedNode.created_by || '')}
                stepTraces={stepTraces}
              />
            )}

            {stepTraces.length === 0 && (
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <p className="text-xs text-slate-500">该节点暂无决策轨迹数据</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Contradictions */}
      {data?.contradicting_evidence && data.contradicting_evidence.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <h3 className="mb-2 text-sm font-medium text-red-700">
            ⚠ 矛盾证据 ({data.contradicting_evidence.length})
          </h3>
          {data.contradicting_evidence.map((c, i) => (
            <div key={i} className="mb-1 text-sm text-red-700">
              {formatContradiction(c)}
            </div>
          ))}
        </div>
      )}

      {/* Export */}
      {data && (
        <div className="flex justify-end">
          <button
            onClick={() => {
              const json = JSON.stringify(data, null, 2);
              const blob = new Blob([json], { type: 'application/json' });
              const a = document.createElement('a');
              a.href = URL.createObjectURL(blob);
              a.download = `trace-${id}-${insightId || 'export'}.json`;
              a.click();
            }}
            className="rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-500 transition-all hover:border-teal-300 hover:text-teal-800 active:scale-95"
          >
            导出 JSON
          </button>
        </div>
      )}
    </div>
  );
}
