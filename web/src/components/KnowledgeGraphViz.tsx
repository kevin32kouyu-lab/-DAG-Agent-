import { useMemo, useRef, useEffect, useCallback } from 'react';
// @ts-ignore
import ForceGraph2D from 'react-force-graph-2d';

export interface KNode {
  id: string;
  label: string;
  layer: number;
  nodeType: string;
  product?: string;
}

export interface KEdge {
  source: string;
  target: string;
}

interface Props {
  nodes: KNode[];
  edges: KEdge[];
  width?: number;
  height?: number;
}

const LAYER_COLORS: Record<number, string> = {
  1: '#3b82f6',
  2: '#8b5cf6',
  3: '#10b981',
};

const LAYER_LABELS: Record<number, string> = {
  1: 'L1 原始数据',
  2: 'L2 分析层',
  3: 'L3 报告层',
};

export default function KnowledgeGraphViz({ nodes, edges, width = 800, height = 550 }: Props) {
  const fgRef = useRef<any>(null);

  // Pre-compute layer-based positions for a clear left-to-right flow
  const graphData = useMemo(() => {
    if (nodes.length === 0) return { nodes: [], links: [] };

    // Group by layer
    const byLayer: Record<number, KNode[]> = { 1: [], 2: [], 3: [] };
    nodes.forEach(n => {
      const l = n.layer >= 1 && n.layer <= 3 ? n.layer : 2;
      byLayer[l].push(n);
    });

    // Assign positions: Layer 1=left, Layer 2=middle, Layer 3=right
    const positionedNodes = nodes.map(n => {
      const layerNodes = byLayer[n.layer] || [n];
      const idx = layerNodes.indexOf(n);
      const total = layerNodes.length;
      // Spread nodes vertically within each layer
      const colX = (n.layer / 4) * (width * 0.9) + width * 0.05;
      const spacing = Math.min((height - 80) / Math.max(total, 1), 30);
      const colY = 40 + (idx + 0.5) * spacing + (Math.random() - 0.5) * spacing * 0.5;

      return {
        ...n,
        val: n.layer === 3 ? 2.5 : n.layer === 2 ? 2 : 1.5,
        color: LAYER_COLORS[n.layer] || '#6b7280',
        fx: colX,
        fy: colY,
      };
    });

    return {
      nodes: positionedNodes,
      links: edges.map(e => ({ source: e.source, target: e.target })),
    };
  }, [nodes, edges, width, height]);

  // Zoom to fit on data change
  useEffect(() => {
    if (fgRef.current && nodes.length > 0) {
      setTimeout(() => fgRef.current?.zoomToFit(300, 40), 600);
    }
  }, [nodes.length]);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const size = (node.val || 2) * (3.5 / globalScale);
    const color = node.color || '#6b7280';

    // Glow
    ctx.beginPath();
    ctx.arc(node.x, node.y, size * 1.8, 0, 2 * Math.PI);
    ctx.fillStyle = color + '20';
    ctx.fill();

    // Node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#ffffff88';
    ctx.lineWidth = 1 / globalScale;
    ctx.stroke();

    // Label — show for larger scales
    if (globalScale > 1.5) {
      const label = (node.label || node.id || '').slice(0, 12);
      ctx.font = `${Math.max(9, 10 / globalScale)}px "Inter", system-ui, sans-serif`;
      ctx.fillStyle = '#444651';
      ctx.textAlign = 'center';
      ctx.fillText(label, node.x, node.y + size + 7 / globalScale);

      // Sub-label: node type
      if (globalScale > 2.5) {
        ctx.font = `${Math.max(7, 8 / globalScale)}px "JetBrains Mono", monospace`;
        ctx.fillStyle = '#94a3b8';
        ctx.fillText(node.nodeType || '', node.x, node.y + size + 16 / globalScale);
      }
    }
  }, []);

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-border-subtle bg-surface" style={{ width, height }}>
        <div className="text-center text-sm text-on-surface-variant/60">
          <span className="material-symbols-outlined text-4xl mb-3 block opacity-30">hub</span>
          <p>等待知识图谱构建...</p>
          <p className="text-xs mt-1 opacity-50">Agent 生成的节点将在此实时展示</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border-subtle bg-surface overflow-hidden relative" style={{ width, height }}>
      {/* Layer labels */}
      <div className="absolute top-3 left-0 right-0 flex justify-around px-4 z-10 pointer-events-none">
        {[1, 2, 3].map(l => (
          <div key={l} className="text-center">
            <span className="rounded-full px-2.5 py-0.5 text-[10px] font-medium font-mono"
              style={{ background: LAYER_COLORS[l] + '20', color: LAYER_COLORS[l] }}>
              {LAYER_LABELS[l]}
            </span>
          </div>
        ))}
      </div>

      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        nodeCanvasObject={paintNode}
        linkColor={() => 'rgba(148,163,184,0.25)'}
        linkWidth={0.6}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={1.5}
        linkDirectionalParticleColor={() => '#cbd5e1'}
        linkDirectionalParticleSpeed={0.004}
        cooldownTicks={50}
        d3AlphaDecay={0.05}
        d3VelocityDecay={0.4}
        enableNodeHover={true}
        nodeLabel={(node: any) =>
          `${node.nodeType} · Layer ${node.layer}${node.product ? ' · ' + node.product : ''}\n${(node.label || '').slice(0, 60)}`
        }
        onNodeClick={(node: any) => {
          // Briefly un-fix to allow dragging, then re-fix
          if (fgRef.current && node.fx !== undefined) {
            node.fx = undefined; node.fy = undefined;
            fgRef.current.d3ReheatSimulation();
            setTimeout(() => {
              node.fx = (node.layer / 4) * (width * 0.9) + width * 0.05;
              node.fy = node.y;
            }, 2000);
          }
        }}
      />
    </div>
  );
}
