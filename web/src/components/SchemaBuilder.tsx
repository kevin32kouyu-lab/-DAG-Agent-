// 这个组件提供高级分析维度、信息源和报告输出配置。

import { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import type { AnalysisDimension, SourcePreferences } from '../types';

/* ---- static preset data ---- */

interface PresetDim {
  name: string;
  description: string;
  agent_type: string;
  node_types: string[];
  available: boolean;
}

const PRESET_DIMENSIONS: PresetDim[] = [
  { name: '功能矩阵对比', description: '功能拆解与矩阵对比', agent_type: 'FeatureAnalyzer', node_types: ['FeatureNode', 'FeatureMatrix'], available: true },
  { name: '定价策略分析', description: '定价模型拆解、性价比评分', agent_type: 'PricingAnalyst', node_types: ['PricingData', 'PricingModel'], available: true },
  { name: '用户口碑分析', description: '用户评价情感分析、口碑趋势', agent_type: 'SentimentAnalyzer', node_types: ['SentimentNode', 'ReviewEntry'], available: true },
  { name: '技术栈推断', description: '推断产品技术栈、架构特征', agent_type: 'TechStackAnalyzer', node_types: ['TechStack'], available: true },
  { name: '市场定位分析', description: '市场定位、GTM 策略分析', agent_type: 'MarketPositionAnalyzer', node_types: ['MarketPositionNode'], available: true },
];

const AUDIENCE_OPTIONS = [
  { value: 'product_manager', label: '产品经理' },
  { value: 'investor', label: '投资人' },
  { value: 'engineer', label: '工程师' },
];

const SOURCE_OPTIONS = ['G2', 'ProductHunt', '官网', 'TechCrunch', '36Kr', 'Reddit', 'TrustRadius'];

/* ---- dimension state ---- */

interface DimState {
  enabled: boolean;
  weight: number;
  expanded: boolean;
  focusPoints: string[];
}

function buildInitialDims(): Map<string, DimState> {
  const m = new Map<string, DimState>();
  const available = PRESET_DIMENSIONS.filter(d => d.available);
  const baseWeight = Math.floor(100 / available.length);
  for (const d of available) {
    m.set(d.name, { enabled: true, weight: baseWeight, expanded: false, focusPoints: [] });
  }
  return m;
}

/* ---- exported handle ---- */

export interface SchemaBuilderHandle {
  getDimensions: () => AnalysisDimension[];
  getWeights: () => Record<string, number>;
  getFocusPoints: () => Record<string, string[]>;
  getSourcePrefs: () => SourcePreferences;
  getBenchmark: () => string;
  getAudience: () => string;
  getOutputFormats: () => string[];
}

/* ---- component ---- */

interface SchemaBuilderProps {
  targets: string[];
}

const SchemaBuilder = forwardRef<SchemaBuilderHandle, SchemaBuilderProps>(
  function SchemaBuilder({ targets }, ref) {
    const [dims, setDims] = useState<Map<string, DimState>>(buildInitialDims());
    const [expanded, setExpanded] = useState(false);
    const [priSources, setPriSources] = useState<string[]>(['G2', 'ProductHunt', '官网']);
    const [excSources, setExcSources] = useState<string[]>(['Reddit']);
    const [minCred, setMinCred] = useState(0.6);
    const [benchmark, setBenchmark] = useState(targets[0] || '');
    const [audience, setAudience] = useState('product_manager');

    useEffect(() => {
      if (targets.length > 0 && !targets.includes(benchmark)) {
        setBenchmark(targets[0]);
      }
      // only sync when targets list identity changes, not on every benchmark change
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [targets]);
    const [outputs, setOutputs] = useState<string[]>(['markdown', 'json']);

    /* dimension helpers */
    const toggleDim = (name: string) => setDims(prev => {
      const next = new Map(prev);
      const cur = next.get(name)!;
      next.set(name, { ...cur, enabled: !cur.enabled });
      return next;
    });
    const setWeight = (name: string, w: number) => setDims(prev => {
      const next = new Map(prev);
      const cur = next.get(name)!;
      next.set(name, { ...cur, weight: w });
      return next;
    });
    const toggleExpand = (name: string) => setDims(prev => {
      const next = new Map(prev);
      const cur = next.get(name)!;
      next.set(name, { ...cur, expanded: !cur.expanded });
      return next;
    });
    const addFocusPoint = (name: string, fp: string) => {
      if (!fp.trim()) return;
      setDims(prev => {
        const next = new Map(prev);
        const cur = next.get(name)!;
        next.set(name, { ...cur, focusPoints: [...cur.focusPoints, fp.trim()] });
        return next;
      });
    };
    const removeFocusPoint = (name: string, idx: number) => setDims(prev => {
      const next = new Map(prev);
      const cur = next.get(name)!;
      next.set(name, { ...cur, focusPoints: cur.focusPoints.filter((_, i) => i !== idx) });
      return next;
    });

    /* source chips */
    const toggleChip = (list: string[], setList: (v: string[]) => void, val: string) => {
      if (list.includes(val)) setList(list.filter(s => s !== val));
      else setList([...list, val]);
    };

    /* expose methods */
    useImperativeHandle(ref, () => ({
      getDimensions: () => {
        const result: AnalysisDimension[] = [];
        for (const d of PRESET_DIMENSIONS) {
          const st = dims.get(d.name);
          if (!st?.enabled && d.available) continue;
          if (!d.available) continue;
          result.push({
            name: d.name, description: d.description,
            focus_points: st?.focusPoints ?? [],
            node_types: d.node_types, agent_type: d.agent_type,
            weight: st?.weight ?? 0,
          });
        }
        return result;
      },
      getWeights: () => {
        const w: Record<string, number> = {};
        for (const [name, st] of dims) if (st.enabled) w[name] = st.weight;
        return w;
      },
      getFocusPoints: () => {
        const fp: Record<string, string[]> = {};
        for (const [name, st] of dims) if (st.enabled && st.focusPoints.length) fp[name] = st.focusPoints;
        return fp;
      },
      getSourcePrefs: (): SourcePreferences => ({
        priority_sources: priSources,
        excluded_sources: excSources,
        min_credibility: minCred,
        collection_depth: 'standard',
      }),
      getBenchmark: () => benchmark,
      getAudience: () => audience,
      getOutputFormats: () => outputs,
    }));

    const totalWeight = Array.from(dims.values()).filter(d => d.enabled).reduce((s, d) => s + d.weight, 0);

    return (
      <div className="space-y-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm text-slate-500 transition-colors hover:text-teal-700"
        >
          <span>{expanded ? '▾' : '▸'}</span> 高级自定义（分析维度 / 关注点 / 权重 / 信息源）
        </button>

        {expanded && (
          <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
            {/* Dimensions */}
            <div>
              <h4 className="mb-2 text-xs uppercase tracking-wide text-slate-500">分析维度 (勾选启用，拖拽调权重)</h4>
              <div className="space-y-1">
                {PRESET_DIMENSIONS.filter(d => d.available).map(d => {
                  const st = dims.get(d.name);
                  if (!st) return null;
                  const pct = totalWeight > 0 ? Math.round((st.weight / totalWeight) * 100) : 0;
                  return (
                    <div key={d.name} className="rounded border border-slate-200 bg-white p-2">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox" checked={st.enabled}
                          onChange={() => toggleDim(d.name)}
                          className="accent-teal-700"
                        />
                        <span className="flex-1 text-sm text-slate-700">{d.name}</span>
                        <span className="w-8 text-right text-xs text-slate-500">{pct}%</span>
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-200">
                          <div className="h-full rounded-full bg-teal-700" style={{ width: `${pct}%` }} />
                        </div>
                        <input
                          type="range" min={0} max={100} value={st.weight}
                          onChange={e => setWeight(d.name, Number(e.target.value))}
                          disabled={!st.enabled}
                          className="h-1 w-12 accent-teal-700"
                        />
                        <button onClick={() => toggleExpand(d.name)}
                          className="text-xs text-slate-500 hover:text-slate-900">
                          {st.expanded ? '收起▴' : '展开▾'}
                        </button>
                      </div>
                      {st.expanded && (
                        <div className="mt-2 ml-6 rounded border border-slate-200 bg-slate-50 p-2">
                          <p className="mb-1 text-xs text-slate-500">{d.description}</p>
                          <div className="flex flex-wrap gap-1 mb-1">
                            {st.focusPoints.map((fp, i) => (
                              <span key={i} className="inline-flex items-center gap-0.5 rounded border border-teal-200 bg-teal-50 px-1.5 py-0.5 text-xs text-teal-800">
                                {fp}
                                <button onClick={() => removeFocusPoint(d.name, i)} className="text-slate-500 hover:text-red-600">&times;</button>
                              </span>
                            ))}
                          </div>
                          <input
                            placeholder="+ 添加关注点"
                            onKeyDown={e => {
                              if (e.key === 'Enter') {
                                addFocusPoint(d.name, (e.target as HTMLInputElement).value);
                                (e.target as HTMLInputElement).value = '';
                              }
                            }}
                            className="w-full border-b border-slate-200 bg-transparent py-1 text-xs text-slate-600 outline-none placeholder:text-slate-400 focus:border-teal-700"
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Source preferences */}
            <div>
              <h4 className="mb-2 text-xs uppercase tracking-wide text-slate-500">信息源配置</h4>
              <div className="space-y-2">
                <div>
                  <span className="mr-2 text-xs text-slate-500">优先级:</span>
                  <div className="inline-flex flex-wrap gap-1">
                    {SOURCE_OPTIONS.map(s => (
                      <button key={s} onClick={() => toggleChip(priSources, setPriSources, s)}
                        className={`rounded border px-1.5 py-0.5 text-xs transition-colors ${
                          priSources.includes(s)
                            ? 'border-teal-200 bg-teal-50 text-teal-800'
                            : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
                        }`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="mr-2 text-xs text-slate-500">排除源:</span>
                  <div className="inline-flex flex-wrap gap-1">
                    {SOURCE_OPTIONS.map(s => (
                      <button key={s} onClick={() => toggleChip(excSources, setExcSources, s)}
                        className={`rounded border px-1.5 py-0.5 text-xs transition-colors ${
                          excSources.includes(s)
                            ? 'border-red-200 bg-red-50 text-red-700'
                            : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
                        }`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">最低可信度:</span>
                  <input type="range" min={0} max={1} step={0.05} value={minCred}
                    onChange={e => setMinCred(Number(e.target.value))} className="h-1 w-20 accent-teal-700" />
                  <span className="font-mono text-xs text-teal-700">{minCred.toFixed(2)}</span>
                </div>
              </div>
            </div>

            {/* Benchmark + Audience */}
            <div className="flex gap-4">
              <div className="flex-1">
                <label className="mb-1 block text-xs text-slate-500">对比基准</label>
                <select value={benchmark} onChange={e => setBenchmark(e.target.value)}
                  className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 outline-none focus:border-teal-700">
                  {targets.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="flex-1">
                <label className="mb-1 block text-xs text-slate-500">报告受众</label>
                <select value={audience} onChange={e => setAudience(e.target.value)}
                  className="w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 outline-none focus:border-teal-700">
                  {AUDIENCE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>

            {/* Output formats */}
            <div>
              <label className="mb-1 block text-xs text-slate-500">输出格式</label>
              <div className="flex gap-3">
                {['markdown', 'json'].map(f => (
                  <label key={f} className="flex cursor-pointer items-center gap-1.5 text-sm text-slate-700">
                    <input type="checkbox" checked={outputs.includes(f)}
                      onChange={() => setOutputs(outputs.includes(f) ? outputs.filter(o => o !== f) : [...outputs, f])}
                      className="accent-teal-700" />
                    <span className="text-xs">{f === 'markdown' ? 'Markdown' : 'JSON'}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
);

export default SchemaBuilder;
