import { useMemo } from 'react';
import type { DAGNode } from '../types';

/* ---- layer layout: 按 node_id 分层 ---- */

const NODE_LAYER_MAP: Record<string, number> = {
  collector: 1,
  feature_analysis: 2,
  sentiment_analysis: 2,
  pricing_analysis: 2,
  techstack_analysis: 2,
  market_position: 2,
  cross_review: 3,
  report: 4,
  qa: 5,
};

const STATE_COLORS: Record<string, string> = {
  completed: '#15803d',
  running: '#d97706',
  failed: '#b91c1c',
  pending: '#6b7280',
  ready: '#1d4ed8',
  degraded: '#ca8a04',
};

const STATE_LABELS: Record<string, string> = {
  completed: '✓完成',
  running: '◐运行中',
  failed: '✕失败',
  pending: '○等待',
  ready: '◉就绪',
  degraded: '⚠降级',
};

const NODE_SHORT: Record<string, string> = {
  collector: '采集',
  feature_analysis: '功能',
  sentiment_analysis: '口碑',
  pricing_analysis: '定价',
  techstack_analysis: '技术',
  market_position: '定位',
  cross_review: '互审',
  report: '报告',
  qa: '质检',
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
    const l = NODE_LAYER_MAP[n.node_id] ?? 3;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)!.push(n);
  }

  const maxLayer = Math.max(...layers.keys(), 5);
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
      <svg width={width} height={height} className="rounded-lg border border-slate-200 bg-white">
        <text x={width / 2} y={height / 2} textAnchor="middle" fill="#64748b" fontSize={12}>
          DAG 节点为空 — 等待分析流程规划完成...
        </text>
      </svg>
    );
  }

  const layerLabels = ['编排', '采集', '分析', '审查', '撰写', '质检'];

  return (
    <svg width={width} height={height} className="w-full rounded-lg border border-slate-200 bg-white" viewBox={`0 0 ${width} ${height}`}>
      {/* Layer labels on the left */}
      {layerLabels.map((label, i) => (
        <text key={i} x={4} y={30 + i * ((height - 60) / 6) + 4} fill="#94a3b8" fontSize={8}>
          {label}
        </text>
      ))}

      {/* Edges */}
      {edgePaths.map((e, i) => (
        <path key={i} d={e.d} fill="none" stroke="#cbd5e1" strokeWidth={1.2} />
      ))}

      {/* Nodes */}
      {layout.map(ln => {
        const color = STATE_COLORS[ln.node.state] || '#6b7280';
        const short = NODE_SHORT[ln.node.node_id] || ln.node.agent_type.slice(0, 6);
        const isRunning = ln.node.state === 'running';
        const isCompleted = ln.node.state === 'completed';
        return (
          <g key={ln.node.node_id} className="stagger-item animate-fadeSlideUp">
            {isCompleted && (
              <rect
                x={ln.x - 38} y={ln.y - 12}
                width={76} height={24} rx={4}
                fill="none" stroke="#15803d" strokeWidth={1.5}
                className="animate-glowGreen"
              />
            )}
            <rect
              x={ln.x - 36} y={ln.y - 10}
              width={72} height={20} rx={4}
              fill="#ffffff" stroke={color} strokeWidth={1}
              className={isRunning ? 'animate-pulse' : ''}
              style={{ transition: 'stroke 0.4s ease' }}
            />
            <circle
              cx={ln.x - 28} cy={ln.y} r={3}
              fill={color}
              style={{ transition: 'fill 0.3s ease' }}
            />
            <text x={ln.x - 20} y={ln.y + 4} fill="#334155" fontSize={9} fontFamily="monospace">
              {short}
            </text>
          </g>
        );
      })}

      {/* Legend */}
      <g transform={`translate(${width - 130}, ${height - 110})`}>
        <rect x={0} y={0} width={120} height={100} rx={4} fill="#ffffff" stroke="#cbd5e1" strokeWidth={0.5} />
        {Object.entries(STATE_LABELS).map(([state, label], i) => (
          <g key={state} transform={`translate(8, ${12 + i * 16})`}>
            <circle cx={4} cy={0} r={3} fill={STATE_COLORS[state]} />
            <text x={12} y={4} fill="#475569" fontSize={9}>{label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
