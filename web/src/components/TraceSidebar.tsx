import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ConfidenceBar from './ConfidenceBar';
import type { TraceResponse, TraceNodeEntry } from '../types';

interface TraceSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  insightId: string;
  taskId: string;
  sectionTitle: string;
}

export default function TraceSidebar({ isOpen, onClose, insightId, taskId, sectionTitle }: TraceSidebarProps) {
  const [data, setData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    if (!isOpen || !insightId) return;
    setLoading(true);
    setFetchError('');
    fetch(`/api/trace/${taskId}/${insightId}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => { if (d) setData(d); })
      .catch((err: Error) => { setFetchError(err.message || '网络请求失败'); })
      .finally(() => setLoading(false));
  }, [isOpen, insightId, taskId]);

  if (!isOpen) return null;

  const toggle = (i: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  return (
    <>
      {/* backdrop */}
      <div className="fixed inset-0 bg-black/40 z-30" onClick={onClose} />

      {/* sidebar */}
      <div className="fixed right-0 top-0 bottom-0 w-[420px] bg-gray-950 border-l border-gray-800 z-40 flex flex-col shadow-2xl transform transition-transform duration-200">
        {/* header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-300 font-medium truncate">{sectionTitle}</p>
            <p className="text-xs text-gray-600 font-mono">溯源链</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg font-mono ml-2">&times;</button>
        </div>

        {/* body */}
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {loading && (
            <div className="text-gray-600 font-mono text-sm text-center py-8">加载溯源数据...</div>
          )}

          {!loading && !data && !fetchError && (
            <div className="text-gray-600 font-mono text-sm text-center py-8">无溯源数据</div>
          )}
          {!loading && fetchError && (
            <div className="text-red-400 font-mono text-sm text-center py-8">加载失败: {fetchError}</div>
          )}

          {data && (
            <>
              {/* confidence */}
              <div>
                <span className="text-xs text-gray-500">置信度</span>
                <ConfidenceBar value={data.confidence ?? 0} size="md" />
              </div>

              {/* trace tree */}
              <div className="space-y-0.5">
                {data.chain.map((entry, i) => (
                  <TreeRow
                    key={i}
                    entry={entry}
                    expanded={expanded.has(i)}
                    onToggle={() => toggle(i)}
                    depth={0}
                  />
                ))}
              </div>

              {/* contradictions */}
              {data.contradicting_evidence.length > 0 && (
                <div className="bg-red-900/10 border border-red-800/30 rounded-lg p-3">
                  <h4 className="text-red-400 text-xs font-medium mb-1">
                    ⚠ 矛盾证据 ({data.contradicting_evidence.length})
                  </h4>
                  {data.contradicting_evidence.map((c: any, i: number) => (
                    <div key={i} className="text-xs text-gray-400 font-mono mt-1">
                      {typeof c === 'string' ? c : c.evidence?.label || c.detail || JSON.stringify(c)}
                    </div>
                  ))}
                </div>
              )}

              {/* confidence breakdown */}
              {data.confidence_breakdown && (
                <div className="text-xs text-gray-500 font-mono">
                  支持: {data.confidence_breakdown.supporting_count} 条
                  | 矛盾: {data.confidence_breakdown.contradicting_count} 条
                  | 来源: {data.confidence_breakdown.total_sources} 个
                </div>
              )}
            </>
          )}
        </div>

        {/* footer */}
        <div className="p-3 border-t border-gray-800">
          <button
            onClick={() => {
              navigate(`/task/${taskId}/trace?insight=${insightId}`);
              onClose();
            }}
            className="w-full py-2 text-sm text-cyan-400 hover:text-cyan-300 font-mono border border-gray-800 rounded hover:border-cyan-800/50 transition-colors"
          >
            查看完整溯源图 →
          </button>
        </div>
      </div>
    </>
  );
}

/* ---- tree row sub-component ---- */

function TreeRow({ entry, expanded, onToggle, depth }: {
  entry: TraceNodeEntry;
  expanded: boolean;
  onToggle: () => void;
  depth: number;
}) {
  const node = (entry.node || {}) as Record<string, unknown>;
  const nodeType = String(node.node_type || 'Node');
  const label = String(node.label || node.id || '');
  const agent = String(node.created_by || node.agent_type || '');

  const layerColors: Record<string, string> = {
    layer1: 'text-gray-500', SourceInfo: 'text-gray-400', WebPage: 'text-gray-400',
    ReviewEntry: 'text-gray-400', PricingData: 'text-gray-400',
  };
  const typeColor = nodeType.startsWith('Feature') || nodeType === 'SentimentNode'
    ? 'text-blue-400' : nodeType.startsWith('SWOT') || nodeType === 'InsightNode'
    ? 'text-cyan-400' : '';

  return (
    <div style={{ paddingLeft: `${depth * 16}px` }}>
      <button
        onClick={onToggle}
        className="flex items-center gap-1.5 py-1 px-1.5 rounded hover:bg-gray-800/50 w-full text-left group"
      >
        <span className="text-gray-600 font-mono text-xs w-3.5 flex-shrink-0">
          {expanded ? '▾' : '▸'}
        </span>
        <span className={`font-mono text-xs uppercase flex-shrink-0 ${typeColor || layerColors[nodeType] || 'text-gray-400'}`}>
          {nodeType}
        </span>
        <span className="text-gray-300 text-xs truncate">{label}</span>
        {agent && <span className="text-gray-600 text-xs font-mono flex-shrink-0">[{agent}]</span>}
      </button>
      {expanded && (
        <div className="ml-5 mt-0.5 mb-1 p-2 bg-gray-900 rounded border border-gray-800/50">
          <pre className="text-xs text-gray-500 font-mono whitespace-pre-wrap overflow-auto max-h-32">
            {JSON.stringify(node, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
