import { useMemo } from 'react';
import type { DAGNode } from '../types';

/* ---- layer layout ---- */

const LAYER_MAP: Record<string, number> = {
  Orchestrator: 0,
  SourceDiscovery: 1,
  Collector: 2,
  DataEnricher: 3,
  FeatureAnalyzer: 4,
  SentimentAnalyzer: 4,
  PricingAnalyst: 4,
  TechStackAnalyzer: 4,
  MarketPositionAnalyzer: 4,
  CrossReviewAgent: 5,
  SWOTAnalyzer: 6,
  ReportGenerator: 7,
  QA_FactCheck: 8,
  QA_LogicCheck: 8,
};

const STATE_COLORS: Record<string, string> = {
  completed: '#22c55e',
  running: '#f59e0b',
  failed: '#ef4444',
  pending: '#6b7280',
  ready: '#3b82f6',
  degraded: '#eab308',
};

const STATE_LABELS: Record<string, string> = {
  completed: '✓完成',
  running: '◐运行中',
  failed: '✕失败',
  pending: '○等待',
  ready: '◉就绪',
  degraded: '⚠降级',
};

const AGENT_SHORT: Record<string, string> = {
  Orchestrator: 'Orch',
  SourceDiscovery: 'SrcDisc',
  Collector: 'Coll',
  DataEnricher: 'Enrich',
  FeatureAnalyzer: 'Feat',
  SentimentAnalyzer: 'Sent',
  PricingAnalyst: 'Price',
  TechStackAnalyzer: 'Tech',
  MarketPositionAnalyzer: 'MktPos',
  CrossReviewAgent: 'XReview',
  SWOTAnalyzer: 'SWOT',
  ReportGenerator: 'Report',
  QA_FactCheck: 'QA#1',
  QA_LogicCheck: 'QA#2',
};

interface DAGGraphProps {
  nodes: DAGNode[];
  width?: number;
  height?: number;
}

/* ---- helpers ---- */

interface LayoutNode {
  node: DAGNode;
  x: number;
  y: number;
}

function computeLayout(nodes: DAGNode[], w: number, h: number): LayoutNode[] {
  const layers = new Map<number, DAGNode[]>();
  for (const n of nodes) {
    const l = LAYER_MAP[n.agent_type] ?? 3;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)!.push(n);
  }

  const maxLayer = Math.max(...layers.keys(), 8);
  const lh = (h - 60) / (maxLayer + 1);
  const result: LayoutNode[] = [];

  for (const [layer, layerNodes] of layers) {
    const y = 30 + layer * lh;
    const lw = w - 80;
    layerNodes.forEach((n, i) => {
      const x = 40 + (lw / (layerNodes.length + 1)) * (i + 1);
      result.push({ node: n, x, y });
    });
  }
  return result;
}

function buildEdgePaths(layout: LayoutNode[]): { sourceId: string; targetId: string; d: string }[] {
  const map = new Map(layout.map(l => [l.node.node_id, { x: l.x, y: l.y }]));
  const edges: { sourceId: string; targetId: string; d: string }[] = [];
  for (const ln of layout) {
    for (const depId of ln.node.depends_on) {
      const src = map.get(depId);
      if (!src) continue;
      const tgt = { x: ln.x, y: ln.y };
      const mx = (src.x + tgt.x) / 2;
      const d = `M${src.x},${src.y + 10} C${mx},${src.y + 10} ${mx},${tgt.y - 10} ${tgt.x},${tgt.y - 10}`;
      edges.push({ sourceId: depId, targetId: ln.node.node_id, d });
    }
  }
  return edges;
}

/* ---- component ---- */

export default function DAGGraph({ nodes, width = 800, height = 600 }: DAGGraphProps) {
  const layout = useMemo(() => computeLayout(nodes, width, height), [nodes, width, height]);
  const edgePaths = useMemo(() => buildEdgePaths(layout), [layout]);

  if (nodes.length === 0) {
    return (
      <svg width={width} height={height} className="bg-gray-900/50 rounded-lg border border-gray-800">
        <text x={width / 2} y={height / 2} textAnchor="middle" fill="#6b7280" fontSize={12} fontFamily="monospace">
          DAG 节点为空 — 等待分析流程规划完成...
        </text>
      </svg>
    );
  }

  return (
    <svg width={width} height={height} className="bg-gray-900/50 rounded-lg border border-gray-800 w-full" viewBox={`0 0 ${width} ${height}`}>
      {/* Layer labels on the left */}
      {['编排', '源发现', '采集', '富化', '分析', '互审', '综合', '撰写', 'QA'].map((label, i) => (
        <text key={i} x={4} y={30 + i * ((height - 60) / 9) + 4} fill="#374151" fontSize={8} fontFamily="monospace">
          {label}
        </text>
      ))}

      {/* Edges */}
      {edgePaths.map((e, i) => (
        <path key={i} d={e.d} fill="none" stroke="#374151" strokeWidth={1} />
      ))}

      {/* Nodes */}
      {layout.map(ln => {
        const color = STATE_COLORS[ln.node.state] || '#6b7280';
        const short = AGENT_SHORT[ln.node.agent_type] || ln.node.agent_type.slice(0, 6);
        const isRunning = ln.node.state === 'running';
        const isCompleted = ln.node.state === 'completed';
        return (
          <g key={ln.node.node_id} className="stagger-item animate-fadeSlideUp">
            {isCompleted && (
              <rect
                x={ln.x - 38} y={ln.y - 12}
                width={76} height={24} rx={4}
                fill="none" stroke="#22c55e" strokeWidth={1.5}
                className="animate-glowGreen"
              />
            )}
            <rect
              x={ln.x - 36} y={ln.y - 10}
              width={72} height={20} rx={4}
              fill="#111827" stroke={color} strokeWidth={1}
              className={isRunning ? 'animate-pulse' : ''}
              style={{ transition: 'stroke 0.4s ease' }}
            />
            <circle
              cx={ln.x - 28} cy={ln.y} r={3}
              fill={color}
              style={{ transition: 'fill 0.3s ease' }}
            />
            <text x={ln.x - 20} y={ln.y + 4} fill="#d1d5db" fontSize={9} fontFamily="monospace">
              {short}
            </text>
          </g>
        );
      })}

      {/* Legend */}
      <g transform={`translate(${width - 130}, ${height - 110})`}>
        <rect x={0} y={0} width={120} height={100} rx={4} fill="#111827" stroke="#374151" strokeWidth={0.5} />
        {Object.entries(STATE_LABELS).map(([state, label], i) => (
          <g key={state} transform={`translate(8, ${12 + i * 16})`}>
            <circle cx={4} cy={0} r={3} fill={STATE_COLORS[state]} />
            <text x={12} y={4} fill="#9ca3af" fontSize={9} fontFamily="monospace">{label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
