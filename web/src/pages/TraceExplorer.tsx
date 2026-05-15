import { useState, useEffect, useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import ConfidenceBar from '../components/ConfidenceBar';
import TracePanel from '../components/TracePanel';
import EmptyState from '../components/EmptyState';
import Spinner from '../components/Spinner';
import type { TraceResponse, StepTrace } from '../types';

/* ---- layer coloring ---- */

function layerColor(nodeType: string): string {
  if (['SourceInfo', 'WebPage', 'ReviewEntry', 'PricingData', 'NewsArticle', 'MetricData', 'SocialPost', 'ProductNode'].includes(nodeType))
    return 'text-gray-500';
  if (['FeatureNode', 'FeatureMatrix', 'SentimentNode', 'PricingModel', 'TechStack', 'MarketPositionNode', 'CrossReviewFlag'].includes(nodeType))
    return 'text-blue-400';
  if (['SWOTNode', 'ScoringNode', 'InsightNode', 'ReportSection'].includes(nodeType))
    return 'text-cyan-400';
  return 'text-gray-400';
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

/* ---- component ---- */

export default function TraceExplorer() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();

  const [insightId, setInsightId] = useState(searchParams.get('insight') || '');
  const [data, setData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [agentFilter, setAgentFilter] = useState('all');
  const [layerFilter, setLayerFilter] = useState<number | 'all'>('all');
  const [searchText, setSearchText] = useState('');
  const [showDetail, setShowDetail] = useState(false);

  /* auto-search from URL query param */
  useEffect(() => {
    const qInsight = searchParams.get('insight');
    if (qInsight && qInsight !== insightId) {
      setInsightId(qInsight);
      doSearch(qInsight);
    }
  }, [searchParams]);

  const doSearch = async (sid?: string) => {
    const q = sid || insightId;
    if (!q.trim()) return;
    setLoading(true);
    setError('');
    setData(null);
    setSelectedNodeId(null);
    try {
      const resp = await fetch(`/api/trace/${id}/${q}?include_steps=true`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || '查询失败');
    } finally {
      setLoading(false);
    }
  };

  /* filters */
  const chain = data?.chain ?? [];

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
  const selectedEntry = selectedNodeId ? chain.find(e => (e.node as any)?.id === selectedNodeId) : null;
  const selectedNode = selectedEntry?.node as Record<string, any> | undefined;
  const stepTraces: StepTrace[] = selectedNodeId && data?.step_traces?.[selectedNodeId]
    ? data.step_traces[selectedNodeId]
    : [];

  const toggleNode = (nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      next.has(nodeId) ? next.delete(nodeId) : next.add(nodeId);
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
        <h1 className="text-xl font-bold text-gray-100">溯源探索器</h1>
        <p className="text-gray-500 text-sm font-mono mt-1">任务: {id}</p>
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <input
          value={insightId}
          onChange={e => setInsightId(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') doSearch(); }}
          placeholder="输入 Insight ID 或节点 ID..."
          className="flex-1 px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm text-gray-200 font-mono focus:border-cyan-500 outline-none placeholder-gray-600"
        />
        <button
          onClick={() => doSearch()}
          disabled={loading}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 text-white rounded text-sm font-medium transition-all active:scale-95 inline-flex items-center gap-1.5"
        >
          {loading && <Spinner size="sm" />}
          {loading ? '搜索中...' : '搜索'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/10 border border-red-800/30 rounded-lg p-4 text-sm text-red-400 font-mono">{error}</div>
      )}

      {/* Confidence bar */}
      {data?.confidence !== null && data?.confidence !== undefined && (
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500 font-mono">置信度:</span>
          <div className="flex-1 max-w-xs">
            <ConfidenceBar value={data.confidence} size="lg" />
          </div>
          {data.confidence_breakdown && (
            <span className="text-xs text-gray-600 font-mono">
              (支持: {data.confidence_breakdown.supporting_count}
              | 矛盾: {data.confidence_breakdown.contradicting_count}
              | 来源: {data.confidence_breakdown.total_sources})
            </span>
          )}
        </div>
      )}

      {/* Insight text */}
      {data?.insight && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <p className="text-gray-300 text-sm">{data.insight}</p>
        </div>
      )}

      {/* Filters */}
      {chain.length > 0 && (
        <div className="flex gap-3 flex-wrap items-center">
          <select
            value={agentFilter}
            onChange={e => setAgentFilter(e.target.value)}
            className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 font-mono focus:border-cyan-600 outline-none"
          >
            <option value="all">全部 Agent</option>
            {agentTypes.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <select
            value={layerFilter}
            onChange={e => setLayerFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 font-mono focus:border-cyan-600 outline-none"
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
            className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-gray-300 font-mono focus:border-cyan-600 outline-none w-40 placeholder-gray-600"
          />
        </div>
      )}

      {/* Main content: tree + detail panel */}
      <div className="flex gap-4">
        {/* Trace tree */}
        <div className={`${showDetail && selectedNode ? 'w-1/2' : 'w-full'} bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-0.5 transition-all`}>
          {loading && (
            <div className="text-gray-600 font-mono text-sm text-center py-8">加载溯源链...</div>
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
                  className={`flex items-center gap-1.5 py-1 px-1.5 rounded w-full text-left group hover:bg-gray-800/50 ${
                    selected ? 'bg-cyan-900/20 border border-cyan-800/30' : ''
                  }`}
                >
                  <span className="text-gray-600 font-mono text-xs w-3.5 flex-shrink-0">
                    {expanded ? '▾' : '▸'}
                  </span>
                  <span className="text-gray-600 font-mono text-[10px] bg-gray-800 px-1 rounded flex-shrink-0">
                    {layerBadge(nodeType)}
                  </span>
                  <span className={`font-mono text-xs uppercase flex-shrink-0 ${layerColor(nodeType)}`}>
                    {nodeType}
                  </span>
                  <span className="text-gray-300 text-xs truncate flex-1">{label}</span>
                  {agent && <span className="text-gray-600 text-[10px] font-mono flex-shrink-0 hidden sm:inline">[{agent}]</span>}
                  <span
                    onClick={(e) => { e.stopPropagation(); selectNode(nodeId); }}
                    className="text-cyan-600 hover:text-cyan-400 text-[10px] font-mono flex-shrink-0 hidden group-hover:inline"
                  >
                    详情
                  </span>
                </button>

                {expanded && (
                  <div className="ml-8 mt-0.5 mb-1 p-2 bg-gray-950 rounded border border-gray-800/50">
                    <pre className="text-xs text-gray-500 font-mono whitespace-pre-wrap overflow-auto max-h-40">
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
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-300">节点详情</h3>
                <button onClick={() => setShowDetail(false)} className="text-gray-500 hover:text-gray-300 text-xs font-mono">
                  关闭
                </button>
              </div>
              <dl className="space-y-1 text-xs font-mono">
                <div className="flex justify-between">
                  <dt className="text-gray-500">节点类型</dt>
                  <dd className="text-gray-300">{String(selectedNode.node_type || '-')}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Agent</dt>
                  <dd className="text-gray-300">{String(selectedNode.agent_type || selectedNode.created_by || '-')}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">节点 ID</dt>
                  <dd className="text-gray-500 truncate ml-2">{String(selectedNode.id || '-')}</dd>
                </div>
                {selectedNode.confidence !== undefined && (
                  <div className="flex justify-between">
                    <dt className="text-gray-500">置信度</dt>
                    <dd className="text-gray-300">{Math.round(selectedNode.confidence * 100)}%</dd>
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
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <p className="text-gray-600 font-mono text-xs">该节点暂无决策轨迹数据</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Contradictions */}
      {data?.contradicting_evidence && data.contradicting_evidence.length > 0 && (
        <div className="bg-red-900/10 border border-red-800/30 rounded-lg p-4">
          <h3 className="text-red-400 text-sm font-medium mb-2">
            ⚠ 矛盾证据 ({data.contradicting_evidence.length})
          </h3>
          {data.contradicting_evidence.map((c: any, i: number) => (
            <div key={i} className="text-sm text-gray-400 font-mono mb-1">
              {typeof c === 'string' ? c : c.evidence?.label || c.detail || JSON.stringify(c)}
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
            className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-300 font-mono border border-gray-800 rounded hover:border-gray-700 transition-all active:scale-95"
          >
            导出 JSON
          </button>
        </div>
      )}
    </div>
  );
}
