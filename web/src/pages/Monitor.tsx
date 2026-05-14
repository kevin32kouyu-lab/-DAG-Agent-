import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useWebSocket } from '../hooks/useWebSocket';

interface AgentState {
  node_id: string;
  agent_type: string;
  state: string;
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-500',
  running: 'bg-amber-500 animate-pulse',
  failed: 'bg-red-500',
  pending: 'bg-gray-600',
  ready: 'bg-blue-500',
  degraded: 'bg-yellow-600',
};

export default function Monitor() {
  const { id } = useParams<{ id: string }>();
  const events = useWebSocket(id || '');
  const [agents, setAgents] = useState<Map<string, AgentState>>(new Map());
  const [totalCost, setTotalCost] = useState(0);

  useEffect(() => {
    // Process incoming events
    for (const evt of events) {
      if (evt.event === 'node_state_change' || evt.event === 'node_completed') {
        setAgents(prev => {
          const next = new Map(prev);
          next.set(evt.node_id, { node_id: evt.node_id, agent_type: evt.agent_type, state: evt.state });
          return next;
        });
      }
      if (evt.event === 'cost_update') {
        setTotalCost(evt.total_cost);
      }
    }
  }, [events]);

  const agentList = Array.from(agents.values());
  const completed = agentList.filter(a => a.state === 'completed').length;
  const running = agentList.filter(a => a.state === 'running').length;
  const failed = agentList.filter(a => a.state === 'failed').length;

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header with stats */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Agent 协作状态</h1>
          <p className="text-gray-500 text-sm font-mono">任务: {id}</p>
        </div>
        <div className="flex gap-4 text-sm font-mono">
          <span className="text-green-400">{completed} 完成</span>
          <span className="text-amber-400">{running} 运行中</span>
          {failed > 0 && <span className="text-red-400">{failed} 失败</span>}
          <span className="text-gray-500">{agentList.length - completed - running - failed} 等待</span>
        </div>
      </div>

      {/* Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {agentList.map(agent => (
          <div key={agent.node_id} className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[agent.state] || 'bg-gray-600'}`} />
              <span className="text-xs text-gray-500 font-mono uppercase">{agent.state}</span>
            </div>
            <div className="text-sm font-medium text-gray-200">{agent.agent_type}</div>
            <div className="text-xs text-gray-500 font-mono mt-1">{agent.node_id}</div>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {agentList.length === 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center text-gray-600 font-mono text-sm">
          等待 Agent 启动... (WebSocket 已连接)
        </div>
      )}

      {/* Cost bar */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center justify-between font-mono text-sm">
        <span className="text-gray-500">资源消耗</span>
        <span className="text-gray-300">成本: ${totalCost.toFixed(4)}</span>
      </div>
    </div>
  );
}
