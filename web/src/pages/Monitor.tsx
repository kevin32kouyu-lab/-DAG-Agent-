import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useWebSocket } from '../hooks/useWebSocket';
import { useTaskContext } from '../context/TaskContext';
import { useToast } from '../components/Toast';
import AgentCard from '../components/AgentCard';
import DAGGraph from '../components/DAGGraph';
import PipelineSkeleton from '../components/PipelineSkeleton';
import type { AgentState, AgentGroup, DAGNode, WSEvent, NodeState } from '../types';

/* ---- agent grouping ---- */

const GROUP_CONFIG: AgentGroup[] = [
  { role: 'Orchestrator', agentTypes: ['Orchestrator'], variant: 'single', description: '任务指挥官 — 生成 DAG' },
  { role: 'Source Discovery', agentTypes: ['SourceDiscovery'], variant: 'single', description: '信息源侦察 — 搜索可信 URL' },
  { role: 'Collector Group', agentTypes: ['Collector'], variant: 'collection', description: '并行采集 — 网页抓取' },
  { role: 'Data Enricher', agentTypes: ['DataEnricher'], variant: 'single', description: '语境补充 — 关联第三方数据' },
  { role: 'Analysis Layer', agentTypes: ['FeatureAnalyzer', 'SentimentAnalyzer', 'PricingAnalyst', 'TechStackAnalyzer', 'MarketPosition'], variant: 'analysis', description: '分析 Agent — 等待采集完成' },
  { role: 'Cross-Review', agentTypes: ['CrossReview'], variant: 'single', description: '水平交叉审查 — 检测分析矛盾' },
  { role: 'SWOT Synthesizer', agentTypes: ['SWOTSynthesizer'], variant: 'swot', description: '战略综合 — 聚合所有分析' },
  { role: 'Writer', agentTypes: ['Writer'], variant: 'single', description: '报告撰写 — 生成 Markdown' },
  { role: 'QA Group', agentTypes: ['QAFactCheck', 'QALogicCheck'], variant: 'qa', description: '双 QA 审查 — 事实 + 逻辑' },
];

function groupAgents(agents: Map<string, AgentState>): { group: AgentGroup; agents: AgentState[] }[] {
  return GROUP_CONFIG.map(g => ({
    group: g,
    agents: Array.from(agents.values()).filter(a => g.agentTypes.includes(a.agent_type)),
  })).filter(g => g.agents.length > 0);
}

/* ---- component ---- */

