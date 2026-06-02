# Demo-Focused Frontend Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the project into a portfolio-friendly demo with a clear README, a professional consulting-style frontend, preset demo entry points, and a report-first viewing experience.

**Architecture:** Keep the existing backend, APIs, DAG engine, agents, and knowledge graph unchanged. Add a small frontend content layer for demo presets and stages, then restyle the React pages so the first experience explains the result before exposing technical details.

**Tech Stack:** Python 3.12, FastAPI, React 19, Vite, Tailwind CSS 4, Vitest, Recharts.

---

## Scope Check

This plan is one scoped project: demo presentation and frontend visual simplification. It touches documentation and frontend display code only. It does not add agents, data sources, backend endpoints, database changes, or external UI dependencies.

## File Structure

- Create `README.md`: root project introduction, run commands, demo flow, architecture, tests, search record, completed work, and next items.
- Create `web/src/demoContent.ts`: shared preset cases, four demo stages, and short technical highlights.
- Create `web/src/demoContent.test.ts`: unit tests for demo content stability.
- Create `web/src/components/DemoStageStrip.tsx`: reusable four-stage progress strip for the demo workflow.
- Create `web/src/components/DemoStageStrip.test.tsx`: component tests for stage labels and active state.
- Modify `web/src/index.css`: replace dark-console base styling with professional consulting-style tokens and light report markdown styles.
- Modify `web/src/components/charts/chartTheme.ts`: align chart colors with deep blue, teal, neutral gray, and print-safe tones.
- Create `web/src/components/charts/chartTheme.test.ts`: tests for chart palette consistency.
- Modify `web/src/App.tsx`: restyle navigation and app shell from dark console to light professional layout.
- Create `web/src/App.test.tsx`: check product name and primary navigation labels.
- Modify `web/src/pages/TaskPanel.tsx`: turn the home page into a demo entry with preset scenarios, a simple input path, and advanced controls visually pushed down.
- Create `web/src/pages/TaskPanel.test.tsx`: check preset entry, four-stage copy, and task creation payload.
- Modify `web/src/pages/Report.tsx`: restyle report page as a consulting report and make trace controls feel secondary.
- Create `web/src/pages/Report.test.tsx`: check report-first layout, dashboard placement, and trace action.
- Update `CONTEXT.md`: summarize this implementation stage after code changes are complete.

---

### Task 1: Root README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README content**

Create `README.md` with this content:

```markdown
# 竞品分析 Agent 协作系统

输入一个产品或竞品范围，系统会自动收集资料、整理证据，并生成带图表和来源的竞品分析报告。

这个项目适合作品集、比赛展示和面试演示。它的重点不是展示一堆后台配置，而是让使用者快速看到：系统能产出什么报告、报告为什么可信、技术上如何支撑这个结果。

## Demo 能看到什么

- 预设竞品分析案例，一键开始体验。
- 资料来源确认，避免报告凭空生成。
- 四阶段进度：资料收集、结构化分析、报告撰写、质量检查。
- 最终报告、关键图表、来源说明和可选技术细节。

## 它解决什么问题

做竞品分析时，常见问题是资料分散、结论难追溯、报告写作耗时。这个系统把流程拆成多个专业步骤：先找资料，再提取证据，然后分析功能、定价、市场定位、技术栈和用户反馈，最后生成报告并做质量检查。

## 快速运行

### 后端

```powershell
cd E:\Agent_Project
.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload --port 8000
```

### 前端

```powershell
cd E:\Agent_Project\web
npm install
npm run dev
```

打开前端页面后，可以先选择预设 Demo，再查看生成进度和报告结果。

## 使用流程

1. 选择一个预设案例，或输入目标产品。
2. 确认系统找到的资料来源。
3. 等待系统完成资料收集、结构化分析、报告撰写和质量检查。
4. 查看报告、图表、来源和技术细节。

## 核心能力

- 多个专业 Agent 分工完成采集、分析、写作和检查。
- 知识图谱保存资料、证据、结论和报告片段。
- DAG 编排控制任务顺序，保证分析流程可追踪。
- 质量检查减少明显事实错误和逻辑冲突。
- 图表和报告按当前任务隔离，避免混入历史任务数据。

## 技术架构

```text
资料来源 -> Agent 采集与分析 -> 知识图谱 -> DAG 编排 -> FastAPI -> React 报告页
```

后端使用 FastAPI、Pydantic、SQLite 和多个 LLM SDK。前端使用 React、Vite、Tailwind CSS 和 Recharts。知识图谱是报告和图表的数据来源，Agent 不直接互相通信，而是通过知识图谱共享证据和结论。

## 测试方法

### 后端测试

```powershell
cd E:\Agent_Project
.venv\Scripts\python.exe -m pytest tests -v
```

### 前端测试

```powershell
cd E:\Agent_Project\web
npm run test
npm run build
```

测试结果只需要汇总通过和失败数量。

## 搜索记录

- GitHub 对标：只查看过 `bcefghj/competitive-analysis-agent` 的公开仓库页面，用来判断作品集展示方式；没有下载或复制对方代码。
- skills.sh：本次改造不引入外部技能或新依赖，因此没有采用新的外部方案。

## 已完成 / 待办事项

已完成：

- 多 Agent 竞品分析流程。
- 知识图谱存储和查询。
- DAG 编排和任务执行。
- 报告生成、图表展示和来源追踪。
- 质量检查、缓存、降级和任务隔离。

待办事项：

- 完成展示型首页和专业咨询风格视觉改造。
- 固化 2 到 3 个稳定预设 Demo。
- 补充部署说明和线上演示截图。
```

