import { useState, useEffect, useRef } from 'react';
import { getApiUrl } from '../config';
import './Directories.css';

function classifyLine(msg) {
  if (msg.startsWith('[ERROR]')) return 'error';
  if (msg.startsWith('[FILE]')) return 'file';
  if (msg.startsWith('[AI]')) return 'ai';
  return 'info';
}

// ─── Directory Browser ────────────────────────────────────────────────────────

function DirBrowser({ current, onSelect, onClose }) {
  const [browsePath, setBrowsePath] = useState(current || '/');
  const [entries, setEntries] = useState([]);
  const [parent, setParent] = useState('/');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function navigate(path) {
    setLoading(true);
    fetch(getApiUrl(`/api/browse-directory?path=${encodeURIComponent(path)}`))
      .then(r => r.json())
      .then(data => {
        setBrowsePath(data.path);
        setParent(data.parent);
        setEntries(data.entries || []);
        setError(data.error || '');
      })
      .catch(() => setError('Failed to load directory'))
      .finally(() => setLoading(false));
  }

  useEffect(() => { navigate(current || '/'); }, []);

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal browser-modal">
        <div className="browser-header">
          <span className="browser-icon">📁</span>
          <span className="browser-title">Select Directory</span>
          <button className="browser-close" onClick={onClose}>✕</button>
        </div>

        <div className="browser-path-bar">
          <span className="browser-path-text">{browsePath}</span>
          {parent !== browsePath && (
            <button className="browser-up" onClick={() => navigate(parent)} title="Go up">
              ↑ Up
            </button>
          )}
        </div>

        <div className="browser-entries">
          {loading && <div className="browser-loading">Loading...</div>}
          {error && <div className="browser-error">{error}</div>}
          {!loading && entries.length === 0 && !error && (
            <div className="browser-empty">No subdirectories</div>
          )}
          {entries.map(e => (
            <div key={e.path} className="browser-entry" onClick={() => navigate(e.path)}>
              <span className="browser-entry-icon">📁</span>
              <span className="browser-entry-name">{e.name}</span>
              <span className="browser-entry-arrow">›</span>
            </div>
          ))}
        </div>

        <div className="browser-footer">
          <span className="browser-selected-label">Selected:</span>
          <span className="browser-selected-path">{browsePath}</span>
          <button className="btn-primary" onClick={() => onSelect(browsePath)}>
            Select this folder
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Console Panel ────────────────────────────────────────────────────────────

function ConsolePanel({ dir, onClose }) {
  const [lines, setLines] = useState([]);
  const bottomRef = useRef(null);

  useEffect(() => {
    fetch(getApiUrl(`/api/watched-directories/${dir.id}/console`))
      .then(r => r.json())
      .then(setLines)
      .catch(() => {});
  }, [dir.id]);

  useEffect(() => {
    const es = new EventSource(getApiUrl('/api/events'));
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'directory_console' && data.dir_id === dir.id) {
          setLines(prev => [...prev, { message: data.message, timestamp: data.timestamp }]);
        }
      } catch {}
    };
    return () => es.close();
  }, [dir.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  return (
    <div className="console-panel">
      <div className="console-panel-header">
        <span className="console-dot" />
        <span>Console &mdash; {dir.name}</span>
        <button className="console-close" onClick={onClose}>✕</button>
      </div>
      <div className="console-output">
        {lines.length === 0 ? (
          <div className="console-empty">No activity yet. Drop a file into the watched directory to begin.</div>
        ) : (
          lines.map((l, i) => (
            <div key={i} className={`console-line ${classifyLine(l.message)}`}>
              <span className="console-ts">{new Date(l.timestamp).toLocaleTimeString()}</span>
              {l.message}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ─── Add / Edit Modal ─────────────────────────────────────────────────────────

function DirModal({ initial, onSave, onClose }) {
  const [name, setName] = useState(initial?.name || '');
  const [path, setPath] = useState(initial?.path || '');
  const [prompt, setPrompt] = useState(initial?.custom_prompt || '');
  const [showBrowser, setShowBrowser] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim() || !path.trim()) return;
    onSave({ name: name.trim(), path: path.trim(), custom_prompt: prompt.trim() || null });
  }

  return (
    <>
      <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
        <div className="modal">
          <div className="modal-header">
            <h3>{initial ? 'Edit Directory' : 'Add Watched Directory'}</h3>
            <button className="modal-close" onClick={onClose}>✕</button>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Cardiology CT inbox"
                required
              />
            </div>
            <div className="form-group">
              <label>Path</label>
              <div className="path-input-row">
                <input
                  value={path}
                  onChange={e => setPath(e.target.value)}
                  placeholder="/absolute/path/to/directory"
                  required
                />
                <button
                  type="button"
                  className="btn-browse"
                  onClick={() => setShowBrowser(true)}
                  title="Browse filesystem"
                >
                  📁 Browse
                </button>
              </div>
            </div>
            <div className="form-group">
              <label>Custom prompt <span className="label-optional">(optional)</span></label>
              <textarea
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                placeholder="e.g. These are chest CTs. Focus on lung nodules and generate a radlex report."
              />
            </div>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn-primary">
                {initial ? 'Save changes' : 'Add directory'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {showBrowser && (
        <DirBrowser
          current={path || '/'}
          onSelect={p => { setPath(p); setShowBrowser(false); }}
          onClose={() => setShowBrowser(false)}
        />
      )}
    </>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

function StatusBadge({ dir }) {
  if (!dir.enabled) return <span className="badge badge-disabled">Disabled</span>;
  if (dir.watching) return <span className="badge badge-watching"><span className="badge-dot" />Watching</span>;
  return <span className="badge badge-stopped">Stopped</span>;
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Directories() {
  const [dirs, setDirs] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [openConsole, setOpenConsole] = useState(null);

  function load() {
    fetch(getApiUrl('/api/watched-directories'))
      .then(r => r.json())
      .then(setDirs)
      .catch(() => {});
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleAdd(data) {
    await fetch(getApiUrl('/api/watched-directories'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    setShowModal(false);
    load();
  }

  async function handleEdit(data) {
    await fetch(getApiUrl(`/api/watched-directories/${editTarget.id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    setEditTarget(null);
    load();
  }

  async function handleToggle(dir) {
    await fetch(getApiUrl(`/api/watched-directories/${dir.id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !dir.enabled })
    });
    load();
  }

  async function handleDelete(dir) {
    if (!confirm(`Remove watched directory "${dir.name}"?`)) return;
    await fetch(getApiUrl(`/api/watched-directories/${dir.id}`), { method: 'DELETE' });
    if (openConsole?.id === dir.id) setOpenConsole(null);
    load();
  }

  return (
    <div className="directories-page">
      <div className="directories-header">
        <div>
          <h2>Watched Directories</h2>
          <p className="directories-subtitle">
            Drop files into a watched directory and the AI will automatically analyze and organize them.
          </p>
        </div>
        <button className="btn-primary btn-add" onClick={() => setShowModal(true)}>
          + Add directory
        </button>
      </div>

      {dirs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📁</div>
          <strong>No watched directories</strong>
          <p>Add a directory and the AI will process new files automatically.</p>
          <button className="btn-primary" style={{ marginTop: 16 }} onClick={() => setShowModal(true)}>
            + Add your first directory
          </button>
        </div>
      ) : (
        <div className="directories-grid">
          {dirs.map(dir => (
            <div key={dir.id} className={`dir-card ${dir.watching ? 'active' : ''}`}>
              <div className="dir-card-header">
                <div className="dir-card-icon">📁</div>
                <div className="dir-card-info">
                  <span className="dir-card-title">{dir.name}</span>
                  <span className="dir-card-path">{dir.path}</span>
                </div>
                <StatusBadge dir={dir} />
              </div>

              {dir.custom_prompt && (
                <div className="dir-card-prompt">
                  <span className="prompt-icon">&#9998;</span>
                  {dir.custom_prompt}
                </div>
              )}

              <div className="dir-card-actions">
                <button
                  className={`btn-action ${dir.enabled ? 'btn-action-warn' : 'btn-action-success'}`}
                  onClick={() => handleToggle(dir)}
                >
                  {dir.enabled ? '⏸ Pause' : '▶ Start'}
                </button>
                <button
                  className="btn-action btn-action-neutral"
                  onClick={() => setEditTarget(dir)}
                >
                  ✎ Edit
                </button>
                <button
                  className={`btn-action btn-action-console ${openConsole?.id === dir.id ? 'active' : ''}`}
                  onClick={() => setOpenConsole(openConsole?.id === dir.id ? null : dir)}
                >
                  {'>'}_  Console
                </button>
                <button
                  className="btn-action btn-action-danger"
                  onClick={() => handleDelete(dir)}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {openConsole && (
        <ConsolePanel dir={openConsole} onClose={() => setOpenConsole(null)} />
      )}

      {showModal && (
        <DirModal onSave={handleAdd} onClose={() => setShowModal(false)} />
      )}

      {editTarget && (
        <DirModal initial={editTarget} onSave={handleEdit} onClose={() => setEditTarget(null)} />
      )}
    </div>
  );
}
