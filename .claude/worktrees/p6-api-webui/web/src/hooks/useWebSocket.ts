import { useEffect, useRef, useState } from 'react';

export function useWebSocket(taskId: string) {
  const [events, setEvents] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/task/${taskId}`);
    wsRef.current = ws;
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [...prev, data]);
    };
    return () => ws.close();
  }, [taskId]);

  // wsRef is kept for future use (e.g., sending messages)
  void wsRef;
  return events;
}
