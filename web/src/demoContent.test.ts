import { describe, expect, it } from 'vitest';
import { DEMO_PRESETS, DEMO_STAGES, TECH_HIGHLIGHTS, buildPresetTargets } from './demoContent';

describe('demoContent', () => {
  it('defines four demo presets', () => {
    expect(DEMO_PRESETS).toHaveLength(4);
    expect(DEMO_PRESETS.map(p => p.title)).toEqual([
      '飞书 vs 钉钉 vs 企业微信',
      '豆包 vs Kimi vs 通义千问',
      '抖音 vs 快手 vs 视频号',
      'Trae vs Cursor vs Copilot',
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

    expect(targets).toEqual(['飞书', '钉钉', '企业微信']);
    expect(targets).not.toBe(preset.targets);
  });

  it('keeps technical highlights short', () => {
    expect(TECH_HIGHLIGHTS).toHaveLength(4);
    expect(TECH_HIGHLIGHTS.every(item => item.title.length <= 12)).toBe(true);
  });
});
