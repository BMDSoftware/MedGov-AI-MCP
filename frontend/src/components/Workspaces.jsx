import { apiFetch, authEventSourceUrl } from '../apiFetch';
import { useState, useEffect, useRef } from 'react';
import { getApiUrl } from '../config';
import BorderGlow from './BorderGlow';
import { Reorder, useDragControls } from 'motion/react';
import {
  MdDragIndicator,
  MdFolderOpen,
  MdFolder,
  MdPlayArrow,
  MdPause,
  MdEdit,
  MdTerminal,
  MdDeleteOutline,
  MdAdd,
  MdArrowUpward,
  MdClose,
  MdChevronRight,
  MdKeyboardArrowRight,
  MdKeyboardArrowDown,
  MdOutlineEditNote,
  MdFolderSpecial,
} from 'react-icons/md';
import './Workspaces.css';

const ORDER_KEY = 'workspaces_order';

function classifyLine(msg) {
  if (msg.startsWith('[ERROR]')) return 'error';
  if (msg.startsWith('[FILE]')) return 'file';
  if (msg.startsWith('[AI]')) return 'ai';
  return 'info';
}

function applyOrder(apiDirs, savedOrder) {
  if (!savedOrder.length) return apiDirs;
  const map = Object.fromEntries(apiDirs.map(d => [d.id, d]));
  const ordered = savedOrder.filter(id => map[id]).map(id => map[id]);
  const extra = apiDirs.filter(d => !savedOrder.includes(d.id));
  return [...ordered, ...extra];
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
    apiFetch(getApiUrl(`/api/browse-directory?path=${encodeURIComponent(path)}`))
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
          <MdFolder className="browser-icon" />
          <span className="browser-title">Select Folder</span>
          <button className="browser-close" onClick={onClose}><MdClose /></button>
        </div>

        <div className="browser-path-bar">
          <span className="browser-path-text">{browsePath}</span>
          {parent !== browsePath && (
            <button className="browser-up" onClick={() => navigate(parent)}>
              <MdArrowUpward size={13} /> Up
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
              <MdFolder className="browser-entry-icon" />
              <span className="browser-entry-name">{e.name}</span>
              <MdChevronRight className="browser-entry-arrow" />
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
  const sseBaselineRef = useRef(null);

  useEffect(() => {
    apiFetch(getApiUrl(`/api/watched-directories/${dir.id}/console`))
      .then(r => r.json())
      .then(data => {
        setLines(data);
        sseBaselineRef.current = data.length > 0
          ? data[data.length - 1].timestamp
          : new Date().toISOString();
      })
      .catch(() => { sseBaselineRef.current = new Date().toISOString(); });
  }, [dir.id]);

  useEffect(() => {
    const es = new EventSource(authEventSourceUrl('/api/events'));
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'directory_console' && data.dir_id === dir.id) {
          if (sseBaselineRef.current && data.timestamp <= sseBaselineRef.current) return;
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
        <MdTerminal size={14} />
        <span>Console — {dir.name}</span>
        <button className="console-close" onClick={onClose}><MdClose /></button>
      </div>
      <div className="console-output">
        {lines.length === 0 ? (
          <div className="console-empty">No activity yet. Drop a file into this workspace to begin.</div>
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

function WorkspaceModal({ initial, onSave, onClose, workspaces = [] }) {
  const [name, setName] = useState(initial?.name || '');
  const [path, setPath] = useState(initial?.path || '');
  const initialPrompt = initial?.custom_prompt || '';
  const [showBrowser, setShowBrowser] = useState(false);
  const [mcpData, setMcpData] = useState({});
  const [selectedTools, setSelectedTools] = useState(new Set(initial?.allowed_tools || []));
  const [allTools, setAllTools] = useState(true);
  const [expandedServers, setExpandedServers] = useState({});
  const [mention, setMention] = useState({ active: false, query: '' });
  const [mentionIdx, setMentionIdx] = useState(0);
  const editorRef = useRef(null);

  const mentionCandidates = workspaces
    .filter(w => (!initial || w.id !== initial.id) && w.name.toLowerCase().includes(mention.query.toLowerCase()));

  // Read the contentEditable DOM and produce a resolved prompt string
  function readEditorContent(resolve) {
    const el = editorRef.current;
    if (!el) return '';
    let result = '';
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        result += node.textContent;
      } else if (node.dataset?.wsPath && resolve) {
        result += node.dataset.wsPath;
      } else if (node.dataset?.wsName) {
        result += `#${node.dataset.wsName}`;
      } else {
        result += node.textContent;
      }
    }
    return result;
  }

  // Detect # trigger from caret position in contentEditable
  function detectMention() {
    const sel = window.getSelection();
    if (!sel.rangeCount) return setMention({ active: false, query: '' });
    const range = sel.getRangeAt(0);
    const node = range.startContainer;
    if (node.nodeType !== Node.TEXT_NODE) return setMention({ active: false, query: '' });
    const text = node.textContent.slice(0, range.startOffset);
    const hashIdx = text.lastIndexOf('#');
    if (hashIdx >= 0 && (hashIdx === 0 || /\s/.test(text[hashIdx - 1]))) {
      const query = text.slice(hashIdx + 1);
      if (!/\s/.test(query)) {
        setMention({ active: true, query, node, hashIdx });
        setMentionIdx(0);
        return;
      }
    }
    setMention({ active: false, query: '' });
  }

  function handleEditorInput() {
    detectMention();
  }

  function handleEditorKeyDown(e) {
    if (mention.active && mentionCandidates.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIdx(i => (i + 1) % mentionCandidates.length);
        return;
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIdx(i => (i - 1 + mentionCandidates.length) % mentionCandidates.length);
        return;
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(mentionCandidates[mentionIdx]);
        return;
      } else if (e.key === 'Escape') {
        setMention({ active: false, query: '' });
        return;
      }
    }
  }

  function insertMention(ws) {
    const { node, hashIdx, query } = mention;
    if (!node) return;

    // Split the text node: before the #, and after the query
    const textBefore = node.textContent.slice(0, hashIdx);
    const textAfter = node.textContent.slice(hashIdx + 1 + query.length);

    // Create the tag span
    const tag = document.createElement('span');
    tag.className = 'prompt-tag';
    tag.contentEditable = 'false';
    tag.dataset.wsName = ws.name;
    tag.dataset.wsPath = ws.path;
    tag.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg> ${ws.name}`;

    const parent = node.parentNode;

    // Replace: textBefore + tag + space + textAfter
    const beforeNode = document.createTextNode(textBefore);
    const afterNode = document.createTextNode('\u00A0' + textAfter);

    parent.insertBefore(beforeNode, node);
    parent.insertBefore(tag, node);
    parent.insertBefore(afterNode, node);
    parent.removeChild(node);

    // Place caret after the tag
    const sel = window.getSelection();
    const range = document.createRange();
    range.setStart(afterNode, 1);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);

    setMention({ active: false, query: '' });
    editorRef.current?.focus();
  }

  // Initialize editor content from saved prompt (which has paths, need to convert back to tags)
  useEffect(() => {
    if (!editorRef.current || !initialPrompt) return;
    // Build a map of path -> workspace for reverse lookup
    const pathToWs = {};
    workspaces.forEach(ws => { pathToWs[ws.path] = ws; });

    let html = initialPrompt.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c]);
    // Replace known workspace paths with tag spans
    for (const ws of workspaces) {
      if (!initial || ws.id !== initial.id) {
        const escaped = ws.path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        html = html.replace(new RegExp(escaped, 'g'),
          `<span class="prompt-tag" contenteditable="false" data-ws-name="${ws.name}" data-ws-path="${ws.path}"><svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg> ${ws.name}</span>`
        );
      }
    }
    editorRef.current.innerHTML = html;
  }, []);

  useEffect(() => {
    Promise.all([
      apiFetch(getApiUrl('/api/available-tools')).then(r => r.json()),
      apiFetch(getApiUrl('/api/enabled-tools')).then(r => r.json()),
    ]).then(([toolsData, enabledTools]) => {
      const grouped = {};
      Object.entries(toolsData).forEach(([toolName, tool]) => {
        const server = tool.server;
        if (!grouped[server]) grouped[server] = [];
        grouped[server].push(toolName);
      });
      setMcpData(grouped);
      if (!initial?.allowed_tools) {
        setSelectedTools(new Set(enabledTools));
        setAllTools(true);
      } else {
        setSelectedTools(new Set(initial.allowed_tools));
        setAllTools(false);
      }
    }).catch(() => {});
  }, []);

  function toggleServer(server, tools) {
    setAllTools(false);
    setSelectedTools(prev => {
      const next = new Set(prev);
      const allOn = tools.every(t => next.has(t));
      tools.forEach(t => allOn ? next.delete(t) : next.add(t));
      return next;
    });
  }

  function toggleTool(toolName) {
    setAllTools(false);
    setSelectedTools(prev => {
      const next = new Set(prev);
      next.has(toolName) ? next.delete(toolName) : next.add(toolName);
      return next;
    });
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim() || !path.trim()) return;
    const resolvedPrompt = readEditorContent(true).trim() || null;
    console.log('[WorkspaceModal] custom_prompt:', resolvedPrompt);
    onSave({
      name: name.trim(),
      path: path.trim(),
      custom_prompt: resolvedPrompt,
      allowed_tools: allTools ? null : [...selectedTools],
    });
  }

  return (
    <>
      <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
        <div className="modal">
          <div className="modal-header">
            <h3>{initial ? 'Edit Workspace' : 'Add Workspace'}</h3>
            <button className="modal-close" onClick={onClose}><MdClose /></button>
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
                >
                  <MdFolder size={15} /> Browse
                </button>
              </div>
            </div>
            <div className="form-group">
              <label>Custom prompt <span className="label-optional">(optional)</span></label>
              <div className="prompt-mention-wrap">
                <div
                  ref={editorRef}
                  className="prompt-editable"
                  contentEditable
                  suppressContentEditableWarning
                  onInput={handleEditorInput}
                  onKeyDown={handleEditorKeyDown}
                  data-placeholder="e.g. These are chest CTs. Focus on lung nodules. Type # to reference another workspace."
                />
                {mention.active && mentionCandidates.length > 0 && (
                  <div className="mention-dropdown">
                    {mentionCandidates.map((ws, i) => (
                      <div
                        key={ws.id}
                        className={`mention-item ${i === mentionIdx ? 'mention-item-active' : ''}`}
                        onMouseDown={() => insertMention(ws)}
                      >
                        <span className="mention-name">{ws.name}</span>
                        <span className="mention-path">{ws.path}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="form-group">
              <label>Tools <span className="label-optional">(optional)</span></label>
              <div className="tool-selector">
                <label className="tool-all-toggle">
                  <input type="checkbox" checked={allTools} onChange={e => setAllTools(e.target.checked)} />
                  All tools (default)
                </label>
                {!allTools && Object.entries(mcpData).map(([server, tools]) => {
                  const allOn = tools.every(t => selectedTools.has(t));
                  const someOn = tools.some(t => selectedTools.has(t));
                  const expanded = !!expandedServers[server];
                  return (
                    <div key={server} className="tool-server-group">
                      <div className="tool-server-row">
                        <input
                          type="checkbox"
                          checked={allOn}
                          ref={el => { if (el) el.indeterminate = !allOn && someOn; }}
                          onChange={() => toggleServer(server, tools)}
                        />
                        <button
                          type="button"
                          className="tool-server-toggle"
                          onClick={() => setExpandedServers(prev => ({ ...prev, [server]: !prev[server] }))}
                        >
                          <span className="tool-server-name">{server}</span>
                          <span className="tool-server-count">{tools.filter(t => selectedTools.has(t)).length}/{tools.length}</span>
                          {expanded ? <MdKeyboardArrowDown size={16} /> : <MdKeyboardArrowRight size={16} />}
                        </button>
                      </div>
                      {expanded && (
                        <div className="tool-list">
                          {tools.map(t => (
                            <label key={t} className="tool-item">
                              <input type="checkbox" checked={selectedTools.has(t)} onChange={() => toggleTool(t)} />
                              {t.replace(`${server}.`, '').replace(/_/g, ' ').toLowerCase()}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn-primary">
                {initial ? 'Save changes' : 'Add workspace'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {showBrowser && (
        <DirBrowser
          current={path || '/'}
          onSelect={p => { setPath(p); if (!name.trim()) setName(p.split('/').filter(Boolean).pop() || ''); setShowBrowser(false); }}
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

// ─── Workspace Card (draggable) ───────────────────────────────────────────────

function WorkspaceCard({ dir, onToggle, onEdit, onDelete, openConsoleId, setOpenConsole }) {
  const controls = useDragControls();
  const consoleOpen = openConsoleId === dir.id;

  return (
    <Reorder.Item
      value={dir}
      dragListener={false}
      dragControls={controls}
      as="div"
      className="dir-item"
      whileDrag={{ scale: 1.02, boxShadow: '0 16px 40px rgba(0,0,0,0.5)', zIndex: 10 }}
      transition={{ duration: 0.15 }}
    >
      <BorderGlow
        borderRadius={14}
        backgroundColor="#0c0c14"
        colors={dir.watching ? ['#06b6d4', '#6366f1', '#34d399'] : ['#6366f1', '#8b5cf6', '#38bdf8']}
        glowRadius={28}
        glowIntensity={0.8}
        edgeSensitivity={22}
        style={{ width: '100%' }}
      >
        <div className={`dir-card ${dir.watching ? 'active' : ''}`}>

          {/* Drag handle */}
          <div
            className="dir-drag-handle"
            onPointerDown={e => controls.start(e)}
            title="Drag to reorder"
          >
            <MdDragIndicator size={18} />
          </div>

          {/* Folder icon */}
          <div className="dir-card-icon-wrap">
            {dir.watching
              ? <MdFolderOpen size={26} className="dir-folder-icon active" />
              : <MdFolder size={26} className="dir-folder-icon" />}
          </div>

          {/* Info */}
          <div className="dir-card-info">
            <div className="dir-card-top">
              <span className="dir-card-title">{dir.name}</span>
              <StatusBadge dir={dir} />
            </div>
            <span className="dir-card-path">{dir.path}</span>
            {dir.custom_prompt && (
              <div className="dir-card-prompt">
                <MdOutlineEditNote size={13} className="prompt-icon" />
                {dir.custom_prompt}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="dir-card-actions">
            <button
              className={`btn-action ${dir.enabled ? 'btn-action-warn' : 'btn-action-success'}`}
              onClick={() => onToggle(dir)}
              title={dir.enabled ? 'Pause' : 'Start'}
            >
              {dir.enabled ? <MdPause size={15} /> : <MdPlayArrow size={15} />}
              <span>{dir.enabled ? 'Pause' : 'Start'}</span>
            </button>
            <button
              className="btn-action btn-action-neutral"
              onClick={() => onEdit(dir)}
              title="Edit"
            >
              <MdEdit size={14} />
              <span>Edit</span>
            </button>
            <button
              className={`btn-action btn-action-console ${consoleOpen ? 'active' : ''}`}
              onClick={() => setOpenConsole(consoleOpen ? null : dir)}
              title="Console"
            >
              <MdTerminal size={14} />
              <span>Console</span>
            </button>
            <button
              className="btn-action btn-action-danger btn-icon-only"
              onClick={() => onDelete(dir)}
              title="Remove"
            >
              <MdDeleteOutline size={16} />
            </button>
          </div>

        </div>
      </BorderGlow>
    </Reorder.Item>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Workspaces() {
  const [dirs, setDirs] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [openConsole, setOpenConsole] = useState(null);

  function applyStoredOrder(apiDirs) {
    try {
      const saved = JSON.parse(localStorage.getItem(ORDER_KEY) || '[]');
      return applyOrder(apiDirs, saved);
    } catch {
      return apiDirs;
    }
  }

  function load() {
    apiFetch(getApiUrl('/api/watched-directories'))
      .then(r => r.json())
      .then(apiDirs => setDirs(applyStoredOrder(apiDirs)))
      .catch(() => {});
  }

  function handleReorder(newDirs) {
    setDirs(newDirs);
    localStorage.setItem(ORDER_KEY, JSON.stringify(newDirs.map(d => d.id)));
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleAdd(data) {
    await apiFetch(getApiUrl('/api/watched-directories'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    setShowModal(false);
    load();
  }

  async function handleEdit(data) {
    await apiFetch(getApiUrl(`/api/watched-directories/${editTarget.id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    setEditTarget(null);
    load();
  }

  async function handleToggle(dir) {
    await apiFetch(getApiUrl(`/api/watched-directories/${dir.id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !dir.enabled })
    });
    load();
  }

  async function handleDelete(dir) {
    if (!confirm(`Remove workspace "${dir.name}"?`)) return;
    await apiFetch(getApiUrl(`/api/watched-directories/${dir.id}`), { method: 'DELETE' });
    if (openConsole?.id === dir.id) setOpenConsole(null);
    load();
  }

  return (
    <div className="directories-page">
      {/* Subtle background */}
      <div className="ws-bg-orb ws-bg-orb-1" />
      <div className="ws-bg-orb ws-bg-orb-2" />
      <div className="ws-bg-grid" />

      <div className="directories-header">
        <div>
          <h2>Workspaces</h2>
          <p className="directories-subtitle">
            Drop files into a workspace and the AI will automatically analyze and organize them.
          </p>
        </div>
        <button className="btn-primary btn-add" onClick={() => setShowModal(true)}>
          <MdAdd size={17} />
          Add workspace
        </button>
      </div>

      {dirs.length === 0 ? (
        <div className="empty-state">
          <MdFolderSpecial size={48} className="empty-icon" />
          <strong>No workspaces yet</strong>
          <p>Add a workspace and the AI will process new files automatically.</p>
          <button className="btn-primary" style={{ marginTop: 16 }} onClick={() => setShowModal(true)}>
            <MdAdd size={16} /> Add your first workspace
          </button>
        </div>
      ) : (
        <Reorder.Group
          as="div"
          axis="y"
          values={dirs}
          onReorder={handleReorder}
          className="directories-list"
        >
          {dirs.map(dir => (
            <WorkspaceCard
              key={dir.id}
              dir={dir}
              onToggle={handleToggle}
              onEdit={setEditTarget}
              onDelete={handleDelete}
              openConsoleId={openConsole?.id}
              setOpenConsole={setOpenConsole}
            />
          ))}
        </Reorder.Group>
      )}

      {openConsole && (
        <ConsolePanel dir={openConsole} onClose={() => setOpenConsole(null)} />
      )}

      {showModal && (
        <WorkspaceModal onSave={handleAdd} onClose={() => setShowModal(false)} workspaces={dirs} />
      )}

      {editTarget && (
        <WorkspaceModal initial={editTarget} onSave={handleEdit} onClose={() => setEditTarget(null)} workspaces={dirs} />
      )}
    </div>
  );
}
