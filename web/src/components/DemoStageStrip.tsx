// 这个组件展示对外 Demo 的四个固定阶段，供首页和进度说明复用。

import { DEMO_STAGES } from '../demoContent';

interface DemoStageStripProps {
  activeIndex?: number;
}

export default function DemoStageStrip({ activeIndex = 0 }: DemoStageStripProps) {
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Demo 阶段">
      {DEMO_STAGES.map((stage, index) => {
        const isActive = index === activeIndex;
        return (
          <li
            key={stage.key}
            aria-label={isActive ? `当前阶段：${stage.label}` : undefined}
            className={`rounded-md border px-4 py-3 transition-colors ${
              isActive
                ? 'border-teal-700 bg-teal-50'
                : 'border-slate-200 bg-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`flex h-6 w-6 items-center justify-center rounded text-xs font-semibold ${
                isActive ? 'bg-teal-700 text-white' : 'bg-slate-100 text-slate-500'
              }`}>
                {index + 1}
              </span>
              <span className="text-sm font-semibold text-slate-950">{stage.label}</span>
            </div>
            <p className="mt-2 text-sm leading-5 text-slate-600">{stage.description}</p>
          </li>
        );
      })}
    </ol>
  );
}
