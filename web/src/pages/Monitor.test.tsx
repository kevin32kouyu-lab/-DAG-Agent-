import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { TaskContextProvider } from '../context/TaskContext';
import { ToastProvider } from '../components/Toast';
import Monitor from './Monitor';

// Mock ResizeObserver for test environment
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ events: [], connectionStatus: 'connected' }),
}));

vi.mock('../hooks/useDemoSimulation', () => ({
  useDemoSimulation: () => ({ events: [], connectionStatus: 'connected', send: () => {} }),
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

describe('Monitor', () => {
  it('renders the analysis progress bar', async () => {
    renderMonitor();

    await waitFor(() => {
      expect(screen.getByText('分析进度')).toBeInTheDocument();
    });
  });
});
