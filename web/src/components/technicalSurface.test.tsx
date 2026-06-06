import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import AgentCard from './AgentCard';
import ConfidenceBar from './ConfidenceBar';
import DAGGraph from './DAGGraph';
import PipelineSkeleton from './PipelineSkeleton';
import TracePanel from './TracePanel';
import TraceSidebar from './TraceSidebar';

describe('technical surface light theme', () => {
  it('renders the pipeline skeleton as a light planning panel', () => {
    const { container } = render(<PipelineSkeleton />);

    expect(container.firstChild).toHaveClass('bg-white');
    expect(container.firstChild).not.toHaveClass('bg-gray-900');
    expect(screen.getByText('编排')).not.toHaveClass('font-mono');
  });

  it('renders agent cards as light cards', () => {
    const { container } = render(
      <AgentCard
        agent={{
          node_id: 'n1',
          agent_type: 'Collector',
          state: 'running',
          progress: 50,
          outputSummary: '正在采集',
        }}
      />
    );

    expect(container.firstChild).toHaveClass('bg-white');
    expect(container.firstChild).not.toHaveClass('bg-gray-900');
  });

  it('renders DAG graph empty state on a light surface', () => {
    const { container } = render(<DAGGraph nodes={[]} />);
    const svg = container.querySelector('svg');

    expect(svg).toHaveClass('bg-white');
    expect(svg).not.toHaveClass('bg-gray-900/50');
  });

  it('renders confidence track as a light progress bar', () => {
    const { container } = render(<ConfidenceBar value={0.72} />);
    const track = container.querySelector('.overflow-hidden');

    expect(track).toHaveClass('bg-slate-200');
    expect(track).not.toHaveClass('bg-gray-800');
  });

  it('renders trace panel as a light detail panel', () => {
    const { container } = render(
      <TracePanel
        nodeId="node_1"
        agentType="Collector"
        stepTraces={[]}
      />
    );

    expect(container.firstChild).toHaveClass('bg-white');
    expect(container.firstChild).not.toHaveClass('bg-gray-900');
  });

  it('renders trace sidebar as a light drawer', () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        confidence: 0.8,
        chain: [],
        contradicting_evidence: [],
        confidence_breakdown: null,
      }),
    })));

    const { container } = render(
      <MemoryRouter>
        <TraceSidebar
          isOpen
          onClose={() => {}}
          insightId="insight_1"
          taskId="task_1"
          sectionTitle="执行摘要"
        />
      </MemoryRouter>
    );

    const drawer = container.querySelector('.fixed.right-0');
    expect(drawer).toHaveClass('bg-white');
    expect(drawer).not.toHaveClass('bg-gray-950');
    vi.unstubAllGlobals();
  });
});
