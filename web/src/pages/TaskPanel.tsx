import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

// Mock history data for initial display
const MOCK_HISTORY = [
  { id: 'task_3_a1b2c3d4', time: '05-14 14:30', targets: 'Notion, Confluence, Linear', status: 'completed', duration: '4m32s' },
  { id: 'task_3_e5f6g7h8', time: '05-14 15:02', targets: 'Figma, Sketch', status: 'running', duration: '2m15s' },
  { id: 'task_3_i9j0k1l2', time: '05-13 18:45', targets: 'Slack, Teams', status: 'failed', duration: '-' },
];

const STATUS_MAP: Record<string, string> = {
  completed: '✓ 完成', running: '◐ 运行中', failed: '✕ 失败'
};

function StatusBadge({ status, label }: { status: string; label: string }) {
  const colors: Record<string, string> = {
    completed: 'text-green-400 bg-green-400/10 border-green-400/30',
    running: 'text-amber-400 bg-amber-400/10 border-amber-400/30',
    failed: 'text-red-400 bg-red-400/10 border-red-400/30',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-mono ${colors[status] || ''}`}>
      {status === 'running' && <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />}
      {label}
    </span>
  );
}

export default function TaskPanel() {
  const [targets, setTargets] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const addTarget = (name: string) => {
    if (name.trim() && !targets.includes(name.trim())) {
      setTargets([...targets, name.trim()]);
    }
    setInputValue('');
  };

  const removeTarget = (name: string) => setTargets(targets.filter(t => t !== name));

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTarget(inputValue);
    }
  };

  const startAnalysis = async () => {
    if (targets.length === 0) return;
    setLoading(true);
    try {
      const resp = await fetch('/api/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targets, industry: 'saas' }),
      });
      if (resp.ok) {
        const data = await resp.json();
        navigate(`/task/${data.task_id}/monitor`);
      }
    } catch (_err) { /* backend may not be running */ }
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">竞品分析 Agent 协作系统</h1>
        <p className="text-gray-500 text-sm mt-1 font-mono">Multi-Agent Competitive Intelligence</p>
      </div>

      {/* Task Creation Card */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
        <div className="flex items-center gap-2 text-gray-300 font-medium">
          <span className="text-cyan-400">▸</span> 新建分析
        </div>

        {/* Target input */}
        <div className="flex flex-wrap gap-2 p-3 bg-gray-950 border border-gray-700 rounded min-h-[42px] items-center">
          {targets.map(t => (
            <span key={t} className="inline-flex items-center gap-1 px-2.5 py-1 bg-cyan-900/30 border border-cyan-700/50 rounded text-sm text-cyan-300 font-mono">
              {t}
              <button onClick={() => removeTarget(t)} className="text-gray-500 hover:text-red-400 ml-0.5">&times;</button>
            </span>
          ))}
          <input
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={targets.length === 0 ? "输入产品名，回车添加..." : ""}
            className="flex-1 min-w-[160px] bg-transparent border-none outline-none text-gray-200 text-sm placeholder-gray-600"
          />
        </div>

        <button
          onClick={startAnalysis}
          disabled={targets.length === 0 || loading}
          className="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded font-medium transition-colors"
        >
          {loading ? '正在生成 DAG...' : '开始分析'}
        </button>
      </div>

      {/* History */}
      <div>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">历史任务</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 font-mono text-xs">
                <th className="px-4 py-2 text-left font-medium">时间</th>
                <th className="px-4 py-2 text-left font-medium">目标产品</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium">耗时</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_HISTORY.map(task => (
                <tr key={task.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">{task.time}</td>
                  <td className="px-4 py-2.5 text-gray-300">{task.targets}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={task.status} label={STATUS_MAP[task.status]} />
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono text-xs">{task.duration}</td>
                  <td className="px-4 py-2.5 space-x-2">
                    <button onClick={() => navigate(`/task/${task.id}/report`)} className="text-cyan-400 hover:text-cyan-300 text-xs">查看报告</button>
                    <button onClick={() => navigate(`/task/${task.id}/trace`)} className="text-gray-500 hover:text-gray-300 text-xs">溯源</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
