// 这个 hook 让页面访问当前任务状态和历史记录。

import { useContext } from 'react';
import { TaskContext } from '../context/taskContextValue';

export function useTaskContext() {
  return useContext(TaskContext);
}
