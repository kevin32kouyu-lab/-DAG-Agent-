import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type { HistoryTask } from '../types';

function loadHistory(): HistoryTask[] {
  try {
    const raw = localStorage.getItem('compagent_history');
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HistoryTask[];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

interface TaskContextValue {
  activeTaskId: string | null;
  setActiveTaskId: (id: string) => void;
  taskHistory: HistoryTask[];
  addToHistory: (task: HistoryTask) => void;
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;
}

const TaskContext = createContext<TaskContextValue>({
  activeTaskId: null,
  setActiveTaskId: () => {},
  taskHistory: [],
  addToHistory: () => {},
  wsConnected: false,
  setWsConnected: () => {},
});

export function TaskContextProvider({ children }: { children: ReactNode }) {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [taskHistory, setTaskHistory] = useState<HistoryTask[]>(loadHistory);
  const [wsConnected, setWsConnected] = useState(false);

  const addToHistory = useCallback((task: HistoryTask) => {
    setTaskHistory(prev => {
      const next = [task, ...prev.filter(h => h.id !== task.id)].slice(0, 20);
      try { localStorage.setItem('compagent_history', JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);

  return (
    <TaskContext.Provider value={{ activeTaskId, setActiveTaskId, taskHistory, addToHistory, wsConnected, setWsConnected }}>
      {children}
    </TaskContext.Provider>
  );
}

export function useTaskContext() {
  return useContext(TaskContext);
}
