import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

    expect(await screen.findByTestId('analytics-dashboard')).toBeInTheDocument();
    expect(screen.getByText('执行摘要')).toBeInTheDocument();
    expect(screen.getAllByText('查看证据链')[0]).toBeInTheDocument();
  });
});
