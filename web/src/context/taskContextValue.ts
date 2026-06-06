// 这个文件保存任务上下文的共享类型和默认值。

import { createContext } from 'react';
import type { HistoryTask } from '../types';

export interface TaskContextValue {
  activeTaskId: string | null;
  setActiveTaskId: (id: string) => void;
  taskHistory: HistoryTask[];
  addToHistory: (task: HistoryTask) => void;
  updateHistoryTask: (id: string, patch: Partial<HistoryTask>) => void;
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;
}

export const TaskContext = createContext<TaskContextValue>({
  activeTaskId: null,
  setActiveTaskId: () => {},
  taskHistory: [],
  addToHistory: () => {},
  updateHistoryTask: () => {},
  wsConnected: false,
  setWsConnected: () => {},
});
