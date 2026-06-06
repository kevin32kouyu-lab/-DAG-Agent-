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
    id: 'ai-coding',
    title: 'AI 编程助手',
    category: '开发工具',
    description: '比较 Cursor、GitHub Copilot 和 Codeium 的功能、定价、口碑和定位。',
    targets: ['Cursor', 'GitHub Copilot', 'Codeium'],
    industry: 'saas',
    depth: 'standard',
    benchmark: 'Cursor',
  },
  {
    id: 'project-management',
    title: '项目管理工具',
    category: '团队协作',
    description: '分析 Notion、Linear 和 Asana 在项目协作场景中的差异。',
    targets: ['Notion', 'Linear', 'Asana'],
    industry: 'saas',
    depth: 'standard',
    benchmark: 'Notion',
  },
  {
    id: 'browser-extension',
    title: '浏览器插件',
    category: '效率工具',
    description: '对比 Grammarly、Monica 和 Sider 的用户价值、功能覆盖和增长机会。',
    targets: ['Grammarly', 'Monica', 'Sider'],
    industry: 'saas',
    depth: 'shallow',
    benchmark: 'Grammarly',
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
