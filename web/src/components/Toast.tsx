// 这个组件负责渲染全局 Toast 提示，Toast 上下文和 hook 拆在独立文件中。

import { useState, useCallback, type ReactNode, useEffect, useRef } from 'react';
import { ToastContext, type ToastItem, type ToastType } from './toastContext';

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const remove = useCallback((id: number) => {
    setItems(prev => prev.map(t => (t.id === id ? { ...t, exiting: true } : t)));
    setTimeout(() => setItems(prev => prev.filter(t => t.id !== id)), 300);
  }, []);

  const toast = useCallback((message: string, type: ToastType = 'success') => {
    const id = nextId++;
    setItems(prev => [...prev.slice(-4), { id, message, type }]);
    const timer = setTimeout(() => remove(id), 3000);
    timers.current.set(id, timer);
  }, [remove]);

  useEffect(() => {
    const activeTimers = timers.current;
    return () => { activeTimers.forEach(t => clearTimeout(t)); };
  }, []);

  const icons: Record<ToastType, string> = {
    success: '✓', error: '✕', info: 'ℹ', warning: '⚠',
  };
  const colors: Record<ToastType, string> = {
    success: 'border-green-200 bg-green-50 text-green-800',
    error: 'border-red-200 bg-red-50 text-red-800',
    info: 'border-teal-200 bg-teal-50 text-teal-800',
    warning: 'border-amber-200 bg-amber-50 text-amber-800',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
        {items.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm shadow-lg backdrop-blur-sm transition-all duration-300 ${
              t.exiting ? 'opacity-0 translate-x-8 scale-95' : 'opacity-100 translate-x-0 animate-toastIn'
            } ${colors[t.type]}`}
          >
            <span className="text-base">{icons[t.type]}</span>
            <span>{t.message}</span>
            <button onClick={() => remove(t.id)} className="ml-2 text-current opacity-50 hover:opacity-100">&times;</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
