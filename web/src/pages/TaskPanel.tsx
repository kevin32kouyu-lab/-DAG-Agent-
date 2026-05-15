import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import SchemaBuilder, { type SchemaBuilderHandle } from '../components/SchemaBuilder';
import StatusBadge from '../components/StatusBadge';
import Spinner from '../components/Spinner';
import { useTaskContext } from '../context/TaskContext';
import { useToast } from '../components/Toast';
import type { HistoryTask } from '../types';

/* ---- helpers ---- */

function loadHistory(): HistoryTask[] {
  try {
    const raw = localStorage.getItem('compagent_history');
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function nowStr(): string {
  const d = new Date();
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/* ---- constants ---- */

const INDUSTRIES = [
  { value: 'saas', label: 'SaaS' },
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'fintech', label: 'Fintech' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'gaming', label: 'Gaming' },
];

const DEPTH_OPTIONS = [
  { value: 'shallow', label: '快速', desc: '仅官网+G2' },
  { value: 'standard', label: '标准', desc: '+社媒+新闻' },
  { value: 'deep', label: '深度', desc: '+第三方API' },
];

const MODEL_OPTIONS = [
  { value: 'auto', label: 'Auto (自动分配)' },
  { value: 'claude-opus-4-7', label: 'Claude Opus 4.7' },
  { value: 'kimi-k2', label: 'Kimi K2' },
  { value: 'qwen-plus', label: 'Qwen Plus' },
];

/* ---- component ---- */

export default function TaskPanel() {
  const [targets, setTargets] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [industry, setIndustry] = useState('saas');
  const [depth, setDepth] = useState('standard');
  const [execMode, setExecMode] = useState('auto');
  const [modelPref, setModelPref] = useState('auto');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<HistoryTask[]>(loadHistory);
  const [error, setError] = useState('');
  const [shakeSubmit, setShakeSubmit] = useState(false);

  const schemaRef = useRef<SchemaBuilderHandle>(null);
  const navigate = useNavigate();
  const { setActiveTaskId, addToHistory, updateHistoryTask } = useTaskContext();
  const { toast } = useToast();

  /* preserved mock history on first load */
  useEffect(() => {
    const existing = loadHistory();
    if (existing.length === 0) {
      const mock: HistoryTask[] = [
        { id: 'task_3_a1b2c3d4', time: '05-14 14:30', targets: 'Notion, Confluence, Linear', targetsArr: ['Notion', 'Confluence', 'Linear'], status: 'completed', duration: '4m32s' },
        { id: 'task_3_e5f6g7h8', time: '05-14 15:02', targets: 'Figma, Sketch', targetsArr: ['Figma', 'Sketch'], status: 'running', duration: '2m15s' },
        { id: 'task_3_i9j0k1l2', time: '05-13 18:45', targets: 'Slack, Teams', targetsArr: ['Slack', 'Teams'], status: 'failed', duration: '-' },
      ];
      setHistory(mock);
      localStorage.setItem('compagent_history', JSON.stringify(mock));
    }
  }, []);

  /* listen for cross-tab / cross-component history updates (e.g. from Monitor) */
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<HistoryTask[]>).detail;
      if (detail) setHistory(detail);
    };
    window.addEventListener('historyUpdated', handler);
    return () => window.removeEventListener('historyUpdated', handler);
  }, []);

  /* ---- target chips ---- */
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

  /* ---- start analysis ---- */
  const startAnalysis = async (overrideTargets?: string[]) => {
    const t = overrideTargets ?? targets;
    if (t.length === 0) {
      setShakeSubmit(true);
      setTimeout(() => setShakeSubmit(false), 400);
      return;
    }
    setError('');
    setLoading(true);

    // Optimistic: add pending entry to history immediately
    const tempId = `task_${t.length}_${Date.now().toString(36)}`;
    const tempEntry: HistoryTask = {
      id: tempId, time: nowStr(),
      targets: t.join(', '), targetsArr: t,
      status: 'planning', duration: '...',
    };
    const optimisticHistory = [tempEntry, ...history.filter(h => h.id !== tempId)];
    setHistory(optimisticHistory);
    localStorage.setItem('compagent_history', JSON.stringify(optimisticHistory));

    const schema = schemaRef.current;
    const payload: Record<string, unknown> = {
      targets: t,
      industry,
      execution_mode: execMode,
      collection_depth: depth,
      model_preference: modelPref,
      dimensions: schema?.getDimensions() ?? [],
      exclude_dimensions: [],
      focus_points: schema?.getFocusPoints() ?? {},
      dimension_weights: schema?.getWeights() ?? {},
      source_preferences: schema?.getSourcePrefs() ?? {},
      benchmark_product: schema?.getBenchmark() ?? null,
      report_audience: schema?.getAudience() ?? 'product_manager',
      report_sections: [],
      output_formats: schema?.getOutputFormats() ?? ['markdown'],
    };

    try {
      const resp = await fetch('/api/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (resp.ok) {
        const data = await resp.json();
        setActiveTaskId(data.task_id);
        // Replace temp entry with real one
        const entry: HistoryTask = {
          id: data.task_id, time: nowStr(),
          targets: t.join(', '), targetsArr: t,
          status: 'planning', duration: '...',
        };
        const updated = [entry, ...optimisticHistory.filter(h => h.id !== tempId)];
        setHistory(updated);
        localStorage.setItem('compagent_history', JSON.stringify(updated));
        addToHistory(entry);
        toast('任务已创建，正在规划分析流程...', 'success');
        setLoading(false);
        navigate(`/task/${data.task_id}/monitor`);
      } else {
        const txt = await resp.text();
        // Remove optimistic entry on failure
        const reverted = optimisticHistory.filter(h => h.id !== tempId);
        setHistory(reverted);
        localStorage.setItem('compagent_history', JSON.stringify(reverted));
        setError(txt || '创建任务失败');
        toast(txt || '创建任务失败', 'error');
        setLoading(false);
      }
    } catch (_err) {
      // Backend not running — keep optimistic entry and navigate with temp ID
      setActiveTaskId(tempId);
      addToHistory(tempEntry);
      toast('后端未响应，使用模拟模式', 'warning');
      setLoading(false);
      navigate(`/task/${tempId}/monitor`);
    }
  };

  const rerunTask = (task: HistoryTask) => {
    setActiveTaskId(task.id);
    if (task.targetsArr && task.targetsArr.length > 0) {
      startAnalysis(task.targetsArr);
    } else {
      // fallback: parse from comma-separated string
      const parsed = task.targets.split(',').map(s => s.trim()).filter(Boolean);
      startAnalysis(parsed);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8 animate-pageEnter">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">竞品分析 Agent 协作系统</h1>
        <p className="text-gray-500 text-sm mt-1 font-mono">Multi-Agent Competitive Intelligence</p>
      </div>

      {/* Task Creation Card */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
        <div className="flex items-center gap-2 text-gray-300 font-medium">
          <span className="text-cyan-400">&#9654;</span> 新建分析
        </div>

        {/* Row 1: industry + depth + mode + model */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">行业模板</label>
            <select value={industry} onChange={e => setIndustry(e.target.value)}
              className="w-full px-2 py-1.5 bg-gray-950 border border-gray-700 rounded text-sm text-gray-300 focus:border-cyan-600 outline-none transition-colors">
              {INDUSTRIES.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">分析深度</label>
            <div className="flex rounded border border-gray-700 overflow-hidden">
              {DEPTH_OPTIONS.map((d, i) => (
                <button key={d.value}
                  onClick={() => setDepth(d.value)}
                  className={`flex-1 px-2 py-1.5 text-xs transition-all active:scale-95 ${
                    depth === d.value
                      ? 'bg-cyan-900/40 text-cyan-300 border-r border-gray-700'
                      : 'bg-gray-950 text-gray-500 hover:text-gray-300 border-r border-gray-700'
                  } ${i === DEPTH_OPTIONS.length - 1 ? 'border-r-0' : ''}`}
                  title={d.desc}>
                  {d.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">执行模式</label>
            <div className="flex rounded border border-gray-700 overflow-hidden">
              <button onClick={() => setExecMode('auto')}
                className={`flex-1 px-2 py-1.5 text-xs transition-all active:scale-95 border-r border-gray-700 ${
                  execMode === 'auto' ? 'bg-cyan-900/40 text-cyan-300' : 'bg-gray-950 text-gray-500 hover:text-gray-300'}`}>
                自动
              </button>
              <button onClick={() => setExecMode('review')}
                className={`flex-1 px-2 py-1.5 text-xs transition-all active:scale-95 ${
                  execMode === 'review' ? 'bg-cyan-900/40 text-cyan-300' : 'bg-gray-950 text-gray-500 hover:text-gray-300'}`}>
                审核
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">模型偏好</label>
            <select value={modelPref} onChange={e => setModelPref(e.target.value)}
              className="w-full px-2 py-1.5 bg-gray-950 border border-gray-700 rounded text-sm text-gray-300 focus:border-cyan-600 outline-none transition-colors">
              {MODEL_OPTIONS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
        </div>

        {/* Target input */}
        <div>
          <label className="text-xs text-gray-500 block mb-1">
            目标产品
            {targets.length === 0 && <span className="text-gray-600 ml-1">（必填）</span>}
          </label>
          <div className={`flex flex-wrap gap-2 p-3 bg-gray-950 border border-gray-700 rounded min-h-[42px] items-center transition-colors ${
            targets.length === 0 ? 'border-amber-700/30' : ''
          }`}>
            {targets.map(t => (
              <span key={t} className="inline-flex items-center gap-1 px-2.5 py-1 bg-cyan-900/30 border border-cyan-700/50 rounded text-sm text-cyan-300 font-mono animate-scaleIn">
                {t}
                <button onClick={() => removeTarget(t)} className="text-gray-500 hover:text-red-400 ml-0.5 transition-colors active:scale-90">&times;</button>
              </span>
            ))}
            <input
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={targets.length === 0 ? "输入产品名，回车添加..." : "+ 添加更多"}
              className="flex-1 min-w-[160px] bg-transparent border-none outline-none text-gray-200 text-sm placeholder-gray-600"
            />
          </div>
        </div>

        {/* Schema Builder */}
        <SchemaBuilder ref={schemaRef} targets={targets.length > 0 ? targets : ['Notion']} />

        {/* Error */}
        {error && (
          <div className="bg-red-900/10 border border-red-800/30 rounded p-2 text-xs text-red-400 font-mono animate-fadeIn">{error}</div>
        )}

        {/* Submit */}
        <button
          onClick={() => startAnalysis()}
          disabled={targets.length === 0 || loading}
          className={`w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded font-medium transition-all active:scale-[0.98] disabled:active:scale-100 inline-flex items-center justify-center gap-2 ${shakeSubmit ? 'animate-shake' : ''}`}
        >
          {loading && <Spinner size="sm" />}
          {loading ? '正在生成 DAG...' : targets.length === 0 ? '请添加至少一个目标产品' : '开始分析'}
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
              {history.map(task => (
                <tr key={task.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                  <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">{task.time}</td>
                  <td className="px-4 py-2.5 text-gray-300">{task.targets}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={task.status} />
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono text-xs">{task.duration}</td>
                  <td className="px-4 py-2.5 space-x-2">
                    <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/report`); }}
                      className="text-cyan-400 hover:text-cyan-300 text-xs transition-colors active:scale-95 inline-block">查看报告</button>
                    <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/trace`); }}
                      className="text-gray-500 hover:text-gray-300 text-xs transition-colors active:scale-95 inline-block">溯源</button>
                    {task.status === 'running' && (
                      <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/monitor`); }}
                        className="text-amber-400 hover:text-amber-300 text-xs transition-colors active:scale-95 inline-block">实时监控</button>
                    )}
                    {task.status === 'failed' && (
                      <button onClick={() => rerunTask(task)}
                        className="text-red-400 hover:text-red-300 text-xs transition-colors active:scale-95 inline-block">重新运行</button>
                    )}
                    {task.status === 'completed' && (
                      <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/monitor`); }}
                        className="text-gray-500 hover:text-gray-300 text-xs transition-colors active:scale-95 inline-block">查看日志</button>
                    )}
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
