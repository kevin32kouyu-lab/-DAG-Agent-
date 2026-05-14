import { useState } from 'react';
import { useParams } from 'react-router-dom';

interface TraceNode {
  node: Record<string, any>;
  incoming: any[];
  outgoing: any[];
  depth: number;
}

export default function TraceExplorer() {
  const { id } = useParams<{ id: string }>();
  const [insightId, setInsightId] = useState('');
  const [chain, setChain] = useState<TraceNode[]>([]);
  const [contradictions, setContradictions] = useState<any[]>([]);
  const [breakdown, setBreakdown] = useState<any>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const search = async () => {
    if (!insightId.trim()) return;
    try {
      const resp = await fetch(`/api/trace/${id}/${insightId}?include_steps=true`);
      if (resp.ok) {
        const data = await resp.json();
        setChain(data.chain || []);
        setContradictions(data.contradicting_evidence || []);
        setBreakdown(data.confidence_breakdown);
        setConfidence(data.confidence);
      }
    } catch (_err) { /* ignore */ }
  };

  const toggle = (i: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-100">溯源探索器</h1>
        <p className="text-gray-500 text-sm font-mono mt-1">任务: {id}</p>
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <input
          value={insightId}
          onChange={e => setInsightId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          placeholder="输入 Insight ID..."
          className="flex-1 px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm text-gray-200 font-mono focus:border-cyan-500 outline-none"
        />
        <button onClick={search} className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-sm font-medium">
          搜索
        </button>
      </div>

      {/* Confidence */}
      {confidence !== null && (
        <div className="flex items-center gap-4 text-sm font-mono">
          <span className="text-gray-500">置信度:</span>
          <span className={`text-lg font-bold ${confidence >= 0.8 ? 'text-green-400' : confidence >= 0.6 ? 'text-amber-400' : 'text-red-400'}`}>
            {(confidence * 100).toFixed(0)}%
          </span>
          {breakdown && (
            <span className="text-gray-600">
              (支持: {breakdown.supporting_count} | 矛盾: {breakdown.contradicting_count})
            </span>
          )}
        </div>
      )}

      {/* Trace Tree */}
      {chain.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-1">
          {chain.map((entry, i) => (
            <div key={i} style={{ paddingLeft: `${entry.depth * 20}px` }}>
              <button
                onClick={() => toggle(i)}
                className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-gray-800/50 w-full text-left group"
              >
                <span className="text-gray-600 font-mono text-xs w-4">
                  {expanded.has(i) ? '▾' : '▸'}
                </span>
                <span className="text-gray-400 font-mono text-xs uppercase">{entry.node.node_type || 'Node'}</span>
                <span className="text-gray-300 text-sm truncate">{entry.node.label || entry.node.id}</span>
              </button>
              {expanded.has(i) && (
                <div className="ml-6 mt-1 mb-2 p-3 bg-gray-950 rounded border border-gray-800/50">
                  <pre className="text-xs text-gray-500 font-mono whitespace-pre-wrap overflow-auto max-h-40">
                    {JSON.stringify(entry.node, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Contradictions */}
      {contradictions.length > 0 && (
        <div className="bg-red-900/10 border border-red-800/30 rounded-lg p-4">
          <h3 className="text-red-400 text-sm font-medium mb-2">⚠ 矛盾证据 ({contradictions.length})</h3>
          {contradictions.map((c, i) => (
            <div key={i} className="text-sm text-gray-400 font-mono mb-1">
              {JSON.stringify(c.evidence?.label || c)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