export default function Monitor() {
  const { id } = useParams<{ id: string }>();
  const { events, connectionStatus } = useWebSocket(id || '');
  const { setWsConnected, updateHistoryTask } = useTaskContext();
  const { toast } = useToast();
  const [agents, setAgents] = useState<Map<string, AgentState>>(new Map());
  const [totalCost, setTotalCost] = useState(0);
  const [totalTokens, setTotalTokens] = useState(0);
  const [pagesCollected, setPagesCollected] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [dagNodes, setDagNodes] = useState<DAGNode[]>([]);
  const [phase, setPhase] = useState<'connecting' | 'planning' | 'executing' | 'done'>('connecting');
  const [showLogs, setShowLogs] = useState(false);

  /* sync WS status to context + cleanup on unmount */
  useEffect(() => {
    setWsConnected(connectionStatus === 'connected');
    if (connectionStatus === 'connected' && phase === 'connecting') {
      setPhase('planning');
    }
    return () => { setWsConnected(false); };
  }, [connectionStatus, setWsConnected, phase]);

  const processedCount = useRef(0);

  /* process incoming WebSocket events incrementally */
  useEffect(() => {
    const newEvents = events.slice(processedCount.current);
    if (newEvents.length === 0) return;

    for (const raw of newEvents) {
      const evt = raw as WSEvent;
      if (!evt?.event) continue;

      switch (evt.event) {
        case 'node_state_change':
        case 'node_completed':
          setAgents(prev => {
            const next = new Map(prev);
            const existing = next.get(evt.node_id);
            next.set(evt.node_id, {
              node_id: evt.node_id,
              agent_type: evt.agent_type,
              state: evt.state as NodeState,
              progress: evt.state === 'completed' ? 100 : evt.state === 'running' ? (existing?.progress ?? 50) : existing?.progress,
              outputSummary: existing?.outputSummary,
              details: existing?.details,
              duration: existing?.duration,
            });
            return next;
          });
          /* track DAG nodes for graph */
          setDagNodes(prev => {
            const exists = prev.find(n => n.node_id === evt.node_id);
            const deps = (evt as { depends_on?: string[] }).depends_on ?? [];
            if (exists) {
              return prev.map(n => n.node_id === evt.node_id ? { ...n, state: evt.state as NodeState, depends_on: deps } : n);
            }
            return [...prev, { node_id: evt.node_id, agent_type: evt.agent_type, depends_on: deps, state: evt.state as NodeState }];
          });
          break;

        case 'dag_state':
          /* full state snapshot on (re)connect */
          {
            const nodes = (evt as { nodes?: Array<{ node_id: string; agent_type: string; state: NodeState; depends_on: string[] }> }).nodes ?? [];
            if (nodes.length === 0) {
              setPhase('planning');
              break;
            }
            setPhase('executing');
            const agentMap = new Map<string, AgentState>();
            const dagList: DAGNode[] = [];
            for (const n of nodes) {
              agentMap.set(n.node_id, {
                node_id: n.node_id,
                agent_type: n.agent_type,
                state: n.state,
                progress: n.state === 'completed' ? 100 : 0,
              });
              dagList.push({
                node_id: n.node_id,
                agent_type: n.agent_type,
                depends_on: n.depends_on,
                state: n.state,
              });
            }
            setAgents(agentMap);
            setDagNodes(dagList);
            setTotalCost((evt as { total_cost?: number }).total_cost ?? 0);
            setTotalTokens((evt as { total_tokens?: number }).total_tokens ?? 0);
            setPagesCollected((evt as { pages_collected?: number }).pages_collected ?? 0);
          }
          break;

        case 'dag_created': {
          const nodes = (evt as { nodes?: Array<{ node_id: string; agent_type: string; state: NodeState; depends_on: string[] }> }).nodes ?? [];
          const agentMap = new Map<string, AgentState>();
          const dagList: DAGNode[] = [];
          for (const n of nodes) {
            agentMap.set(n.node_id, {
              node_id: n.node_id,
              agent_type: n.agent_type,
              state: n.state,
              progress: 0,
            });
            dagList.push({
              node_id: n.node_id,
              agent_type: n.agent_type,
              depends_on: n.depends_on,
              state: n.state,
            });
          }
          setAgents(agentMap);
          setDagNodes(dagList);
          setTotalCost((evt as { total_cost?: number }).total_cost ?? 0);
          setTotalTokens((evt as { total_tokens?: number }).total_tokens ?? 0);
          setPagesCollected((evt as { pages_collected?: number }).pages_collected ?? 0);
          setPhase('executing');
          break;
        }

        case 'dag_failed':
          setPhase('done');
          toast(`DAG 规划失败: ${(evt as { error?: string }).error || '未知错误'}`, 'error');
          break;

        case 'node_failed':
          setAgents(prev => {
            const next = new Map(prev);
            const cur = next.get(evt.node_id);
            next.set(evt.node_id, {
              node_id: evt.node_id, agent_type: evt.agent_type,
              state: 'failed',
              outputSummary: cur?.outputSummary,
              details: 'Permanent failure (retries exhausted)',
            });
            return next;
          });
          break;

        case 'agent_log':
          setLogs(prev => {
            const entry = `[${evt.agent_type}] Step ${evt.step} ${evt.phase}: ${evt.summary}`;
            return [...prev.slice(-199), entry];
          });
          break;

        case 'cost_update':
          setTotalCost(evt.total_cost);
          setTotalTokens((evt as unknown as { total_tokens?: number }).total_tokens ?? totalTokens);
          setPagesCollected((evt as unknown as { pages_collected?: number }).pages_collected ?? pagesCollected);
          break;

        case 'qa_reject':
          for (const nid of evt.affected_nodes) {
            setAgents(prev => {
              const next = new Map(prev);
              const cur = next.get(nid);
              if (cur) next.set(nid, { ...cur, state: 'degraded', details: `QA 拒绝: ${evt.reasons.join(', ')}` });
              return next;
            });
          }
          break;
      }
    }

    processedCount.current = events.length;
  }, [events]);

  /* grouping */
  const groups = useMemo(() => groupAgents(agents), [agents]);
  const agentList = Array.from(agents.values());
  const completed = agentList.filter(a => a.state === 'completed').length;
  const running = agentList.filter(a => a.state === 'running').length;
  const failed = agentList.filter(a => a.state === 'failed').length;

  /* update history when task finishes */
  useEffect(() => {
    if (agentList.length === 0 || !id) return;
    const allDone = agentList.every(a => a.state === 'completed');
    const anyFailed = agentList.some(a => a.state === 'failed');
    if (allDone) {
      updateHistoryTask(id, { status: 'completed', duration: '已完成' });
      toast('任务已全部完成', 'success');
    } else if (anyFailed) {
      updateHistoryTask(id, { status: 'failed', duration: '失败' });
      toast('部分节点执行失败', 'error');
    }
  }, [completed, failed, agentList.length, id, updateHistoryTask, toast]);

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6 animate-pageEnter">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Agent 协作状态</h1>
          <p className="text-gray-500 text-sm font-mono">任务: {id}</p>
        </div>
        <div className="flex gap-4 text-sm font-mono">
          <span className="text-green-400">{completed} 完成</span>
          <span className="text-amber-400">{running} 运行中</span>
          {failed > 0 && <span className="text-red-400">{failed} 失败</span>}
          <span className="text-gray-500">{agentList.length - completed - running - failed} 等待</span>
          <span className={`w-2 h-2 rounded-full self-center ${connectionStatus === 'connected' ? 'bg-green-500' : connectionStatus === 'connecting' ? 'bg-amber-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-xs text-gray-600 self-center">
            {connectionStatus === 'connected' ? 'WS 已连接' : connectionStatus === 'connecting' ? '连接中...' : 'WS 断开'}
          </span>
        </div>
      </div>

      {/* Agent Group Panels */}
      {groups.map(({ group, agents: groupAgents }) => (
        <div key={group.role} className="space-y-2">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide">{group.role}</h3>
            {group.agentTypes.length > 1 && (
              <span className="text-xs text-gray-600 font-mono">(×{groupAgents.length})</span>
            )}
            <span className="text-xs text-gray-600">— {group.description}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {groupAgents.map(a => (
              <AgentCard
                key={a.node_id}
                agent={a}
                variant={['single', 'swot'].includes(group.variant) ? 'detailed' : 'compact'}
              />
            ))}
          </div>
        </div>
      ))}

      {/* Planning / Connecting state */}
      {phase === 'planning' && agentList.length === 0 && (
        <PipelineSkeleton />
      )}

      {phase === 'connecting' && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center text-gray-600 font-mono text-sm">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse mr-2" />
          正在连接 WebSocket...
        </div>
      )}

      {/* Log stream */}
      {logs.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="w-full px-4 py-2 flex items-center justify-between text-xs text-gray-500 font-mono hover:bg-gray-800/50"
          >
            <span>实时日志流 ({logs.length} 条)</span>
            <span>{showLogs ? '▴ 收起' : '▾ 展开'}</span>
          </button>
          {showLogs && (
            <div className="max-h-48 overflow-auto border-t border-gray-800 p-2 space-y-0.5 font-mono text-xs">
              {logs.map((l, i) => (
                <div key={i} className="text-gray-500 hover:text-gray-300 truncate">{l}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* DAG Graph */}
      <DAGGraph nodes={dagNodes} />

      {/* Bottom status bar */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center justify-between font-mono text-sm">
        <span className="text-gray-500">资源消耗</span>
        <div className="flex gap-6">
          <span className="text-gray-400">Token: {totalTokens > 0 ? totalTokens.toLocaleString() : '—'}</span>
          <span className="text-gray-300">成本: ${totalCost.toFixed(4)}</span>
          <span className="text-gray-400">采集: {pagesCollected > 0 ? `${pagesCollected} 页` : '—'}</span>
        </div>
      </div>
    </div>
  );
}
