import { useMemo, useRef, useEffect, useCallback } from 'react';
// @ts-ignore
import ForceGraph2D from 'react-force-graph-2d';

interface FlowNode {
  id: string;
  label: string;
  /** 'agent' | 'kg' */
  kind: 'agent' | 'kg';
  /** agent type or node type */
  subType: string;
  layer?: number;
  state?: string;
}

interface FlowEdge {
  source: string;
  target: string;
  /** 'pipeline' | 'reads' | 'writes' */
  relation: 'pipeline' | 'reads' | 'writes';
}

interface Props { width: number; height: number; }

const AGENT_COLORS: Record<string, string> = {
  Collector: '#3b82f6',
  'Feature Analyst': '#8b5cf6',
  'Pricing Analyst': '#f59e0b',
  'Sentiment Analyst': '#ec4899',
  'Market Analyst': '#06b6d4',
  'Report Generator': '#10b981',
};

const KG_LAYER_COLORS: Record<number, string> = {
  1: '#93c5fd', 2: '#a78bfa', 3: '#6ee7b7',
};

// Build the process flow graph: agents + sample KG nodes + edges
// This simulates the demo flow for 飞书 vs 钉钉 vs 企业微信
function buildProcessFlow(): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const nodes: FlowNode[] = [];
  const edges: FlowEdge[] = [];

  // ── Agent nodes (top row) ──
  const agents = [
    { id: 'agent_collector', label: 'Collector', subType: 'Collector', y: 80 },
    { id: 'agent_feature', label: 'Feature 分析', subType: 'Feature Analyst', y: 80 },
    { id: 'agent_pricing', label: 'Pricing 分析', subType: 'Pricing Analyst', y: 200 },
    { id: 'agent_sentiment', label: 'Sentiment 分析', subType: 'Sentiment Analyst', y: 320 },
    { id: 'agent_market', label: 'Market 分析', subType: 'Market Analyst', y: 440 },
    { id: 'agent_writer', label: 'Report Writer', subType: 'Report Generator', y: 80 },
  ];

  agents.forEach((a, i) => {
    nodes.push({
      id: a.id, label: a.label, kind: 'agent', subType: a.subType,
      layer: 0,
    });
  });

  // Pipeline edges: Collector → all analysts → Writer
  edges.push({ source: 'agent_collector', target: 'agent_feature', relation: 'pipeline' });
  edges.push({ source: 'agent_collector', target: 'agent_pricing', relation: 'pipeline' });
  edges.push({ source: 'agent_collector', target: 'agent_sentiment', relation: 'pipeline' });
  edges.push({ source: 'agent_collector', target: 'agent_market', relation: 'pipeline' });
  edges.push({ source: 'agent_feature', target: 'agent_writer', relation: 'pipeline' });
  edges.push({ source: 'agent_pricing', target: 'agent_writer', relation: 'pipeline' });
  edges.push({ source: 'agent_sentiment', target: 'agent_writer', relation: 'pipeline' });
  edges.push({ source: 'agent_market', target: 'agent_writer', relation: 'pipeline' });

  // ── KG nodes (grouped by layer, positioned below agents) ──
  const kgNodes = {
    collector: [
      { id: 'kg_serper', label: 'Serper 搜索结果', layer: 1 },
      { id: 'kg_ddgs', label: 'DDGS 搜索结果', layer: 1 },
      { id: 'kg_sogou', label: '搜狗 搜索结果', layer: 1 },
      { id: 'kg_sourceinfo', label: 'SourceInfo 节点 ×574', layer: 1 },
      { id: 'kg_webpage', label: 'WebPage 节点 ×112', layer: 1 },
    ],
    feature: [
      { id: 'kg_feature1', label: '实时协作编辑 Feature', layer: 2 },
      { id: 'kg_feature2', label: 'AI 智能助手 Feature', layer: 2 },
      { id: 'kg_feature3', label: '开放 API Feature', layer: 2 },
      { id: 'kg_feature4', label: '企业安全管理 Feature', layer: 2 },
    ],
    pricing: [
      { id: 'kg_pricing1', label: '飞书 定价模型', layer: 2 },
      { id: 'kg_pricing2', label: '钉钉 定价模型', layer: 2 },
      { id: 'kg_pricing3', label: '企业微信 定价模型', layer: 2 },
    ],
    sentiment: [
      { id: 'kg_sent1', label: '定价满意度 Sentiment', layer: 2 },
      { id: 'kg_sent2', label: '功能体验 Sentiment', layer: 2 },
      { id: 'kg_sent3', label: '客服支持 Sentiment', layer: 2 },
    ],
    market: [
      { id: 'kg_market1', label: '飞书 市场定位', layer: 2 },
      { id: 'kg_market2', label: '钉钉 市场定位', layer: 2 },
      { id: 'kg_market3', label: '企业微信 市场定位', layer: 2 },
    ],
    writer: [
      { id: 'kg_swot', label: 'SWOT 分析 ×3', layer: 3 },
      { id: 'kg_scoring', label: '维度评分 ×15', layer: 3 },
      { id: 'kg_report', label: '报告章节 ×5', layer: 3 },
    ],
  };

  const kgEntries: [string, { id: string; label: string; layer: number }[]][] = [
    ['agent_collector', kgNodes.collector],
    ['agent_feature', kgNodes.feature],
    ['agent_pricing', kgNodes.pricing],
    ['agent_sentiment', kgNodes.sentiment],
    ['agent_market', kgNodes.market],
    ['agent_writer', kgNodes.writer],
  ];

  kgEntries.forEach(([agentId, kNodes]) => {
    kNodes.forEach(kn => {
      nodes.push({
        id: kn.id, label: kn.label, kind: 'kg',
        subType: kn.layer === 1 ? 'SourceInfo' : kn.layer === 2 ? 'Analysis' : 'Report',
        layer: kn.layer,
      });
      // Write edge: agent → kg node
      edges.push({ source: agentId, target: kn.id, relation: 'writes' });
    });
  });

  // Add cross-agent read edges: analysts read collector's KG nodes
  edges.push({ source: 'kg_sourceinfo', target: 'agent_feature', relation: 'reads' });
  edges.push({ source: 'kg_sourceinfo', target: 'agent_pricing', relation: 'reads' });
  edges.push({ source: 'kg_sourceinfo', target: 'agent_sentiment', relation: 'reads' });
  edges.push({ source: 'kg_sourceinfo', target: 'agent_market', relation: 'reads' });
  edges.push({ source: 'agent_writer', target: 'kg_feature1', relation: 'reads' });

  return { nodes, edges };
}

