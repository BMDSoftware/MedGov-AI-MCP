import { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../apiFetch';
import { API_URL } from '../config.js';

/**
 * Floating debug log panel — only rendered in debug mode.
 * Polls /api/logs every 2 seconds and shows the tail of the agent log file.
 */
function AgentLog() {
  const [lines, setLines] = useState([]);
  const [collapsed, setCollapsed] = useState(false);
  const [filename, setFilename] = useState('');
  const bottomRef = useRef(null);
  const containerRef = useRef(null);
  const userScrolledUp = useRef(false);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const res = await apiFetch(`${API_URL}/api/logs?lines=200`);
        const data = await res.json();
        if (active) {
          setLines(data.lines || []);
          setFilename(data.file || '');
        }
      } catch {
        // backend may not be up
      }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => { active = false; clearInterval(interval); };
  }, []);

  // Auto-scroll to bottom unless user scrolled up
  useEffect(() => {
    if (!userScrolledUp.current && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lines]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    userScrolledUp.current = !atBottom;
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      right: 0,
      width: collapsed ? '160px' : '520px',
      maxHeight: collapsed ? '36px' : '320px',
      background: '#0d0d14',
      border: '1px solid #6366f1',
      borderBottom: 'none',
      borderRight: 'none',
      borderTopLeftRadius: '8px',
      fontFamily: 'monospace',
      fontSize: '11px',
      zIndex: 2000,
      display: 'flex',
      flexDirection: 'column',
      transition: 'width 0.2s, max-height 0.2s',
      boxShadow: '0 -4px 20px rgba(99,102,241,0.15)',
    }}>
      {/* Header */}
      <div
        onClick={() => setCollapsed(c => !c)}
        style={{
          padding: '6px 10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          background: '#1a1a2e',
          borderTopLeftRadius: '8px',
          userSelect: 'none',
          flexShrink: 0,
        }}
      >
        <span style={{ color: '#6366f1', fontWeight: 700, fontSize: '11px' }}>
          AGENT LOG {filename ? `— ${filename}` : ''}
        </span>
        <span style={{ color: '#6366f1' }}>{collapsed ? '▲' : '▼'}</span>
      </div>

      {/* Log body */}
      {!collapsed && (
        <div
          ref={containerRef}
          onScroll={handleScroll}
          style={{
            overflowY: 'auto',
            flex: 1,
            padding: '6px 8px',
            color: '#a0a8c0',
            lineHeight: '1.5',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {lines.length === 0 ? (
            <span style={{ color: '#444' }}>No log output yet...</span>
          ) : (
            lines.map((line, i) => {
              let color = '#a0a8c0';
              if (line.includes('[ERROR]')) color = '#f87171';
              else if (line.includes('[WARNING]')) color = '#fbbf24';
              else if (line.includes('TOOL CALL')) color = '#60a5fa';
              else if (line.includes('TOOL RESULT') || line.includes('SUCCESS')) color = '#34d399';
              else if (line.includes('ITERATION')) color = '#c084fc';
              else if (line.includes('PROMPT SENT')) color = '#818cf8';
              return (
                <div key={i} style={{ color }}>{line.replace(/\n$/, '')}</div>
              );
            })
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

export default AgentLog;
