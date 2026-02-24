import { useEffect, useRef, useState } from 'react';
import './Toast.css';

const API_URL = 'http://localhost:5001';

/**
 * Global toast notification component.
 * Opens a single SSE connection on mount and shows a toast whenever
 * a background task starts, finishes, or fails.
 * Mount once in App.jsx outside of any tab routing.
 */
function Toast({ onTaskUpdate }) {
  const [toasts, setToasts] = useState([]);
  // Keep a ref so the onmessage closure always calls the latest callback
  // even though the effect only runs once (empty deps).
  const onTaskUpdateRef = useRef(onTaskUpdate);
  useEffect(() => { onTaskUpdateRef.current = onTaskUpdate; }, [onTaskUpdate]);

  useEffect(() => {
    const es = new EventSource(`${API_URL}/api/events`);

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        if (event.type === 'connected') return;

        let text = '';
        let variant = 'info';

        if (event.type === 'task_running') {
          text = `Running: ${event.description}`;
          variant = 'info';
        } else if (event.type === 'task_done') {
          text = `Done: ${event.description}`;
          variant = 'success';
        } else if (event.type === 'task_failed') {
          text = `Failed: ${event.description}`;
          variant = 'error';
        }

        if (text) {
          const id = Date.now();
          setToasts(prev => [...prev, { id, text, variant }]);
          setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id));
          }, 5000);
        }

        if (onTaskUpdateRef.current) onTaskUpdateRef.current(event);
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      // SSE auto-reconnects; nothing to do
    };

    return () => es.close();
  }, []);

  const dismiss = (id) => setToasts(prev => prev.filter(t => t.id !== id));

  if (toasts.length === 0) return null;

  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.variant}`}>
          <span className="toast-text">{t.text}</span>
          <button className="toast-close" onClick={() => dismiss(t.id)}>×</button>
        </div>
      ))}
    </div>
  );
}

export default Toast;
