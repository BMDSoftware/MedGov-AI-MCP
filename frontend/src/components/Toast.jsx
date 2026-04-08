import { apiFetch, authEventSourceUrl } from '../apiFetch';
import { useEffect, useRef, useState } from 'react';
import './Toast.css';

import { API_URL } from '../config.js';

/**
 * Global toast notification component.
 * Opens a single SSE connection on mount and shows a toast whenever
 * a background task starts, finishes, or fails.
 * Mount once in App.jsx outside of any tab routing.
 */
function Toast({ onTaskUpdate, authToken }) {
  const [toasts, setToasts] = useState([]);
  // Keep a ref so the onmessage closure always calls the latest callback
  // even though the effect only runs once per token (deps: [authToken]).
  const onTaskUpdateRef = useRef(onTaskUpdate);
  useEffect(() => { onTaskUpdateRef.current = onTaskUpdate; }, [onTaskUpdate]);

  useEffect(() => {
    if (!authToken) return; // don't open SSE if not logged in

    let es;
    let retryTimeout;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      es = new EventSource(authEventSourceUrl('/api/events'));
      es.onmessage = handleMessage;
      es.onerror = () => {
        es.close();
        if (!cancelled) retryTimeout = setTimeout(connect, 3000);
      };
    };

    const handleMessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        if (event.type === 'connected') return;

        let text = '';
        let variant = 'info';

        if (event.type === 'task_queued') {
          text = `Queued: ${event.description}`;
          variant = 'info';
        } else if (event.type === 'task_running') {
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
          }, 8000);
        }

        if (onTaskUpdateRef.current) onTaskUpdateRef.current(event);
      } catch {
        // ignore parse errors
      }
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(retryTimeout);
      if (es) es.close();
    };
  }, [authToken]);

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
