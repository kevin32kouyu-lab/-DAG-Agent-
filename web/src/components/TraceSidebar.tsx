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

export default function TraceSidebar({ isOpen, onClose, insightId, taskId, sectionTitle }: TraceSidebarProps) {
  const [data, setData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(() => isOpen && Boolean(insightId));
  const [fetchError, setFetchError] = useState('');
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const navigate = useNavigate();

  useEffect(() => {
    if (!isOpen || !insightId) return;
    let ignore = false;
    fetch(`/api/trace/${taskId}/${insightId}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        if (ignore) return;
        if (d) setData(d);
        setFetchError('');
      })
      .catch((err: Error) => {
        if (!ignore) setFetchError(err.message || '网络请求失败');
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => { ignore = true; };
  }, [isOpen, insightId, taskId]);

  if (!isOpen) return null;

  const toggle = (i: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(i)) {
        next.delete(i);
      } else {
        next.add(i);
      }
      return next;
    });
  };

  return (
    <>
      {/* backdrop */}
      <div className="fixed inset-0 z-30 bg-slate-950/20" onClick={onClose} />

      {/* sidebar */}
      <div className="fixed right-0 top-0 bottom-0 z-40 flex w-[420px] transform flex-col border-l border-slate-200 bg-white shadow-2xl transition-transform duration-200">
        {/* header */}
        <div className="flex items-center justify-between border-b border-slate-200 p-4">
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">{sectionTitle}</p>
            <p className="text-xs text-slate-500">溯源链</p>
          </div>
          <button onClick={onClose} className="ml-2 text-lg text-slate-500 hover:text-slate-900">&times;</button>
        </div>

        {/* body */}
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {loading && (
            <div className="py-8 text-center text-sm text-slate-500">加载溯源数据...</div>
          )}

          {!loading && !data && !fetchError && (
            <div className="py-8 text-center text-sm text-slate-500">无溯源数据</div>
          )}
          {!loading && fetchError && (
            <div className="py-8 text-center text-sm text-red-700">加载失败: {fetchError}</div>
          )}

          {data && (
            <>
              {/* confidence */}
              <div>
                <span className="text-xs text-slate-500">置信度</span>
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
                <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                  <h4 className="mb-1 text-xs font-medium text-red-700">
                    ⚠ 矛盾证据 ({data.contradicting_evidence.length})
                  </h4>
                  {data.contradicting_evidence.map((c, i) => (
                    <div key={i} className="mt-1 text-xs text-red-700">
                      {formatContradiction(c)}
                    </div>
                  ))}
                </div>
              )}

              {/* confidence breakdown */}
              {data.confidence_breakdown && (
                <div className="text-xs text-slate-500">
                  支持: <span className="font-mono">{data.confidence_breakdown.supporting_count}</span> 条
                  | 矛盾: <span className="font-mono">{data.confidence_breakdown.contradicting_count}</span> 条
                  | 来源: <span className="font-mono">{data.confidence_breakdown.total_sources}</span> 个
                </div>
              )}
            </>
          )}
        </div>

        {/* footer */}
        <div className="border-t border-slate-200 p-3">
          <button
            onClick={() => {
              navigate(`/task/${taskId}/trace?insight=${insightId}`);
              onClose();
            }}
            className="w-full rounded border border-teal-200 bg-teal-50 py-2 text-sm font-medium text-teal-800 transition-colors hover:border-teal-300 hover:bg-teal-100"
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
    layer1: 'text-slate-500', SourceInfo: 'text-slate-500', WebPage: 'text-slate-500',
    ReviewEntry: 'text-slate-500', PricingData: 'text-slate-500',
  };
  const typeColor = nodeType.startsWith('Feature') || nodeType === 'SentimentNode'
    ? 'text-blue-700' : nodeType.startsWith('SWOT') || nodeType === 'InsightNode'
    ? 'text-teal-700' : '';

  return (
    <div style={{ paddingLeft: `${depth * 16}px` }}>
      <button
        onClick={onToggle}
        className="group flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left hover:bg-slate-50"
      >
        <span className="w-3.5 flex-shrink-0 font-mono text-xs text-slate-400">
          {expanded ? '▾' : '▸'}
        </span>
        <span className={`flex-shrink-0 font-mono text-xs uppercase ${typeColor || layerColors[nodeType] || 'text-slate-500'}`}>
          {nodeType}
        </span>
        <span className="truncate text-xs text-slate-700">{label}</span>
        {agent && <span className="flex-shrink-0 font-mono text-xs text-slate-400">[{agent}]</span>}
      </button>
      {expanded && (
        <div className="ml-5 mt-0.5 mb-1 rounded border border-slate-200 bg-slate-50 p-2">
          <pre className="max-h-32 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-600">
            {JSON.stringify(node, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
