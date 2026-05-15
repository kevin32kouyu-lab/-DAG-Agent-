import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { TaskContextProvider, useTaskContext } from './context/TaskContext';
import { ToastProvider } from './components/Toast';
import ErrorBoundary from './components/ErrorBoundary';
import TaskPanel from './pages/TaskPanel';
import Monitor from './pages/Monitor';
import Report from './pages/Report';
import TraceExplorer from './pages/TraceExplorer';

/* ---- nav bar with active route highlight ---- */

function NavBar() {
  const { activeTaskId, wsConnected } = useTaskContext();
  const location = useLocation();
  const tid = activeTaskId || 'demo-task';

  const linkClass = (path: string) =>
    `text-sm transition-colors active:scale-95 inline-block ${
      location.pathname === path || location.pathname.startsWith(path + '/')
        ? 'text-white'
        : 'text-gray-400 hover:text-white'
    }`;

  return (
    <nav className="border-b border-gray-800 px-6 py-3 flex gap-4 items-center">
      <Link to="/" className="font-bold text-lg tracking-tight">
        <span className="text-cyan-400">Comp</span><span className="text-gray-100">Agent</span>
      </Link>
      <span className="text-gray-700">|</span>
      <Link to="/" className={linkClass('/')}>Tasks</Link>
      <Link to={`/task/${tid}/monitor`} className={linkClass(`/task/${tid}/monitor`)}>Monitor</Link>
      <Link to={`/task/${tid}/report`} className={linkClass(`/task/${tid}/report`)}>Report</Link>
      <Link to={`/task/${tid}/trace`} className={linkClass(`/task/${tid}/trace`)}>Trace</Link>
      <span className="flex-1" />

      {/* WS connection status */}
      {activeTaskId && (
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${
            wsConnected ? 'bg-green-500' : 'bg-red-500'
          }`} />
          <span className="text-xs text-gray-500 font-mono">
            {wsConnected ? '已连接' : '未连接'}
          </span>
        </div>
      )}

      {/* Task ID display */}
      {activeTaskId && (
        <span className="text-xs text-gray-600 font-mono bg-gray-900 px-2 py-1 rounded border border-gray-800 truncate max-w-[200px]">
          {activeTaskId}
        </span>
      )}
    </nav>
  );
}

/* ---- app layout ---- */

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<TaskPanel />} />
      <Route path="/task/:id/monitor" element={<Monitor />} />
      <Route path="/task/:id/report" element={<Report />} />
      <Route path="/task/:id/trace" element={<TraceExplorer />} />
    </Routes>
  );
}

/* ---- root ---- */

export default function App() {
  return (
    <BrowserRouter>
      <TaskContextProvider>
        <ToastProvider>
          <div className="min-h-screen bg-gray-950 text-gray-100">
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
