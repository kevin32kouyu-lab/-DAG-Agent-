import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import TraceExplorer from './TraceExplorer';

function renderTraceExplorer() {
  return render(
    <MemoryRouter initialEntries={['/task/demo-task/trace']}>
      <Routes>
        <Route path="/task/:id/trace" element={<TraceExplorer />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('TraceExplorer light theme', () => {
  it('uses a light search input and light empty trace panel', () => {
    const { container } = renderTraceExplorer();
    const input = screen.getByPlaceholderText('输入 Insight ID 或节点 ID...');
    const treePanel = container.querySelector('[data-testid="trace-tree-panel"]');

    expect(input).toHaveClass('bg-white');
    expect(input).not.toHaveClass('bg-gray-900');
    expect(treePanel).toHaveClass('bg-white');
    expect(treePanel).not.toHaveClass('bg-gray-900');
    expect(screen.getByText('输入 Insight ID 开始溯源')).toBeInTheDocument();
  });
});
