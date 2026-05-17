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
  { name: 'AI 能力分析', description: 'AI 功能成熟度与实际可用性对比', agent_type: 'FeatureAnalyzer', node_types: ['FeatureNode'], available: true },
  { name: 'API 与集成生态', description: 'API 开放性、第三方集成生态', agent_type: 'FeatureAnalyzer', node_types: ['FeatureNode'], available: true },
  { name: '客户支持质量', description: '支持渠道、响应速度、用户满意度', agent_type: 'SentimentAnalyzer', node_types: ['SentimentNode'], available: true },
  { name: '产品迭代速度', description: '发版频率、功能更新节奏', agent_type: 'FeatureAnalyzer', node_types: ['MetricData'], available: true },
  { name: '安全合规', description: '安全认证、合规标准支持', agent_type: 'TechStackAnalyzer', node_types: ['TechStack'], available: false },
  { name: 'Onboarding 体验', description: '新用户上手难度与引导设计', agent_type: 'FeatureAnalyzer', node_types: ['FeatureNode'], available: false },
  { name: '移动端体验', description: '移动端功能完整度与 UX', agent_type: 'FeatureAnalyzer', node_types: ['FeatureNode'], available: false },
  { name: '开源策略', description: '开源程度、社区活跃度', agent_type: 'TechStackAnalyzer', node_types: ['TechStack'], available: false },
  { name: '国际化程度', description: '多语言支持、区域化运营', agent_type: 'MarketPositionAnalyzer', node_types: ['MarketPositionNode'], available: false },
  { name: '团队规模推断', description: '从公开信息推断团队规模', agent_type: 'MarketPositionAnalyzer', node_types: ['MetricData'], available: false },
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
    const [customName, setCustomName] = useState('');

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

    /* custom dimension */
    const addCustomDim = () => {
      if (!customName.trim()) return;
      const d = PRESET_DIMENSIONS.find(d => d.name === customName.trim());
      if (d && d.available) return; // already exists
      setDims(prev => {
        const next = new Map(prev);
        next.set(customName.trim(), { enabled: true, weight: 5, expanded: false, focusPoints: [] });
        return next;
      });
      setCustomName('');
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
        // add custom dims (not in presets)
        for (const [name, st] of dims) {
          if (!PRESET_DIMENSIONS.find(d => d.name === name)) {
            result.push({
              name, description: '', focus_points: st.focusPoints,
              node_types: [], agent_type: 'FeatureAnalyzer', weight: st.weight,
            });
          }
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
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-cyan-400 font-mono transition-colors"
        >
          <span>{expanded ? '▾' : '▸'}</span> 高级自定义（分析维度 / 关注点 / 权重 / 信息源）
        </button>

        {expanded && (
          <div className="space-y-4 p-4 bg-gray-950 border border-gray-800 rounded-lg">
            {/* Dimensions */}
            <div>
              <h4 className="text-xs text-gray-500 uppercase tracking-wide mb-2">分析维度 (勾选启用，拖拽调权重)</h4>
              <div className="space-y-1">
                {PRESET_DIMENSIONS.filter(d => d.available).map(d => {
                  const st = dims.get(d.name);
                  if (!st) return null;
                  const pct = totalWeight > 0 ? Math.round((st.weight / totalWeight) * 100) : 0;
                  return (
                    <div key={d.name} className="border border-gray-800/50 rounded p-2">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox" checked={st.enabled}
                          onChange={() => toggleDim(d.name)}
                          className="accent-cyan-500"
                        />
                        <span className="text-sm text-gray-300 flex-1">{d.name}</span>
                        <span className="text-xs text-gray-600 w-8 text-right">{pct}%</span>
                        <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-cyan-600 rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                        <input
                          type="range" min={0} max={100} value={st.weight}
                          onChange={e => setWeight(d.name, Number(e.target.value))}
                          disabled={!st.enabled}
                          className="w-12 h-1 accent-cyan-500"
                        />
                        <button onClick={() => toggleExpand(d.name)}
                          className="text-gray-600 hover:text-gray-400 font-mono text-xs">
                          {st.expanded ? '收起▴' : '展开▾'}
                        </button>
                      </div>
                      {st.expanded && (
                        <div className="mt-2 ml-6 p-2 bg-gray-900/50 rounded border border-gray-800/30">
                          <p className="text-xs text-gray-500 mb-1">{d.description}</p>
                          <div className="flex flex-wrap gap-1 mb-1">
                            {st.focusPoints.map((fp, i) => (
                              <span key={i} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-cyan-900/20 border border-cyan-800/30 rounded text-xs text-cyan-300 font-mono">
                                {fp}
                                <button onClick={() => removeFocusPoint(d.name, i)} className="text-gray-500 hover:text-red-400">&times;</button>
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
                            className="w-full bg-transparent border-b border-gray-800 text-xs text-gray-400 placeholder-gray-600 outline-none focus:border-cyan-600 py-1"
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Future dimensions */}
              <div className="mt-2">
                <p className="text-xs text-gray-600 uppercase tracking-wide mb-1">后续扩展（暂不可选）</p>
                <div className="opacity-40 pointer-events-none">
                  {PRESET_DIMENSIONS.filter(d => !d.available).map(d => (
                    <div key={d.name} className="flex items-center gap-2 py-1 px-2">
                      <input type="checkbox" disabled className="accent-gray-600" />
                      <span className="text-sm text-gray-500">{d.name}</span>
                      <span className="text-xs text-gray-600">(开发中)</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Custom dimension */}
              <div className="mt-2 flex gap-2">
                <input
                  value={customName} onChange={e => setCustomName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') addCustomDim(); }}
                  placeholder="+ 新建自定义维度"
                  className="flex-1 px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-gray-300 placeholder-gray-600 outline-none focus:border-cyan-600"
                />
                <button onClick={addCustomDim} className="px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-400 hover:text-cyan-400">添加</button>
              </div>
            </div>

            {/* Source preferences */}
            <div>
              <h4 className="text-xs text-gray-500 uppercase tracking-wide mb-2">信息源配置</h4>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-gray-600 mr-2">优先级:</span>
                  <div className="inline-flex flex-wrap gap-1">
                    {SOURCE_OPTIONS.map(s => (
                      <button key={s} onClick={() => toggleChip(priSources, setPriSources, s)}
                        className={`px-1.5 py-0.5 text-xs rounded border font-mono transition-colors ${
                          priSources.includes(s)
                            ? 'bg-cyan-900/30 border-cyan-700/50 text-cyan-300'
                            : 'bg-gray-800 border-gray-700 text-gray-500 hover:border-gray-600'
                        }`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs text-gray-600 mr-2">排除源:</span>
                  <div className="inline-flex flex-wrap gap-1">
                    {SOURCE_OPTIONS.map(s => (
                      <button key={s} onClick={() => toggleChip(excSources, setExcSources, s)}
                        className={`px-1.5 py-0.5 text-xs rounded border font-mono transition-colors ${
                          excSources.includes(s)
                            ? 'bg-red-900/20 border-red-700/30 text-red-300'
                            : 'bg-gray-800 border-gray-700 text-gray-500 hover:border-gray-600'
                        }`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-600">最低可信度:</span>
                  <input type="range" min={0} max={1} step={0.05} value={minCred}
                    onChange={e => setMinCred(Number(e.target.value))} className="w-20 h-1 accent-cyan-500" />
                  <span className="text-xs text-cyan-400 font-mono">{minCred.toFixed(2)}</span>
                </div>
              </div>
            </div>

            {/* Benchmark + Audience */}
            <div className="flex gap-4">
              <div className="flex-1">
                <label className="text-xs text-gray-500 block mb-1">对比基准</label>
                <select value={benchmark} onChange={e => setBenchmark(e.target.value)}
                  className="w-full px-2 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 focus:border-cyan-600 outline-none">
                  {targets.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="flex-1">
                <label className="text-xs text-gray-500 block mb-1">报告受众</label>
                <select value={audience} onChange={e => setAudience(e.target.value)}
                  className="w-full px-2 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 focus:border-cyan-600 outline-none">
                  {AUDIENCE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>

            {/* Output formats */}
            <div>
              <label className="text-xs text-gray-500 block mb-1">输出格式</label>
              <div className="flex gap-3">
                {['markdown', 'json'].map(f => (
                  <label key={f} className="flex items-center gap-1.5 text-sm text-gray-300 cursor-pointer">
                    <input type="checkbox" checked={outputs.includes(f)}
                      onChange={() => setOutputs(outputs.includes(f) ? outputs.filter(o => o !== f) : [...outputs, f])}
                      className="accent-cyan-500" />
                    <span className="font-mono text-xs">{f === 'markdown' ? 'Markdown' : 'JSON'}</span>
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
