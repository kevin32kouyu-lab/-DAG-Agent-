import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import type { HistoryTask } from '../types';

function loadHistory(): HistoryTask[] {
  try {
    const raw = localStorage.getItem('compagent_history');
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HistoryTask[];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

const MAX_HISTORY = 20;

interface TaskContextValue {
  activeTaskId: string | null;
  setActiveTaskId: (id: string) => void;
  taskHistory: HistoryTask[];
  addToHistory: (task: HistoryTask) => void;
  updateHistoryTask: (id: string, patch: Partial<HistoryTask>) => void;
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;
}

const TaskContext = createContext<TaskContextValue>({
  activeTaskId: null,
  setActiveTaskId: () => {},
  taskHistory: [],
  addToHistory: () => {},
  updateHistoryTask: () => {},
  wsConnected: false,
  setWsConnected: () => {},
});

export function TaskContextProvider({ children }: { children: ReactNode }) {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [taskHistory, setTaskHistory] = useState<HistoryTask[]>(loadHistory);
  const [wsConnected, setWsConnected] = useState(false);
  const isFirstRender = useRef(true);

  // Persist history to localStorage on change (skip initial mount)
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    try { localStorage.setItem('compagent_history', JSON.stringify(taskHistory)); } catch { /* ignore */ }
    window.dispatchEvent(new CustomEvent('historyUpdated', { detail: taskHistory }));
  }, [taskHistory]);

  const addToHistory = useCallback((task: HistoryTask) => {
    setTaskHistory(prev => [task, ...prev.filter(h => h.id !== task.id)].slice(0, MAX_HISTORY));
  }, []);

  const updateHistoryTask = useCallback((id: string, patch: Partial<HistoryTask>) => {
    setTaskHistory(prev => prev.map(h => h.id === id ? { ...h, ...patch } : h));
  }, []);

  return (
    <TaskContext.Provider value={{ activeTaskId, setActiveTaskId, taskHistory, addToHistory, updateHistoryTask, wsConnected, setWsConnected }}>
      {children}
    </TaskContext.Provider>
  );
}

export function useTaskContext() {
  return useContext(TaskContext);
}
