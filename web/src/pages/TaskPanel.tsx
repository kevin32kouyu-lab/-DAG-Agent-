// 这个页面是项目首页，负责展示预设 Demo、自定义分析入口和最近任务。

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import SchemaBuilder, { type SchemaBuilderHandle } from '../components/SchemaBuilder';
import StatusBadge from '../components/StatusBadge';
import Spinner from '../components/Spinner';
import DemoStageStrip from '../components/DemoStageStrip';
import { useTaskContext } from '../hooks/useTaskContext';
import { useToast } from '../hooks/useToast';
import { DEMO_PRESETS, TECH_HIGHLIGHTS, type DemoPreset } from '../demoContent';
import type { HistoryTask } from '../types';

function loadHistory(): HistoryTask[] {
  try {
    const raw = localStorage.getItem('compagent_history');
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

const DEFAULT_HISTORY: HistoryTask[] = [
  { id: 'task_3_a1b2c3d4', time: '05-14 14:30', targets: 'Notion, Confluence, Linear', targetsArr: ['Notion', 'Confluence', 'Linear'], status: 'completed', duration: '4m32s' },
  { id: 'task_3_e5f6g7h8', time: '05-14 15:02', targets: 'Figma, Sketch', targetsArr: ['Figma', 'Sketch'], status: 'running', duration: '2m15s' },
  { id: 'task_3_i9j0k1l2', time: '05-13 18:45', targets: 'Slack, Teams', targetsArr: ['Slack', 'Teams'], status: 'failed', duration: '-' },
];

function loadInitialHistory(): HistoryTask[] {
  const existing = loadHistory();
  if (existing.length > 0) return existing;
  try {
    localStorage.setItem('compagent_history', JSON.stringify(DEFAULT_HISTORY));
  } catch {
    // localStorage 不可用时仍展示默认演示记录。
  }
  return DEFAULT_HISTORY;
}

function nowStr(): string {
  const d = new Date();
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function createTempTaskId(targetCount: number): string {
  return `task_${targetCount}_${Date.now().toString(36)}`;
}

const INDUSTRIES = [
  { value: 'saas', label: 'SaaS' },
  { value: 'app', label: 'App / 互联网产品' },
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

interface StartOptions {
  industry?: string;
  depth?: string;
  benchmark?: string;
}

export default function TaskPanel() {
  const [targets, setTargets] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [industry, setIndustry] = useState('saas');
  const [depth, setDepth] = useState('standard');
  const [execMode, setExecMode] = useState('auto');
  const [modelPref, setModelPref] = useState('auto');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<HistoryTask[]>(loadInitialHistory);
  const [error, setError] = useState('');
  const [shakeSubmit, setShakeSubmit] = useState(false);

  const schemaRef = useRef<SchemaBuilderHandle>(null);
  const navigate = useNavigate();
  const { setActiveTaskId, addToHistory } = useTaskContext();
  const { toast } = useToast();

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<HistoryTask[]>).detail;
      if (detail) setHistory(detail);
    };
    window.addEventListener('historyUpdated', handler);
    return () => window.removeEventListener('historyUpdated', handler);
  }, []);

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

  const startAnalysis = async (overrideTargets?: string[], options: StartOptions = {}) => {
    const t = overrideTargets ?? targets;
    if (t.length === 0) {
      setShakeSubmit(true);
      setTimeout(() => setShakeSubmit(false), 400);
      return;
    }
    setError('');
    setLoading(true);

    const selectedIndustry = options.industry ?? industry;
    const selectedDepth = options.depth ?? depth;
    const selectedBenchmark = options.benchmark ?? schemaRef.current?.getBenchmark() ?? null;
    const tempId = createTempTaskId(t.length);
    const tempEntry: HistoryTask = {
      id: tempId,
      time: nowStr(),
      targets: t.join(', '),
      targetsArr: t,
      status: 'planning',
      duration: '...',
    };
    const optimisticHistory = [tempEntry, ...history.filter(h => h.id !== tempId)];
    setHistory(optimisticHistory);
    localStorage.setItem('compagent_history', JSON.stringify(optimisticHistory));

    const schema = schemaRef.current;
    const payload: Record<string, unknown> = {
      targets: t,
      industry: selectedIndustry,
      execution_mode: execMode,
      collection_depth: selectedDepth,
      model_preference: modelPref,
      dimensions: schema?.getDimensions() ?? [],
      exclude_dimensions: [],
      focus_points: schema?.getFocusPoints() ?? {},
      dimension_weights: schema?.getWeights() ?? {},
      source_preferences: schema?.getSourcePrefs() ?? {},
      benchmark_product: selectedBenchmark,
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
        const entry: HistoryTask = {
          id: data.task_id,
          time: nowStr(),
          targets: t.join(', '),
          targetsArr: t,
          status: 'planning',
          duration: '...',
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
        const reverted = optimisticHistory.filter(h => h.id !== tempId);
        setHistory(reverted);
        localStorage.setItem('compagent_history', JSON.stringify(reverted));
        setError(txt || '创建任务失败');
        toast(txt || '创建任务失败', 'error');
        setLoading(false);
      }
    } catch {
      setActiveTaskId(tempId);
      addToHistory(tempEntry);
      toast('后端未响应，使用模拟模式', 'warning');
      setLoading(false);
      navigate(`/task/${tempId}/monitor`);
    }
  };

  const startPreset = (preset: DemoPreset) => {
    const presetTargets = [...preset.targets];
    setIndustry(preset.industry);
    setDepth(preset.depth);
    setTargets(presetTargets);
    setInputValue('');
    startAnalysis(presetTargets, {
      industry: preset.industry,
      depth: preset.depth,
      benchmark: preset.benchmark,
    });
  };

  const rerunTask = (task: HistoryTask) => {
    setActiveTaskId(task.id);
    if (task.targetsArr && task.targetsArr.length > 0) {
      startAnalysis(task.targetsArr);
    } else {
      const parsed = task.targets.split(',').map(s => s.trim()).filter(Boolean);
      startAnalysis(parsed);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 animate-pageEnter">
      <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold text-teal-700">竞品分析 Demo</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-normal text-slate-950">
              自动生成竞品分析报告
            </h1>
            <p className="mt-4 text-base leading-7 text-slate-600">
              输入一个产品，系统会自动找资料、整理证据，并生成带图表和来源的竞品分析报告。
            </p>
          </div>
          <DemoStageStrip />
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-950">选择预设案例</h2>
          <p className="mt-1 text-sm text-slate-500">先用稳定案例查看完整效果，再尝试自由输入。</p>
          <div className="mt-4 space-y-3">
            {DEMO_PRESETS.map(preset => (
              <button
                key={preset.id}
                onClick={() => startPreset(preset)}
                className="w-full rounded-md border border-slate-200 bg-slate-50 p-4 text-left transition-colors hover:border-teal-600 hover:bg-teal-50"
                aria-label={`使用 ${preset.title}案例`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-950">{preset.title}</div>
                    <div className="mt-1 text-xs font-medium text-teal-700">{preset.category}</div>
                  </div>
                  <span className="text-xs text-slate-500">{preset.targets.length} 个产品</span>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">{preset.description}</p>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-slate-950">自定义分析</h2>
            <p className="mt-1 text-sm text-slate-500">适合已有明确竞品名单的场景。</p>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs text-slate-500">行业模板</label>
              <select
                value={industry}
                onChange={e => setIndustry(e.target.value)}
                className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 outline-none transition-colors focus:border-teal-700"
              >
                {INDUSTRIES.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">分析深度</label>
              <div className="flex overflow-hidden rounded border border-slate-300">
                {DEPTH_OPTIONS.map((d, i) => (
                  <button
                    key={d.value}
                    onClick={() => setDepth(d.value)}
                    className={`flex-1 border-r px-2 py-1.5 text-xs transition-all active:scale-95 ${
                      depth === d.value
                        ? 'bg-teal-50 text-teal-800'
                        : 'bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                    } ${i === DEPTH_OPTIONS.length - 1 ? 'border-r-0' : 'border-slate-300'}`}
                    title={d.desc}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">执行模式</label>
              <div className="flex overflow-hidden rounded border border-slate-300">
                <button
                  onClick={() => setExecMode('auto')}
                  className={`flex-1 border-r border-slate-300 px-2 py-1.5 text-xs transition-all active:scale-95 ${
                    execMode === 'auto' ? 'bg-teal-50 text-teal-800' : 'bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  自动
                </button>
                <button
                  onClick={() => setExecMode('review')}
                  className={`flex-1 px-2 py-1.5 text-xs transition-all active:scale-95 ${
                    execMode === 'review' ? 'bg-teal-50 text-teal-800' : 'bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  审核
                </button>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">模型偏好</label>
              <select
                value={modelPref}
                onChange={e => setModelPref(e.target.value)}
                className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 outline-none transition-colors focus:border-teal-700"
              >
                {MODEL_OPTIONS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
          </div>

          <div className="mt-4">
            <label className="mb-1 block text-xs text-slate-500">
              目标产品
              {targets.length === 0 && <span className="ml-1 text-slate-400">（必填）</span>}
            </label>
            <div className={`flex min-h-[42px] flex-wrap items-center gap-2 rounded border bg-white p-3 transition-colors ${
              targets.length === 0 ? 'border-amber-300' : 'border-slate-300'
            }`}>
              {targets.map(t => (
                <span key={t} className="inline-flex items-center gap-1 rounded border border-teal-200 bg-teal-50 px-2.5 py-1 text-sm text-teal-800 animate-scaleIn">
                  {t}
                  <button onClick={() => removeTarget(t)} className="ml-0.5 text-slate-400 transition-colors hover:text-red-600 active:scale-90">&times;</button>
                </span>
              ))}
              <input
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={targets.length === 0 ? '输入产品名，回车添加...' : '+ 添加更多'}
                className="min-w-[160px] flex-1 border-none bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400"
              />
            </div>
          </div>

          <div className="mt-4">
            <SchemaBuilder ref={schemaRef} targets={targets.length > 0 ? targets : ['Notion']} />
          </div>

          {error && (
            <div className="mt-4 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700 animate-fadeIn">{error}</div>
          )}

          <button
            onClick={() => startAnalysis()}
            disabled={targets.length === 0 || loading}
            className={`mt-4 inline-flex w-full items-center justify-center gap-2 rounded bg-slate-950 py-2.5 font-medium text-white transition-all hover:bg-slate-800 active:scale-[0.98] disabled:bg-slate-200 disabled:text-slate-500 disabled:active:scale-100 ${shakeSubmit ? 'animate-shake' : ''}`}
          >
            {loading && <Spinner size="sm" />}
            {loading ? '正在生成 DAG...' : targets.length === 0 ? '请添加至少一个目标产品' : '开始分析'}
          </button>
        </div>

        <aside className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-base font-semibold text-slate-950">为什么可信</h2>
            <div className="mt-4 space-y-4">
              {TECH_HIGHLIGHTS.map(item => (
                <div key={item.title}>
                  <div className="text-sm font-semibold text-slate-950">{item.title}</div>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{item.description}</p>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">最近分析</h2>
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
                <th className="px-4 py-2 text-left font-medium">时间</th>
                <th className="px-4 py-2 text-left font-medium">目标产品</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium">耗时</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {history.map(task => (
                <tr key={task.id} className="border-b border-slate-100 transition-colors hover:bg-slate-50">
                  <td className="px-4 py-2.5 text-xs text-slate-500">{task.time}</td>
                  <td className="px-4 py-2.5 text-slate-700">{task.targets}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={task.status} />
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">{task.duration}</td>
                  <td className="space-x-2 px-4 py-2.5">
                    <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/report`); }}
                      className="inline-block text-xs text-teal-700 transition-colors hover:text-teal-900 active:scale-95">查看报告</button>
                    <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/trace`); }}
                      className="inline-block text-xs text-slate-500 transition-colors hover:text-slate-900 active:scale-95">溯源</button>
                    {task.status === 'running' && (
                      <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/monitor`); }}
                        className="inline-block text-xs text-amber-700 transition-colors hover:text-amber-900 active:scale-95">实时监控</button>
                    )}
                    {task.status === 'failed' && (
                      <button onClick={() => rerunTask(task)}
                        className="inline-block text-xs text-red-700 transition-colors hover:text-red-900 active:scale-95">重新运行</button>
                    )}
                    {task.status === 'completed' && (
                      <button onClick={() => { setActiveTaskId(task.id); navigate(`/task/${task.id}/monitor`); }}
                        className="inline-block text-xs text-slate-500 transition-colors hover:text-slate-900 active:scale-95">查看日志</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
