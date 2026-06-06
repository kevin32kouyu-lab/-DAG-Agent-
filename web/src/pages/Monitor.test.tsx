import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { TaskContextProvider } from '../context/TaskContext';
import { ToastProvider } from '../components/Toast';
import Monitor from './Monitor';

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ events: [], connectionStatus: 'connected' }),
}));

function renderMonitor() {
  return render(
    <MemoryRouter initialEntries={['/task/demo-task/monitor']}>
      <TaskContextProvider>
        <ToastProvider>
          <Routes>
            <Route path="/task/:id/monitor" element={<Monitor />} />
          </Routes>
        </ToastProvider>
      </TaskContextProvider>
    </MemoryRouter>
  );
}

describe('Monitor light theme', () => {
  it('shows planning state on a light panel', async () => {
    const { container } = renderMonitor();

    await waitFor(() => {
      expect(screen.getByText('正在规划分析流程...')).toBeInTheDocument();
    });

    const planningPanel = container.querySelector('[data-testid="pipeline-skeleton"]');
    expect(planningPanel).toHaveClass('bg-white');
    expect(planningPanel).not.toHaveClass('bg-gray-900');
  });
});
