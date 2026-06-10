import { useState, useEffect, useRef, useCallback } from 'react';
import type { AgentType, NodeState, WSEvent, DAGNode } from '../types';

/**
 * Demo 模拟模式 —— 用 JS 定时器驱动进度动画，零后端调用。
 *
 * 用法: Monitor 页检测到 demo=true 时，用此 hook 替代 useWebSocket。
 * 在 ~15 秒内模拟 6 个 DAG 节点的完整执行流程。
 */

const SIMULATION_SPEED = 1; // 倍速 (1 = 实时)

export interface DemoSimResult {
  events: WSEvent[];
  connectionStatus: 'connected';
  send: () => void;
}

const NODE_CONFIGS: Record<string, { agent_type: AgentType; depends_on: string[] }> = {
  intent:             { agent_type: 'Orchestrator',     depends_on: [] },
  collector:          { agent_type: 'Collector',        depends_on: ['intent'] },
  enricher:           { agent_type: 'Collector',        depends_on: ['collector'] },
  feature_analysis:   { agent_type: 'Analyst',          depends_on: ['enricher'] },
  pricing_analysis:   { agent_type: 'Analyst',          depends_on: ['enricher'] },
  sentiment_analysis: { agent_type: 'Analyst',          depends_on: ['enricher'] },
  market_position:    { agent_type: 'Analyst',          depends_on: ['enricher'] },
  cross_review:       { agent_type: 'Analyst',          depends_on: ['feature_analysis','pricing_analysis','sentiment_analysis','market_position'] },
  report:             { agent_type: 'ReportGenerator',   depends_on: ['cross_review'] },
  qa_fact:            { agent_type: 'QA',                depends_on: ['report'] },
  qa_logic:           { agent_type: 'QA',                depends_on: ['qa_fact'] },
};

type TimelineEntry = { ms: number; event: WSEvent };

