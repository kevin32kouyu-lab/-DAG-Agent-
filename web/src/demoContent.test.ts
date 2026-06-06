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