- [ ] **Step 2: Check README has required sections**

Run:

```powershell
chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
rg -n "快速运行|使用流程|核心能力|技术架构|测试方法|搜索记录|已完成" README.md
```

Expected: command exits with code `0` and prints matching headings.

- [ ] **Step 3: Commit README**

Run:

```powershell
git add README.md
git commit -m "docs: add portfolio-focused readme"
```

Expected: commit succeeds with `1 file changed`.

---

### Task 2: Demo Content Layer

**Files:**
- Create: `web/src/demoContent.ts`
- Create: `web/src/demoContent.test.ts`

- [ ] **Step 1: Write failing demo content tests**

Create `web/src/demoContent.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { DEMO_PRESETS, DEMO_STAGES, TECH_HIGHLIGHTS, buildPresetTargets } from './demoContent';

describe('demoContent', () => {
  it('defines three stable demo presets', () => {
    expect(DEMO_PRESETS).toHaveLength(3);
    expect(DEMO_PRESETS.map(p => p.title)).toEqual([
      'AI 编程助手',
      '项目管理工具',
      '浏览器插件',
    ]);
  });

  it('uses the simplified four-stage flow', () => {
    expect(DEMO_STAGES.map(s => s.label)).toEqual([
      '资料收集',
      '结构化分析',
      '报告撰写',
      '质量检查',
    ]);
  });

  it('builds targets from a preset without mutating the preset', () => {
    const preset = DEMO_PRESETS[0];
    const targets = buildPresetTargets(preset.id);

    expect(targets).toEqual(['Cursor', 'GitHub Copilot', 'Codeium']);
    expect(targets).not.toBe(preset.targets);
  });

  it('keeps technical highlights short', () => {
    expect(TECH_HIGHLIGHTS).toHaveLength(4);
    expect(TECH_HIGHLIGHTS.every(item => item.title.length <= 12)).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/demoContent.test.ts
```

Expected: FAIL because `web/src/demoContent.ts` does not exist.

- [ ] **Step 3: Implement demo content**

Create `web/src/demoContent.ts`:

```ts
// 这个文件集中保存首页 Demo 文案，避免页面组件里散落业务展示内容。

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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/demoContent.test.ts
```

Expected: PASS with `4 passed`.

- [ ] **Step 5: Commit demo content**

Run:

```powershell
git add web/src/demoContent.ts web/src/demoContent.test.ts
git commit -m "feat: add demo presentation content"
```

Expected: commit succeeds with `2 files changed`.

---

### Task 3: Four-Stage Demo Strip

**Files:**
- Create: `web/src/components/DemoStageStrip.tsx`
- Create: `web/src/components/DemoStageStrip.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `web/src/components/DemoStageStrip.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import DemoStageStrip from './DemoStageStrip';

