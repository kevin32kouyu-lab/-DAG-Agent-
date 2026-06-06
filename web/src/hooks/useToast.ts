// 这个 hook 让页面和组件调用全局提示。

import { useContext } from 'react';
import { ToastContext } from '../components/toastContext';

export function useToast() {
  return useContext(ToastContext);
}
