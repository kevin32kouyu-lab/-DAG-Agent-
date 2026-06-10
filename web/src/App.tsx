import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { TaskContextProvider } from './context/TaskContext';
import { useTaskContext } from './hooks/useTaskContext';
import { ToastProvider } from './components/Toast';
import ErrorBoundary from './components/ErrorBoundary';

const TaskPanel = lazy(() => import('./pages/TaskPanel'));
const Monitor = lazy(() => import('./pages/Monitor'));
const Report = lazy(() => import('./pages/Report'));
const Sources = lazy(() => import('./pages/Sources'));

/* ── Sidebar ── */
const NAV_ITEMS = [
  { to: '/', icon: '➕', label: '新建分析', en: 'New Task', exact: true },
  { to: '/monitor', icon: '📊', label: '分析进度', en: 'Monitor' },
  { to: '/report', icon: '📄', label: '分析报告', en: 'Report' },
  { to: '/sources', icon: '🔍', label: '来源追溯', en: 'Sources' },
];

function resolvePath(base: string, tid: string): string {
  if (base === '/') return '/';
  return `/task/${tid}${base}`;
}

function Sidebar() {
  const { activeTaskId, wsConnected } = useTaskContext();
  const tid = activeTaskId || 'demo-task';
  const location = useLocation();

  const isActive = (path: string, exact?: boolean) => {
    if (exact) return location.pathname === '/';
    return location.pathname.includes(path);
  };

  return (
    <aside className="sidebar fixed left-0 top-0 h-full w-64 border-r border-border-subtle bg-surface flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border-subtle">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 text-lg shadow-sm">🧠</span>
          <div>
            <p className="font-headline text-base font-bold tracking-tight text-on-surface leading-tight">竞品分析</p>
            <p className="text-[11px] text-on-surface-variant/40 leading-tight">Competitive Intelligence</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-5 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(item => (
          <NavLink key={item.to} to={resolvePath(item.to, tid)}
            className={[
              'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150',
              isActive(item.to, item.exact)
                ? 'bg-primary-container text-on-primary-container shadow-sm'
                : 'text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface',
            ].join(' ')}>
            <span className="text-lg flex-shrink-0">{item.icon}</span>
            <div className="min-w-0">
              <p className="text-sm font-medium leading-tight truncate">{item.label}</p>
              <p className="text-[11px] text-current/40 leading-tight">{item.en}</p>
            </div>
          </NavLink>
        ))}
      </nav>

      {/* System status */}
      <div className="border-t border-border-subtle px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${wsConnected ? 'bg-emerald-500 animate-ping' : 'bg-slate-300'}`} />
            <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${wsConnected ? 'bg-emerald-500' : 'bg-slate-400'}`} />
          </span>
          <div>
            <p className="text-xs font-medium text-on-surface-variant leading-tight">
              {wsConnected ? '系统在线' : '系统离线'}
            </p>
            <p className="text-[10px] text-on-surface-variant/40 leading-tight">
              {wsConnected ? 'Connected' : 'Disconnected'}
            </p>
          </div>
        </div>
        {activeTaskId && (
          <p className="mt-2 text-[10px] text-on-surface-variant/40 truncate pl-5">
            {activeTaskId.startsWith('demo_') ? '演示模式' : activeTaskId}
          </p>
        )}
      </div>
    </aside>
  );
}

/* ── Layout ── */
function AppRoutes() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <Routes>
        <Route path="/" element={<TaskPanel />} />
        <Route path="/task/:id/monitor" element={<Monitor />} />
        <Route path="/task/:id/report" element={<Report />} />
        <Route path="/task/:id/sources" element={<Sources />} />
        {/* evidence 重定向到 sources */}
        <Route path="/task/:id/evidence" element={<Sources />} />
      </Routes>
    </Suspense>
  );
}

function RouteLoading() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-surface border border-border-subtle text-sm text-on-surface-variant shadow-sm">
        <span className="material-symbols-outlined animate-spin text-lg">progress_activity</span>
        加载中...
      </div>
    </div>
  );
}

/* ── Root ── */
export default function App() {
  return (
    <BrowserRouter>
      <TaskContextProvider>
        <ToastProvider>
          <div className="min-h-screen bg-bg text-on-surface">
            <Sidebar />
            <main className="ml-64 min-h-screen">
              <ErrorBoundary>
                <AppRoutes />
              </ErrorBoundary>
            </main>
          </div>
        </ToastProvider>
      </TaskContextProvider>
    </BrowserRouter>
  );
}
