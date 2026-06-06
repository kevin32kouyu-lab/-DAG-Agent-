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