export default function ProcessFlowViz({ width, height }: Props) {
  const fgRef = useRef<any>(null);

  const graphData = useMemo(() => {
    const { nodes, edges } = buildProcessFlow();

    // Position nodes: agents left-to-right across top, KG below each agent
    const agentOrder = ['agent_collector', 'agent_feature', 'agent_pricing', 'agent_sentiment', 'agent_market', 'agent_writer'];
    const positioned = nodes.map(n => {
      let fx: number, fy: number;

      if (n.kind === 'agent') {
        const idx = agentOrder.indexOf(n.id);
        fx = width * 0.1 + (width * 0.8 * idx) / Math.max(agentOrder.length - 1, 1);
        fy = height * 0.1;
      } else {
        // KG nodes positioned below their parent agent
        const parentAgent = n.id.startsWith('kg_') ?
          agentOrder.find(a => {
            if (n.id.includes('sourceinfo') || n.id.includes('webpage') || n.id.includes('serper') || n.id.includes('ddgs') || n.id.includes('sogou')) return a === 'agent_collector';
            if (n.id.includes('feature')) return a === 'agent_feature';
            if (n.id.includes('pricing')) return a === 'agent_pricing';
            if (n.id.includes('sent')) return a === 'agent_sentiment';
            if (n.id.includes('market')) return a === 'agent_market';
            if (n.id.includes('swot') || n.id.includes('scoring') || n.id.includes('report')) return a === 'agent_writer';
            return false;
          }) : 'agent_collector';

        const agentIdx = agentOrder.indexOf(parentAgent || 'agent_collector');
        const agentX = width * 0.1 + (width * 0.8 * agentIdx) / Math.max(agentOrder.length - 1, 1);
        fx = agentX + (Math.random() - 0.5) * 100;
        fy = height * 0.3 + (n.layer || 1) * (height * 0.15) + Math.random() * 40;
      }

      return { ...n, fx, fy };
    });

    return {
      nodes: positioned,
      links: edges.map(e => ({ source: e.source, target: e.target, relation: e.relation })),
    };
  }, [width, height]);

  useEffect(() => {
    if (fgRef.current) setTimeout(() => fgRef.current?.zoomToFit(200, 30), 800);
  }, [width, height]);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    if (node.kind === 'agent') {
      // Agent node: rounded rectangle
      const w = 90 / globalScale;
      const h = 28 / globalScale;
      const color = AGENT_COLORS[node.subType] || '#64748b';

      ctx.shadowColor = color + '60';
      ctx.shadowBlur = 8 / globalScale;
      ctx.fillStyle = color;
      ctx.beginPath();
      const r = 6 / globalScale;
      ctx.moveTo(node.x - w / 2 + r, node.y - h / 2);
      ctx.lineTo(node.x + w / 2 - r, node.y - h / 2);
      ctx.quadraticCurveTo(node.x + w / 2, node.y - h / 2, node.x + w / 2, node.y - h / 2 + r);
      ctx.lineTo(node.x + w / 2, node.y + h / 2 - r);
      ctx.quadraticCurveTo(node.x + w / 2, node.y + h / 2, node.x + w / 2 - r, node.y + h / 2);
      ctx.lineTo(node.x - w / 2 + r, node.y + h / 2);
      ctx.quadraticCurveTo(node.x - w / 2, node.y + h / 2, node.x - w / 2, node.y + h / 2 - r);
      ctx.lineTo(node.x - w / 2, node.y - h / 2 + r);
      ctx.quadraticCurveTo(node.x - w / 2, node.y - h / 2, node.x - w / 2 + r, node.y - h / 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Label
      ctx.font = `bold ${Math.max(9, 10 / globalScale)}px "Inter", system-ui, sans-serif`;
      ctx.fillStyle = '#fff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, node.x, node.y);
    } else {
      // KG node: circle
      const size = (node.layer === 3 ? 5 : 4) / globalScale;
      const color = KG_LAYER_COLORS[node.layer] || '#94a3b8';

      ctx.beginPath();
      ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#ffffff88';
      ctx.lineWidth = 0.8 / globalScale;
      ctx.stroke();

      if (globalScale > 1.2) {
        ctx.font = `${Math.max(7, 8 / globalScale)}px system-ui, sans-serif`;
        ctx.fillStyle = '#475569';
        ctx.textAlign = 'center';
        ctx.fillText((node.label || '').slice(0, 16), node.x, node.y + size + 8 / globalScale);
      }
    }
  }, []);

  const linkColor = useCallback((link: any) => {
    if (link.relation === 'pipeline') return '#64748b80';
    if (link.relation === 'writes') return '#3b82f660';
    return '#10b98160';
  }, []);

  return (
    <div className="rounded-xl border border-border-subtle bg-surface overflow-hidden relative" style={{ width, height }}>
      <div className="absolute top-3 left-4 z-10 flex items-center gap-4 text-[10px] pointer-events-none">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{background:'#3b82f6'}} /> Agent</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{background:'#93c5fd'}} /> L1 数据</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{background:'#a78bfa'}} /> L2 分析</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{background:'#6ee7b7'}} /> L3 报告</span>
        <span className="text-on-surface-variant/50 ml-2">—— pipeline →</span>
        <span className="text-blue-500/50">—— 写入 →</span>
        <span className="text-green-500/50">—— 读取 →</span>
      </div>

      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        nodeCanvasObject={paintNode}
        linkColor={linkColor}
        linkWidth={(l: any) => l.relation === 'pipeline' ? 1.2 : 0.5}
        linkDirectionalParticles={(l: any) => l.relation === 'pipeline' ? 2 : 1}
        linkDirectionalParticleWidth={1.5}
        linkDirectionalParticleColor={(l: any) => l.relation === 'pipeline' ? '#94a3b8' : l.relation === 'writes' ? '#60a5fa' : '#34d399'}
        linkDirectionalParticleSpeed={0.005}
        cooldownTicks={30}
        d3AlphaDecay={0.03}
        d3VelocityDecay={0.3}
        enableNodeHover={true}
        nodeLabel={(n: any) => n.kind === 'agent' ? `🤖 ${n.label}\n${n.subType}` : `📊 ${n.label}\nLayer ${n.layer} · ${n.subType}`}
      />
    </div>
  );
}
