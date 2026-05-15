import { createContext, useContext, useState, useCallback, type ReactNode, useEffect, useRef } from 'react';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
  exiting?: boolean;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

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
    return () => { timers.current.forEach(t => clearTimeout(t)); };
  }, []);

  const icons: Record<ToastType, string> = {
    success: '✓', error: '✕', info: 'ℹ', warning: '⚠',
  };
  const colors: Record<ToastType, string> = {
    success: 'border-green-600/40 bg-green-900/20 text-green-300',
    error: 'border-red-600/40 bg-red-900/20 text-red-300',
    info: 'border-cyan-600/40 bg-cyan-900/20 text-cyan-300',
    warning: 'border-amber-600/40 bg-amber-900/20 text-amber-300',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
        {items.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-mono shadow-lg backdrop-blur-sm transition-all duration-300 ${
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

export function useToast() {
  return useContext(ToastContext);
}