describe('DemoStageStrip', () => {
  it('renders the four public demo stages', () => {
    render(<DemoStageStrip />);

    expect(screen.getByText('资料收集')).toBeInTheDocument();
    expect(screen.getByText('结构化分析')).toBeInTheDocument();
    expect(screen.getByText('报告撰写')).toBeInTheDocument();
    expect(screen.getByText('质量检查')).toBeInTheDocument();
  });

  it('marks the active stage for assistive labels', () => {
    render(<DemoStageStrip activeIndex={2} />);

    expect(screen.getByLabelText('当前阶段：报告撰写')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/components/DemoStageStrip.test.tsx
```

Expected: FAIL because `DemoStageStrip` does not exist.

- [ ] **Step 3: Implement component**

Create `web/src/components/DemoStageStrip.tsx`:

```tsx
// 这个组件把复杂 Agent 流程压缩成用户能理解的四个演示阶段。

import { DEMO_STAGES } from '../demoContent';

interface DemoStageStripProps {
  activeIndex?: number;
}

export default function DemoStageStrip({ activeIndex = 0 }: DemoStageStripProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {DEMO_STAGES.map((stage, index) => {
        const isActive = index === activeIndex;
        return (
          <div
            key={stage.key}
            aria-label={isActive ? `当前阶段：${stage.label}` : stage.label}
            className={`rounded-md border p-4 transition-colors ${
              isActive
                ? 'border-teal-600 bg-teal-50'
                : 'border-slate-200 bg-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                isActive ? 'bg-teal-700 text-white' : 'bg-slate-100 text-slate-600'
              }`}>
                {index + 1}
              </span>
              <h3 className="text-sm font-semibold text-slate-950">{stage.label}</h3>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">{stage.description}</p>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/components/DemoStageStrip.test.tsx
```

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit component**

Run:

```powershell
git add web/src/components/DemoStageStrip.tsx web/src/components/DemoStageStrip.test.tsx
git commit -m "feat: add simplified demo stage strip"
```

Expected: commit succeeds with `2 files changed`.

---

### Task 4: Visual System and Chart Palette

**Files:**
- Modify: `web/src/index.css`
- Modify: `web/src/components/charts/chartTheme.ts`
- Create: `web/src/components/charts/chartTheme.test.ts`

- [ ] **Step 1: Write failing chart theme tests**

Create `web/src/components/charts/chartTheme.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { COLORS, tooltipStyle, legendStyle } from './chartTheme';

describe('chartTheme', () => {
  it('uses a restrained consulting palette', () => {
    expect(COLORS.product.slice(0, 4)).toEqual(['#1d4ed8', '#0f766e', '#64748b', '#9333ea']);
    expect(COLORS.background).toBe('#ffffff');
    expect(COLORS.text).toBe('#334155');
  });

  it('keeps tooltip and legend readable on a light report page', () => {
    expect(tooltipStyle.contentStyle.background).toBe('#ffffff');
    expect(tooltipStyle.contentStyle.color).toBe('#0f172a');
    expect(legendStyle.wrapperStyle.color).toBe('#475569');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/components/charts/chartTheme.test.ts
```

Expected: FAIL because the current chart theme uses dark-console colors.

- [ ] **Step 3: Update chart theme**

Replace `web/src/components/charts/chartTheme.ts` with:

```ts
// Shared chart theme — hex values only (no CSS variables) for html2pdf compatibility

export const COLORS = {
  // Product series — restrained and print-safe
  product: ['#1d4ed8', '#0f766e', '#64748b', '#9333ea', '#b45309', '#be123c'],

  // Semantic
  positive: '#15803d',
  negative: '#b91c1c',
  neutral: '#64748b',

  // Maturity ordinal colors
  maturity: {
    experimental: '#b45309',
    beta: '#1d4ed8',
    ga: '#15803d',
    deprecated: '#b91c1c',
    unknown: '#94a3b8',
  } as Record<string, string>,

  // Differentiation ordinal colors
  differentiation: {
    disadvantage: '#b91c1c',
    parity: '#64748b',
    advantage: '#0f766e',
    unique: '#1d4ed8',
    unknown: '#94a3b8',
  } as Record<string, string>,

  // Chart chrome
  grid: '#e2e8f0',
  axis: '#94a3b8',
  text: '#334155',
  background: '#ffffff',
  tooltipBg: '#ffffff',
  tooltipBorder: '#cbd5e1',
} as const;

export const CHART_DEFAULTS = {
  isAnimationActive: false,
};

/** Shared tooltip style for all Recharts charts */
export const tooltipStyle = {
  contentStyle: {
    background: COLORS.tooltipBg,
    border: `1px solid ${COLORS.tooltipBorder}`,
    borderRadius: '6px',
    fontSize: '13px',
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    color: '#0f172a',
    padding: '8px 12px',
    boxShadow: '0 8px 24px rgba(15, 23, 42, 0.08)',
  },
  labelStyle: { color: '#475569', marginBottom: '4px' },
};

/** Shared legend wrapper style */
export const legendStyle = {
  wrapperStyle: {
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontSize: '12px',
    color: '#475569',
    paddingTop: '12px',
  },
};
```

- [ ] **Step 4: Update global CSS**

In `web/src/index.css`, remove the Google font import and replace the top theme block with:

```css
@import "tailwindcss";

@theme {
  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

:root {
  color-scheme: light;
  background: #f6f7f9;
  color: #0f172a;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background:
    linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
  color: #0f172a;
}
```

Then update the markdown colors in `web/src/index.css` to this light report style:

```css
.md-content .md-h1 { font-size: 1.45rem; font-weight: 700; color: #0f172a; margin: 1.5em 0 0.5em; line-height: 1.3; }
.md-content .md-h2 { font-size: 1.22rem; font-weight: 700; color: #1e293b; margin: 1.25em 0 0.4em; line-height: 1.35; }
.md-content .md-h3 { font-size: 1.05rem; font-weight: 650; color: #334155; margin: 1em 0 0.3em; line-height: 1.4; }
.md-content .md-h4,
.md-content .md-h5,
.md-content .md-h6 { font-size: 0.95rem; font-weight: 650; color: #475569; margin: 0.75em 0 0.25em; }

.md-content .md-p { margin: 0.55em 0; color: #334155; }
.md-content .md-spacer { height: 0.5em; }

.md-content strong { color: #0f172a; font-weight: 650; }
.md-content em { font-style: italic; color: #475569; }

.md-content .md-inline-code {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 0.85em;
  background: #eef2f7;
  color: #1d4ed8;
  padding: 0.1em 0.35em;
  border-radius: 3px;
  border: 1px solid #dbe3ed;
}

.md-content .md-link {
  color: #1d4ed8;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.md-content .md-link:hover { color: #1e40af; }

.md-content .md-ul,
.md-content .md-ol {
  margin: 0.45em 0;
  padding-left: 1.5em;
}
.md-content .md-ul { list-style: disc; }
.md-content .md-ol { list-style: decimal; }
.md-content li { margin: 0.2em 0; color: #334155; }
.md-content li::marker { color: #64748b; }

.md-content .md-blockquote {
  border-left: 3px solid #0f766e;
  margin: 0.7em 0;
  padding: 0.45em 0.85em;
  background: #f0fdfa;
  border-radius: 0 4px 4px 0;
}
.md-content .md-blockquote p { margin: 0; color: #334155; }

.md-content .md-hr {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 1.2em 0;
}

.md-content .md-table-wrap {
  width: 100%;
  overflow-x: auto;
  margin: 0.9em 0;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.md-content .md-table {
  width: 100%;
  min-width: 520px;
  border-collapse: collapse;
  font-size: 0.88em;
}

.md-content .md-table th,
.md-content .md-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.55rem 0.65rem;
  text-align: left;
  vertical-align: top;
}

.md-content .md-table th {
  background: #f8fafc;
  color: #0f172a;
  font-weight: 650;
}

.md-content .md-table td {
  background: #ffffff;
  color: #334155;
}
```

- [ ] **Step 5: Run visual theme tests**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/components/charts/chartTheme.test.ts src/utils/markdown.test.ts
```

Expected: PASS with `4 passed`.

- [ ] **Step 6: Commit visual system**

Run:

```powershell
git add web/src/index.css web/src/components/charts/chartTheme.ts web/src/components/charts/chartTheme.test.ts
git commit -m "style: apply consulting visual system"
```

Expected: commit succeeds with `3 files changed`.

---

### Task 5: App Shell and Navigation

**Files:**
- Modify: `web/src/App.tsx`
- Create: `web/src/App.test.tsx`

- [ ] **Step 1: Write failing app shell test**

Create `web/src/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('App shell', () => {
  it('shows the demo-focused product name and navigation', () => {
    render(<App />);

    expect(screen.getByText('CompAgent')).toBeInTheDocument();
    expect(screen.getByText('开始分析')).toBeInTheDocument();
    expect(screen.getByText('生成进度')).toBeInTheDocument();
    expect(screen.getByText('分析报告')).toBeInTheDocument();
    expect(screen.getByText('技术细节')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/App.test.tsx
```

Expected: FAIL because the current navigation uses `Tasks`, `Monitor`, `Report`, and `Trace`.

- [ ] **Step 3: Update app shell**

In `web/src/App.tsx`, replace `NavBar` with:

```tsx
function NavBar() {
  const { activeTaskId, wsConnected } = useTaskContext();
  const location = useLocation();
  const tid = activeTaskId || 'demo-task';

  const linkClass = (path: string) =>
    `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
      location.pathname === path || location.pathname.startsWith(path + '/')
        ? 'bg-slate-950 text-white'
        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
    }`;

  return (
    <nav className="border-b border-slate-200 bg-white/90 px-6 py-3 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-950 text-sm font-bold text-white">C</span>
          <span className="text-base font-semibold tracking-normal text-slate-950">CompAgent</span>
        </Link>
        <div className="hidden h-5 w-px bg-slate-200 sm:block" />
        <div className="flex items-center gap-1">
          <Link to="/" className={linkClass('/')}>开始分析</Link>
          <Link to={`/task/${tid}/monitor`} className={linkClass(`/task/${tid}/monitor`)}>生成进度</Link>
          <Link to={`/task/${tid}/report`} className={linkClass(`/task/${tid}/report`)}>分析报告</Link>
          <Link to={`/task/${tid}/trace`} className={linkClass(`/task/${tid}/trace`)}>技术细节</Link>
        </div>
        <span className="flex-1" />

        {activeTaskId && (
          <div className="hidden items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-500 sm:flex">
            <span className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-emerald-600' : 'bg-rose-600'}`} />
            <span>{wsConnected ? '已连接' : '未连接'}</span>
            <span className="max-w-[160px] truncate font-mono">#{activeTaskId}</span>
          </div>
        )}
      </div>
    </nav>
  );
}
```

In the exported `App`, replace the outer shell class with:

```tsx
<div className="min-h-screen bg-slate-100 text-slate-950">
  <NavBar />
  <ErrorBoundary>
    <AppRoutes />
  </ErrorBoundary>
</div>
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/App.test.tsx
```

Expected: PASS with `1 passed`.

- [ ] **Step 5: Commit app shell**

Run:

```powershell
git add web/src/App.tsx web/src/App.test.tsx
git commit -m "style: simplify app shell navigation"
```

Expected: commit succeeds with `2 files changed`.

---

### Task 6: Demo-Focused Home Page

**Files:**
- Modify: `web/src/pages/TaskPanel.tsx`
- Create: `web/src/pages/TaskPanel.test.tsx`

- [ ] **Step 1: Write failing home page tests**

Create `web/src/pages/TaskPanel.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ToastProvider } from '../components/Toast';
import { TaskContextProvider } from '../context/TaskContext';
import TaskPanel from './TaskPanel';

vi.mock('../components/SchemaBuilder', () => ({
  default: vi.fn(() => <div data-testid="schema-builder" />),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <TaskContextProvider>
        <ToastProvider>
          <TaskPanel />
        </ToastProvider>
      </TaskContextProvider>
    </MemoryRouter>
  );
}

describe('TaskPanel demo entry', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ task_id: 'task_demo_1' }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('presents preset demo cases before advanced controls', () => {
    renderPage();

    expect(screen.getByText('自动生成竞品分析报告')).toBeInTheDocument();
    expect(screen.getByText('AI 编程助手')).toBeInTheDocument();
    expect(screen.getByText('项目管理工具')).toBeInTheDocument();
    expect(screen.getByText('浏览器插件')).toBeInTheDocument();
    expect(screen.getByText('资料收集')).toBeInTheDocument();
  });

  it('starts a preset analysis with preset targets', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /使用 AI 编程助手案例/ }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/task', expect.objectContaining({
        method: 'POST',
      }));
    });

    const [, options] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse(String(options?.body));
    expect(body.targets).toEqual(['Cursor', 'GitHub Copilot', 'Codeium']);
    expect(body.collection_depth).toBe('standard');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/pages/TaskPanel.test.tsx
```

Expected: FAIL because the current page does not show preset demo cards.

- [ ] **Step 3: Update TaskPanel imports and preset helper**

In `web/src/pages/TaskPanel.tsx`, add imports:

```tsx
import DemoStageStrip from '../components/DemoStageStrip';
import { DEMO_PRESETS, TECH_HIGHLIGHTS, type DemoPreset } from '../demoContent';
```

Add this helper inside `TaskPanel` before `return`:

```tsx
  const startPreset = (preset: DemoPreset) => {
    setIndustry(preset.industry);
    setDepth(preset.depth);
    setTargets([...preset.targets]);
    setInputValue('');
    startAnalysis([...preset.targets]);
  };
```

- [ ] **Step 4: Add the demo hero and preset panel**

In `web/src/pages/TaskPanel.tsx`, change the opening wrapper from:

```tsx
<div className="max-w-4xl mx-auto p-6 space-y-8 animate-pageEnter">
```

to:

```tsx
<div className="mx-auto max-w-7xl px-6 py-8 animate-pageEnter">
```

Replace the old header block:

```tsx
<div>
  <h1 className="text-2xl font-bold text-gray-100">竞品分析 Agent 协作系统</h1>
  <p className="text-gray-500 text-sm mt-1 font-mono">Multi-Agent Competitive Intelligence</p>
</div>
```

with:

```tsx
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
```

Immediately before the existing task creation card, insert:

```tsx
<section className="mt-8 grid gap-6 lg:grid-cols-[1fr_360px]">
  <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
    <div>
      <h2 className="text-base font-semibold text-slate-950">自定义分析</h2>
      <p className="mt-1 text-sm text-slate-500">适合已有明确竞品名单的场景。</p>
    </div>
```

Then remove the opening line of the old task creation card:

```tsx
<div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
```

and keep its children inside the new white panel. After the submit button closing `</button>`, close the panel and add the credibility panel:

```tsx
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
```

Apply these class replacements in `TaskPanel.tsx`:

```tsx
bg-gray-950 -> bg-white
bg-gray-900 -> bg-white
bg-gray-800 -> bg-slate-100
border-gray-800 -> border-slate-200
border-gray-700 -> border-slate-300
text-gray-100 -> text-slate-950
text-gray-200 -> text-slate-800
text-gray-300 -> text-slate-700
text-gray-400 -> text-slate-600
text-gray-500 -> text-slate-500
text-cyan-400 -> text-teal-700
text-cyan-300 -> text-teal-800
bg-cyan-600 -> bg-slate-950
hover:bg-cyan-500 -> hover:bg-slate-800
focus:border-cyan-600 -> focus:border-teal-700
bg-cyan-900/40 -> bg-teal-50
bg-cyan-900/30 -> bg-teal-50
border-cyan-700/50 -> border-teal-200
```

Change the history heading from:

```tsx
历史任务
```

to:

```tsx
最近分析
```

- [ ] **Step 5: Run home page tests**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/pages/TaskPanel.test.tsx src/demoContent.test.ts src/components/DemoStageStrip.test.tsx
```

Expected: PASS with `8 passed`.

- [ ] **Step 6: Commit home page**

Run:

```powershell
git add web/src/pages/TaskPanel.tsx web/src/pages/TaskPanel.test.tsx
git commit -m "feat: make home page demo focused"
```

Expected: commit succeeds with `2 files changed`.

---

### Task 7: Consulting-Style Report Page

**Files:**
- Modify: `web/src/pages/Report.tsx`
- Create: `web/src/pages/Report.test.tsx`

- [ ] **Step 1: Write failing report tests**

Create `web/src/pages/Report.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ToastProvider } from '../components/Toast';
import Report from './Report';

vi.mock('../components/charts/AnalyticsDashboard', () => ({
  default: () => <div data-testid="analytics-dashboard">分析仪表盘</div>,
}));

function renderReport() {
  return render(
    <MemoryRouter initialEntries={['/task/task_demo/report']}>
      <ToastProvider>
        <Routes>
          <Route path="/task/:id/report" element={<Report />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe('Report page', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        sections: [
          { section: '执行摘要', content: '## 执行摘要\n\n这是摘要。', order: 1, node_id: 'n1' },
          { section: '功能对比', content: '## 功能对比\n\n这是功能。', order: 2, node_id: 'n2' },
        ],
        content: '完整报告',
      }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('puts report content and dashboard before technical trace actions', async () => {
    renderReport();

    await waitFor(() => {
      expect(screen.getByText('竞品分析报告')).toBeInTheDocument();
    });

    expect(screen.getByTestId('analytics-dashboard')).toBeInTheDocument();
    expect(screen.getByText('执行摘要')).toBeInTheDocument();
    expect(screen.getAllByText('查看证据链')[0]).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/pages/Report.test.tsx
```

Expected: FAIL because the current trace button text is `溯源 / Trace` and the page still uses dark-console styling.

- [ ] **Step 3: Restyle report shell**

In `web/src/pages/Report.tsx`, replace:

```tsx
<div className="min-h-screen bg-gray-950">
```

with:

```tsx
<div className="min-h-screen bg-slate-100">
```

Replace the sticky toolbar wrapper:

```tsx
<div className="sticky top-0 z-20 bg-gray-950/85 backdrop-blur-md border-b border-gray-800/60">
  <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
```

with:

```tsx
<div className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
  <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
```

Apply these toolbar class replacements:

```tsx
text-gray-500 -> text-slate-500
hover:text-gray-300 -> hover:text-slate-900
text-gray-700 -> text-slate-300
text-gray-100 -> text-slate-950
text-gray-600 -> text-slate-500
bg-gray-800/50 -> bg-slate-100
text-cyan-300 -> text-teal-800
bg-cyan-500/20 -> bg-teal-50
bg-cyan-500/10 -> bg-teal-50
border-cyan-500/30 -> border-teal-200
hover:bg-cyan-500/20 -> hover:bg-teal-100
hover:border-cyan-500/50 -> hover:border-teal-300
```

Replace the main content wrapper:

```tsx
<div className="max-w-5xl mx-auto px-6 py-8">
```

with:

```tsx
<div className="mx-auto max-w-6xl px-6 py-8">
```

Replace the report container:

```tsx
<div ref={reportRef} id="report-content" className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
```

Replace the report header with:

```tsx
<div className="border-b border-slate-200 px-8 py-7">
  <p className="text-sm font-semibold text-teal-700">
    {lang === 'zh' ? '竞品分析报告' : 'Competitive Analysis Report'}
  </p>
  <h2 className="mt-2 text-2xl font-semibold tracking-normal text-slate-950">
    {lang === 'zh' ? '面向决策的竞品分析' : 'Decision-ready Competitive Analysis'}
  </h2>
  <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate-500">
    <span className="rounded-md bg-slate-100 px-2.5 py-1">{sections.length} {lang === 'zh' ? '个章节' : 'sections'}</span>
    <span className="rounded-md bg-slate-100 px-2.5 py-1">Report ID: {id}</span>
    <span className="rounded-md bg-slate-100 px-2.5 py-1">
      {new Date().toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
    </span>
  </div>
</div>
```

- [ ] **Step 4: Restyle dashboard and section blocks**

In `web/src/pages/Report.tsx`, replace the dashboard wrapper with:

```tsx
<div className="border-b border-slate-200 bg-slate-50 px-8 py-6">
  <AnalyticsDashboard taskId={id!} />
</div>
```

Replace section header and trace button classes with:

```tsx
<div className="flex items-center gap-3 pt-7 pb-2">
  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 text-sm text-slate-600">
    {String(i + 1).padStart(2, '0')}
  </span>
  <h3 className="text-base font-semibold text-slate-950">{s.section}</h3>
  <div className="h-px flex-1 bg-slate-200" />
</div>

<button
  onClick={() => setSidebar({ insightId: getInsightId(s), sectionTitle: s.section })}
  className="mt-3 mb-4 inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:border-teal-700 hover:text-teal-800"
>
  查看证据链
</button>
```

- [ ] **Step 5: Run report tests**

Run:

```powershell
cd E:\Agent_Project\web
npm run test -- src/pages/Report.test.tsx src/utils/markdown.test.ts
```

Expected: PASS with `3 passed`.

- [ ] **Step 6: Commit report page**

Run:

```powershell
git add web/src/pages/Report.tsx web/src/pages/Report.test.tsx
git commit -m "style: make report page consulting focused"
```

Expected: commit succeeds with `2 files changed`.

---

### Task 8: Final Verification and Context Update

**Files:**
- Modify: `CONTEXT.md`

- [ ] **Step 1: Run frontend tests**

Run:

```powershell
cd E:\Agent_Project\web
npm run test
```

Expected: all frontend tests pass. Report only total pass and fail counts.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd E:\Agent_Project\web
npm run build
```

Expected: build exits with code `0`.

- [ ] **Step 3: Run focused backend tests**

Run:

```powershell
cd E:\Agent_Project
.venv\Scripts\python.exe -m pytest tests/test_api/test_analytics.py tests/test_agents/test_tools.py -v
```

Expected: selected backend tests pass. Report only total pass and fail counts.

- [ ] **Step 4: Start frontend dev server for visual check**

Run:

```powershell
cd E:\Agent_Project\web
npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a local URL such as `http://127.0.0.1:5173/`.

Open the local URL in the in-app browser and verify:

- 首页首屏能看到预设 Demo。
- 配色是浅灰白背景、深色正文、深蓝/青绿强调色。
- 四阶段流程清楚。
- 报告页像咨询报告，不像深色监控台。
- 技术细节入口没有抢占主内容。

- [ ] **Step 5: Update context**

Update `CONTEXT.md` to:

```markdown
# CONTEXT.md

## 当前正在做什么
已完成展示型减负实施：README、预设 Demo、四阶段流程、专业咨询感视觉和报告页展示已调整。

## 上次停在哪个位置
前端测试、前端构建和相关后端测试已完成，等待用户确认展示效果。

## 近期关键决定和原因
- 展示型改造选择“作品集 Demo 化”：首页和 README 先讲报告结果，技术细节后移。
- 默认演示流程压成 4 步：输入目标、确认来源、生成报告、查看结果。
- 暂时不新增 Agent、不新增数据源、不重构后端，优先降低对外理解成本。
- 前端视觉方向确定为“专业咨询感”：浅灰白背景、深色正文、少量深蓝/青绿强调色、小圆角和低阴影。
- 预设 Demo 固定为 AI 编程助手、项目管理工具、浏览器插件，优先保证首次体验稳定。
```

- [ ] **Step 6: Commit final context and verification-ready state**

Run:

```powershell
git add CONTEXT.md
git commit -m "docs: update context for demo simplification"
```

Expected: commit succeeds with `1 file changed`.

---

## Final Review Checklist

- [ ] README explains the product before the architecture.
- [ ] Home page shows preset demos before advanced controls.
- [ ] Four public stages are visible: 资料收集、结构化分析、报告撰写、质量检查。
- [ ] App shell no longer looks like a dark monitoring console.
- [ ] Report page prioritizes report content, chart data, and evidence links.
- [ ] Trace and DAG details remain accessible as secondary views.
- [ ] No backend endpoints or agent behavior were changed.
- [ ] `npm run test` passes.
- [ ] `npm run build` passes.
- [ ] Focused backend tests pass.
