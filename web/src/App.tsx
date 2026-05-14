import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import TaskPanel from './pages/TaskPanel';
import Monitor from './pages/Monitor';
import Report from './pages/Report';
import TraceExplorer from './pages/TraceExplorer';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-gray-100">
        <nav className="border-b border-gray-800 px-6 py-3 flex gap-4 items-center">
          <Link to="/" className="font-bold text-lg tracking-tight">
            <span className="text-cyan-400">Comp</span>Agent
          </Link>
          <Link to="/" className="text-gray-400 hover:text-white text-sm">Tasks</Link>
        </nav>
        <Routes>
          <Route path="/" element={<TaskPanel />} />
          <Route path="/task/:id/monitor" element={<Monitor />} />
          <Route path="/task/:id/report" element={<Report />} />
          <Route path="/task/:id/trace" element={<TraceExplorer />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