function buildTimeline(taskId: string): TimelineEntry[] {
  const t: TimelineEntry[] = [];
  const speed = SIMULATION_SPEED;
  const nodeIds = Object.keys(NODE_CONFIGS);

  // t=0: dag_created
  const dagNodes: DAGNode[] = nodeIds.map(nid => ({
    node_id: nid,
    agent_type: NODE_CONFIGS[nid].agent_type,
    depends_on: NODE_CONFIGS[nid].depends_on,
    state: 'pending' as NodeState,
  }));

  t.push({
    ms: 0,
    event: {
      event: 'dag_created',
      task_id: taskId,
      nodes: dagNodes.map(n => ({ ...n, state: n.state as NodeState })),
      total_cost: 0,
      total_tokens: 0,
      pages_collected: 0,
    },
  });

  // Phase 1: Intent (t=500 → 2000)
  t.push({ ms: 500 / speed,  event: stateChange(taskId, 'intent', 'Orchestrator', 'running', []) });
  t.push({ ms: 2000 / speed, event: stateChange(taskId, 'intent', 'Orchestrator', 'completed', []) });
  // Phase 2: Collector → Enricher
  t.push({ ms: 2500 / speed, event: stateChange(taskId, 'collector', 'Collector', 'running', ['intent']) });
  t.push({ ms: 5000 / speed, event: stateChange(taskId, 'collector', 'Collector', 'completed', ['intent']) });
  t.push({ ms: 5500 / speed, event: stateChange(taskId, 'enricher', 'Collector', 'running', ['collector']) });
  t.push({ ms: 7500 / speed, event: stateChange(taskId, 'enricher', 'Collector', 'completed', ['collector']) });
  // Phase 3: 4 Analysts (parallel, staggered)
  t.push({ ms: 8000 / speed,  event: stateChange(taskId, 'feature_analysis',   'Analyst', 'running', ['enricher']) });
  t.push({ ms: 8500 / speed,  event: stateChange(taskId, 'pricing_analysis',   'Analyst', 'running', ['enricher']) });
  t.push({ ms: 9000 / speed,  event: stateChange(taskId, 'sentiment_analysis', 'Analyst', 'running', ['enricher']) });
  t.push({ ms: 9500 / speed,  event: stateChange(taskId, 'market_position',    'Analyst', 'running', ['enricher']) });
  t.push({ ms: 12000 / speed, event: stateChange(taskId, 'feature_analysis',   'Analyst', 'completed', ['enricher']) });
  t.push({ ms: 13000 / speed, event: stateChange(taskId, 'pricing_analysis',   'Analyst', 'completed', ['enricher']) });
  t.push({ ms: 13500 / speed, event: stateChange(taskId, 'sentiment_analysis', 'Analyst', 'completed', ['enricher']) });
  t.push({ ms: 14500 / speed, event: stateChange(taskId, 'market_position',    'Analyst', 'completed', ['enricher']) });
  // Phase 4: CrossReview → Report
  t.push({ ms: 15000 / speed, event: stateChange(taskId, 'cross_review', 'Analyst', 'running', ['feature_analysis','pricing_analysis','sentiment_analysis','market_position']) });
  t.push({ ms: 17500 / speed, event: stateChange(taskId, 'cross_review', 'Analyst', 'completed', ['feature_analysis','pricing_analysis','sentiment_analysis','market_position']) });
  t.push({ ms: 18000 / speed, event: stateChange(taskId, 'report', 'ReportGenerator', 'running', ['cross_review']) });
  t.push({ ms: 22000 / speed, event: stateChange(taskId, 'report', 'ReportGenerator', 'completed', ['cross_review']) });
  // Phase 5: QA Fact → QA Logic
  t.push({ ms: 22500 / speed, event: stateChange(taskId, 'qa_fact', 'QA', 'running', ['report']) });
  t.push({ ms: 25000 / speed, event: stateChange(taskId, 'qa_fact', 'QA', 'completed', ['report']) });
  t.push({ ms: 25500 / speed, event: stateChange(taskId, 'qa_logic', 'QA', 'running', ['qa_fact']) });
  t.push({ ms: 28000 / speed, event: stateChange(taskId, 'qa_logic', 'QA', 'completed', ['qa_fact']) });

  // Log events
  const logEvents = [
    { ms: 800 / speed,  agent: 'Orchestrator', step: 1, phase: '观察' as const, summary: '解析任务目标，识别竞品列表和分析维度' },
    { ms: 1200 / speed, agent: 'Orchestrator', step: 1, phase: '思考' as const, summary: '规划工作流：采集→清洗→分析→审查→报告→校核' },
    { ms: 1600 / speed, agent: 'Orchestrator', step: 2, phase: '执行' as const, summary: '调度采集 Agent，下发搜索关键词和 URL 种子' },
    { ms: 3000 / speed, agent: 'Collector', step: 1, phase: '观察' as const, summary: '接收任务目标，解析竞品列表' },
    { ms: 3500 / speed, agent: 'Collector', step: 1, phase: '思考' as const, summary: '规划搜索策略：官网、定价页、用户评价、新闻报道' },
    { ms: 4000 / speed, agent: 'Collector', step: 2, phase: '执行' as const, summary: '多引擎搜索：Serper + 百度 + 搜狗 + DuckDuckGo' },
    { ms: 4500 / speed, agent: 'Collector', step: 3, phase: '执行' as const, summary: '写入图谱：来源链接 × 2,056' },
    { ms: 6000 / speed, agent: 'Collector', step: 4, phase: '执行' as const, summary: '数据清洗：去重、过滤低质量源、补充元数据' },
    { ms: 7000 / speed, agent: 'Collector', step: 5, phase: '执行' as const, summary: '数据清洗完成，标记可信度评分' },
    { ms: 8500 / speed, agent: 'Analyst', step: 1, phase: '观察' as const, summary: '从图谱读取清洗后的数据源节点' },
    { ms: 9000 / speed, agent: 'Analyst', step: 1, phase: '思考' as const, summary: '识别通用能力维度，逐一评估差异化' },
    { ms: 10000 / speed, agent: 'Analyst', step: 2, phase: '执行' as const, summary: '抓取产品官网功能页面，提取能力信息' },
    { ms: 11500 / speed, agent: 'Analyst', step: 3, phase: '执行' as const, summary: '写入图谱：分析节点 × 30+' },
    { ms: 15500 / speed, agent: 'Analyst', step: 1, phase: '观察' as const, summary: '交叉审查：比对四个分析维度结论一致性' },
    { ms: 16500 / speed, agent: 'Analyst', step: 2, phase: '思考' as const, summary: '检测矛盾：功能分析 vs 用户口碑，标记不一致项' },
    { ms: 17200 / speed, agent: 'Analyst', step: 3, phase: '执行' as const, summary: '交叉审查完成，写入审查标记节点' },
    { ms: 18500 / speed, agent: 'ReportGenerator', step: 1, phase: '观察' as const, summary: '读取全部 L2 分析节点和交叉审查结果' },
    { ms: 19500 / speed, agent: 'ReportGenerator', step: 2, phase: '思考' as const, summary: '综合分析，生成 SWOT 矩阵和五维度评分' },
    { ms: 21000 / speed, agent: 'ReportGenerator', step: 3, phase: '执行' as const, summary: '写入图谱：报告章节 × 5' },
    { ms: 23000 / speed, agent: 'QA', step: 1, phase: '观察' as const, summary: '读取报告内容，逐条追溯证据链' },
    { ms: 24000 / speed, agent: 'QA', step: 2, phase: '思考' as const, summary: '事实校验：检查每个结论是否有充分证据支撑' },
    { ms: 24800 / speed, agent: 'QA', step: 3, phase: '执行' as const, summary: '事实校验通过 ✓' },
    { ms: 26000 / speed, agent: 'QA', step: 1, phase: '观察' as const, summary: '读取报告和事实校验结果' },
    { ms: 27000 / speed, agent: 'QA', step: 2, phase: '思考' as const, summary: '逻辑校验：检查内部一致性、推理缺口、遗漏反方观点' },
    { ms: 27800 / speed, agent: 'QA', step: 3, phase: '执行' as const, summary: '逻辑校验通过，报告就绪 ✓' },
  ];

  for (const le of logEvents) {
    t.push({
      ms: le.ms,
      event: {
        event: 'agent_log',
        task_id: taskId,
        node_id: le.agent === 'Collector' ? 'collector' : le.agent === 'ReportGenerator' ? 'report' : 'feature_analysis',
        agent_type: le.agent as AgentType,
        step: le.step,
        phase: le.phase,
        summary: le.summary,
      },
    });
  }

  // Sort by time
  t.sort((a, b) => a.ms - b.ms);
  return t;
}

function stateChange(taskId: string, nodeId: string, agentType: AgentType, state: NodeState, depends_on: string[]): WSEvent {
  return {
    event: state === 'completed' ? 'node_completed' : 'node_state_change',
    task_id: taskId,
    node_id: nodeId,
    agent_type: agentType,
    state,
    depends_on,
  } as WSEvent;
}

export function useDemoSimulation(taskId: string): DemoSimResult {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const timeline = useRef(buildTimeline(taskId));
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startTime = useRef(Date.now());

  useEffect(() => {
    if (!taskId) return;

    startTime.current = Date.now();
    const tl = timeline.current;

    // Schedule each event
    const timeouts: ReturnType<typeof setTimeout>[] = [];

    for (const entry of tl) {
      const timeout = setTimeout(() => {
        setEvents(prev => [...prev, entry.event]);
      }, entry.ms);
      timeouts.push(timeout);
    }

    return () => {
      timeouts.forEach(clearTimeout);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [taskId]);

  const send = useCallback(() => {}, []);

  return { events, connectionStatus: 'connected', send };
}
