// 这个文件集中保存首页 Demo 文案，避免页面组件里散落展示内容。

export interface DemoPreset {
  id: string;
  title: string;
  category: string;
  description: string;
  targets: string[];
  industry: string;
  depth: string;
  benchmark: string;
}

export interface DemoStage {
  key: string;
  label: string;
  description: string;
}

export interface TechHighlight {
  title: string;
  description: string;
}

export const DEMO_PRESETS: DemoPreset[] = [
  {
    id: 'collab',
    title: '飞书 vs 钉钉 vs 企业微信',
    category: '协同办公',
    description: '三大企业协作平台的功能、定价、用户口碑和市场定位全方位对比。',
    targets: ['飞书', '钉钉', '企业微信'],
    industry: 'saas',
    depth: 'demo',
    benchmark: '飞书',
  },
  {
    id: 'ai-chat',
    title: '豆包 vs Kimi vs 通义千问',
    category: 'AI 大模型',
    description: '国产大模型助手的能力边界、用户体验和生态布局对比分析。',
    targets: ['豆包', 'Kimi', '通义千问'],
    industry: 'app',
    depth: 'demo',
    benchmark: '豆包',
  },
  {
    id: 'short-video',
    title: '抖音 vs 快手 vs 视频号',
    category: '短视频平台',
    description: '三大短视频平台的用户规模、商业化能力和内容生态对比。',
    targets: ['抖音', '快手', '视频号'],
    industry: 'app',
    depth: 'demo',
    benchmark: '抖音',
  },
  {
    id: 'ai-ide',
    title: 'Trae vs Cursor vs Copilot',
    category: 'AI 编程工具',
    description: '字节 Trae 与主流 AI IDE 在代码生成、上下文理解和开发者体验上的对比。',
    targets: ['Trae', 'Cursor', 'GitHub Copilot'],
    industry: 'saas',
    depth: 'demo',
    benchmark: 'Trae',
  },
];

export const DEMO_STAGES: DemoStage[] = [
  { key: 'collect', label: '资料收集', description: '查找官网、社区、新闻和产品资料' },
  { key: 'analyze', label: '结构化分析', description: '整理功能、定价、口碑和市场定位' },
  { key: 'write', label: '报告撰写', description: '生成摘要、图表和分析结论' },
  { key: 'qa', label: '质量检查', description: '检查事实依据和逻辑一致性' },
];

export const TECH_HIGHLIGHTS: TechHighlight[] = [
  { title: '多 Agent', description: '采集、分析、写作和检查由不同角色分工完成。' },
  { title: '证据图谱', description: '资料、结论和报告片段都保存在知识图谱里。' },
  { title: '质量检查', description: '事实检查和逻辑检查降低报告幻觉。' },
  { title: '任务隔离', description: '图表和报告只读取当前任务数据。' },
];

export function buildPresetTargets(presetId: string): string[] {
  const preset = DEMO_PRESETS.find(item => item.id === presetId);
  return preset ? [...preset.targets] : [];
}
