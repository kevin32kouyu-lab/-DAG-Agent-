import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTaskContext } from '../hooks/useTaskContext';
import { DEMO_PRESETS, TECH_HIGHLIGHTS, type DemoPreset } from '../demoContent';

function startDemo(preset: DemoPreset, setActiveTaskId: (id: string) => void, navigate: ReturnType<typeof useNavigate>) {
  const demoTaskId = `demo_${preset.id}`;
  setActiveTaskId(demoTaskId);
  navigate(`/task/${demoTaskId}/monitor?demo=true&task=${demoTaskId}`);
}

export default function TaskPanel() {
  const navigate = useNavigate();
  const { setActiveTaskId } = useTaskContext();
  const [targets, setTargets] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);

  const addTarget = (name: string) => {
    if (name.trim() && !targets.includes(name.trim())) setTargets([...targets, name.trim()]);
    setInputValue('');
  };

  const removeTarget = (name: string) => setTargets(targets.filter(t => t !== name));

  const handleCustomStart = async () => {
    if (targets.length === 0) return;
    setLoading(true);
    try {
      const resp = await fetch('/api/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targets, industry: 'saas', collection_depth: 'demo', planning_mode: 'template' }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setActiveTaskId(data.task_id);
        navigate(`/task/${data.task_id}/monitor`);
      }
    } catch { /* ignore */ }
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto px-8 py-10 animate-pageEnter">
      {/* Hero */}
      <div className="mb-10">
        <p className="text-xs font-semibold text-primary/70 mb-3">竞品分析 · Competitive Intelligence</p>
        <h1 className="font-headline text-4xl font-semibold tracking-tight text-on-surface leading-tight">
          自动生成竞品分析报告
        </h1>
        <p className="mt-4 text-base text-on-surface-variant leading-relaxed max-w-xl">
          输入产品名，AI Agent 协作系统自动收集资料、多维分析、生成带图表和来源追溯的竞品报告。
        </p>
      </div>

      {/* Demo presets */}
      <section className="mb-10">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">📦</span>
          <h2 className="font-headline text-lg font-semibold text-on-surface">预设案例</h2>
          <span className="rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[11px] font-medium text-amber-700">一键 Demo</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {DEMO_PRESETS.map(preset => (
            <button
              key={preset.id}
              onClick={() => startDemo(preset, setActiveTaskId, navigate)}
              className="group text-left rounded-xl border border-border-subtle bg-surface p-5 transition-all duration-200 hover:border-primary/30 hover:shadow-md hover:-translate-y-0.5 active:scale-[0.98]"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-headline text-base font-semibold text-on-surface group-hover:text-primary transition-colors">
                    {preset.title}
                  </div>
                  <div className="mt-1 text-xs font-medium text-primary/70">{preset.category}</div>
                </div>
                <span className="shrink-0 rounded-full bg-surface-container px-2.5 py-0.5 text-[11px] font-medium text-on-surface-variant">
                  {preset.targets.length} 产品
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{preset.description}</p>
            </button>
          ))}
        </div>
      </section>

      {/* Custom input */}
      <section className="rounded-xl border border-border-subtle bg-surface p-6">
        <h2 className="font-headline text-lg font-semibold text-on-surface mb-1">自定义分析</h2>
        <p className="text-sm text-on-surface-variant mb-5">输入竞品名单，启动 AI 分析引擎。</p>
        <div className="flex flex-wrap items-center gap-2 min-h-[44px] rounded-lg border border-border-subtle bg-bg p-3 mb-4">
          {targets.map(t => (
            <span key={t} className="inline-flex items-center gap-1 rounded-md bg-primary-container/20 border border-primary/20 px-2.5 py-1 text-sm font-medium text-primary animate-scaleIn">
              {t}
              <button onClick={() => removeTarget(t)} className="ml-1 text-on-surface-variant/40 hover:text-confidence-low transition-colors">&times;</button>
            </span>
          ))}
          <input
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTarget(inputValue); } }}
            placeholder={targets.length === 0 ? '输入产品名，回车添加...' : '+ 添加更多'}
            className="flex-1 min-w-[160px] bg-transparent border-none text-sm text-on-surface outline-none placeholder:text-on-surface-variant/50"
          />
        </div>
        <button
          onClick={handleCustomStart}
          disabled={targets.length === 0 || loading}
          className="w-full rounded-lg bg-primary py-2.5 text-sm font-semibold text-white transition-all hover:bg-primary/90 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? '创建任务中...' : targets.length === 0 ? '添加至少一个产品' : `开始分析 (${targets.length} 个产品)`}
        </button>
      </section>

      {/* Tech highlights */}
      <section className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {TECH_HIGHLIGHTS.map(item => (
          <div key={item.title} className="rounded-lg border border-border-subtle bg-surface p-4">
            <div className="font-headline text-sm font-semibold text-on-surface">{item.title}</div>
            <p className="mt-1.5 text-xs text-on-surface-variant leading-relaxed">{item.description}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
