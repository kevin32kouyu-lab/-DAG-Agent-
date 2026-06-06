import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../components/Toast';
import { TaskContextProvider } from '../context/TaskContext';
import TaskPanel from './TaskPanel';

vi.mock('../components/SchemaBuilder', () => ({
  default: vi.fn(() => <div data-testid="schema-builder" />),
}));

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

describe('TaskPanel demo entry', () => {
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

  it('presents preset demo cases before advanced controls', () => {
    renderPage();

    expect(screen.getByText('自动生成竞品分析报告')).toBeInTheDocument();
    expect(screen.getByText('AI 编程助手')).toBeInTheDocument();
    expect(screen.getByText('项目管理工具')).toBeInTheDocument();
    expect(screen.getByText('浏览器插件')).toBeInTheDocument();
    expect(screen.getByText('资料收集')).toBeInTheDocument();
  });

  it('starts a preset analysis with preset targets', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /使用 AI 编程助手案例/ }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/task', expect.objectContaining({
        method: 'POST',
      }));
    });

    const [, options] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse(String(options?.body));
    expect(body.targets).toEqual(['Cursor', 'GitHub Copilot', 'Codeium']);
    expect(body.collection_depth).toBe('standard');
  });
});
