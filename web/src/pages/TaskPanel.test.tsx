import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../components/Toast';
import { TaskContextProvider } from '../context/TaskContext';
import TaskPanel from './TaskPanel';

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

describe('TaskPanel', () => {
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

  it('shows all four demo presets', () => {
    renderPage();

    expect(screen.getByText('自动生成竞品分析报告')).toBeInTheDocument();
    expect(screen.getByText('飞书 vs 钉钉 vs 企业微信')).toBeInTheDocument();
    expect(screen.getByText('豆包 vs Kimi vs 通义千问')).toBeInTheDocument();
    expect(screen.getByText('抖音 vs 快手 vs 视频号')).toBeInTheDocument();
    expect(screen.getByText('Trae vs Cursor vs Copilot')).toBeInTheDocument();
    expect(screen.getByText('预设案例')).toBeInTheDocument();
  });

  it('clicking a demo preset navigates without API call', async () => {
    const user = userEvent.setup();
    renderPage();

    // Click the button containing 飞书 vs 钉钉 vs 企业微信
    await user.click(screen.getByText('飞书 vs 钉钉 vs 企业微信'));

    // Demo presets navigate directly, no fetch
    expect(fetch).not.toHaveBeenCalled();
  });
});
