// 这个文件定义前端路由和全局导航。

import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { TaskContextProvider } from './context/TaskContext';
import { useTaskContext } from './hooks/useTaskContext';
import { ToastProvider } from './components/Toast';
import ErrorBoundary from './components/ErrorBoundary';

const TaskPanel = lazy(() => import('./pages/TaskPanel'));
const Monitor = lazy(() => import('./pages/Monitor'));
const Report = lazy(() => import('./pages/Report'));
const TraceExplorer = lazy(() => import('./pages/TraceExplorer'));

/* ---- nav bar with active route highlight ---- */

function NavBar() {
  const { activeTaskId, wsConnected } = useTaskContext();
  const location = useLocation();
  const tid = activeTaskId || 'demo-task';

  const linkClass = (path: string) =>
    `inline-block shrink-0 whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors active:scale-95 sm:px-3 ${
      location.pathname === path || location.pathname.startsWith(path + '/')
        ? 'bg-slate-950 text-white'
        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
    }`;

  return (
    <nav className="border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur sm:px-6">
      <div className="mx-auto flex max-w-7xl items-center gap-3 sm:gap-4">
        <Link to="/" className="flex shrink-0 items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-950 text-sm font-bold text-white">C</span>
          <span className="hidden text-base font-semibold tracking-normal text-slate-950 sm:inline">CompAgent</span>
        </Link>
        <div className="hidden h-5 w-px bg-slate-200 sm:block" />
        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto sm:flex-none sm:overflow-visible">
          <Link to="/" className={linkClass('/')}>开始分析</Link>
          <Link to={`/task/${tid}/monitor`} className={linkClass(`/task/${tid}/monitor`)}>生成进度</Link>
          <Link to={`/task/${tid}/report`} className={linkClass(`/task/${tid}/report`)}>分析报告</Link>
          <Link to={`/task/${tid}/trace`} className={linkClass(`/task/${tid}/trace`)}>技术细节</Link>
        </div>
        <span className="hidden flex-1 sm:block" />

        {activeTaskId && (
          <div className="hidden items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-500 sm:flex">
            <span className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-emerald-600' : 'bg-rose-600'}`} />
            <span>{wsConnected ? '已连接' : '未连接'}</span>
            <span className="max-w-[160px] truncate font-mono">#{activeTaskId}</span>
          </div>
        )}
      </div>
    </nav>
  );
}

/* ---- app layout ---- */

function AppRoutes() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <Routes>
        <Route path="/" element={<TaskPanel />} />
        <Route path="/task/:id/monitor" element={<Monitor />} />
        <Route path="/task/:id/report" element={<Report />} />
        <Route path="/task/:id/trace" element={<TraceExplorer />} />
      </Routes>
    </Suspense>
  );
}

function RouteLoading() {
  return (
    <div className="mx-auto flex min-h-[360px] max-w-7xl items-center justify-center px-6 py-8">
      <div className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
        正在加载页面...
      </div>
    </div>
  );
}

/* ---- root ---- */

export default function App() {
  return (
    <BrowserRouter>
      <TaskContextProvider>
        <ToastProvider>
          <div className="min-h-screen bg-slate-100 text-slate-950">
            <NavBar />
            <ErrorBoundary>
              <AppRoutes />
            </ErrorBoundary>
          </div>
        </ToastProvider>
      </TaskContextProvider>
    </BrowserRouter>
  );
}
