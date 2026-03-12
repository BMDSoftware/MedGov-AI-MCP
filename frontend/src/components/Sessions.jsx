import React, { useEffect, useState } from 'react';
import './Sessions.css';

import { API_URL } from '../config.js';

function Sessions({ onLoadSession }) {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveName, setSaveName] = useState('');
  const [saving, setSaving] = useState(false);
  const [expandedSession, setExpandedSession] = useState(null);
  const [sessionFiles, setSessionFiles] = useState({});
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const [savePrompt, setSavePrompt] = useState(null); // {targetSessionId} or 'new'

  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/sessions`);
      const data = await res.json();
      setSessions(data.sessions || []);
      setCurrentSessionId(data.current_session_id);
    } catch (e) {
      setError('Failed to load sessions.');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const currentSession = sessions.find(s => s.id === currentSessionId);
  const currentIsUnsaved = currentSession && currentSession.persisted === 0;

  const handleSave = async () => {
    if (!saveName.trim()) return;
    setSaving(true);
    try {
      await fetch(`${API_URL}/api/save-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: saveName.trim() })
      });
      setSaveName('');
      await fetchSessions();
    } catch (e) {
      setError('Failed to save session.');
    }
    setSaving(false);
  };

  const handleLoad = async (sessionId) => {
    // If current session is unsaved, prompt to save first
    if (currentIsUnsaved) {
      setSavePrompt({ targetSessionId: sessionId });
      return;
    }
    await doLoad(sessionId);
  };

  const doLoad = async (sessionId) => {
    try {
      const res = await fetch(`${API_URL}/api/load-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      const data = await res.json();
      if (data.status === 'loaded') {
        setCurrentSessionId(sessionId);
        if (onLoadSession) onLoadSession(data);
      }
      await fetchSessions();
    } catch (e) {
      setError('Failed to load session.');
    }
  };

  const handleNewSession = async () => {
    // If current session is unsaved, prompt to save first
    if (currentIsUnsaved) {
      setSavePrompt({ targetSessionId: 'new' });
      return;
    }
    await doNewSession();
  };

  const doNewSession = async () => {
    try {
      const res = await fetch(`${API_URL}/api/reset-session`, { method: 'POST' });
      const data = await res.json();
      await fetchSessions();
      if (onLoadSession) onLoadSession({ isNew: true, session_id: data.session_id });
    } catch (e) {
      setError('Failed to create new session.');
    }
  };

  const handleClearAll = async () => {
    try {
      await fetch(`${API_URL}/api/delete-all-sessions`, { method: 'DELETE' });
      setConfirmClearAll(false);
      setExpandedSession(null);
      setSessionFiles({});
      await fetchSessions();
    } catch (e) {
      setError('Failed to clear sessions.');
    }
  };

  const handleSavePromptSave = async () => {
    // Save current, then proceed with the action
    const target = savePrompt.targetSessionId;
    const nameToSave = saveName.trim() || currentSession?.name || 'Untitled Session';
    try {
      await fetch(`${API_URL}/api/save-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nameToSave })
      });
    } catch (e) {
      setError('Failed to save session.');
    }
    setSavePrompt(null);
    setSaveName('');
    if (target === 'new') {
      await doNewSession();
    } else {
      await doLoad(target);
    }
  };

  const handleSavePromptDiscard = async () => {
    const target = savePrompt.targetSessionId;
    const sessionToDelete = currentSessionId;
    setSavePrompt(null);
    // Switch away first (this changes the active session on the backend)
    if (target === 'new') {
      await doNewSession();
    } else {
      await doLoad(target);
    }
    // Now delete the old unsaved session (it's no longer active)
    if (sessionToDelete) {
      try {
        await fetch(`${API_URL}/api/delete-session`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionToDelete })
        });
        await fetchSessions();
      } catch (e) {
        // ignore
      }
    }
  };

  const handleDelete = async (sessionId) => {
    try {
      const res = await fetch(`${API_URL}/api/delete-session`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setSessionFiles(prev => {
          const copy = { ...prev };
          delete copy[sessionId];
          return copy;
        });
        await fetchSessions();
      }
    } catch (e) {
      setError('Failed to delete session.');
    }
    setConfirmDelete(null);
  };

  const toggleFiles = async (sessionId) => {
    if (expandedSession === sessionId) {
      setExpandedSession(null);
      return;
    }
    setExpandedSession(sessionId);
    if (!sessionFiles[sessionId]) {
      try {
        const res = await fetch(`${API_URL}/api/session-files?session_id=${sessionId}`);
        const data = await res.json();
        setSessionFiles(prev => ({ ...prev, [sessionId]: data.files || [] }));
      } catch (e) {
        setSessionFiles(prev => ({ ...prev, [sessionId]: [] }));
      }
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return '';
    const d = new Date(isoString);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  if (loading) return <div className="sessions-loading">Loading sessions...</div>;

  return (
    <div className="sessions-container">
      {/* Save-before-switch prompt */}
      {savePrompt && (
        <div className="modal-overlay">
          <div className="modal-box">
            <p className="modal-title">Unsaved Session</p>
            <p className="modal-text">
              Current session has not been saved. Save it before switching?
            </p>
            <div className="modal-input-row">
              <input
                type="text"
                className="save-input"
                placeholder="Session name..."
                value={saveName}
                onChange={e => setSaveName(e.target.value)}
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button className="save-btn" onClick={handleSavePromptSave}>
                Save & Switch
              </button>
              <button className="discard-btn" onClick={handleSavePromptDiscard}>
                Discard & Switch
              </button>
              <button className="cancel-btn" onClick={() => setSavePrompt(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmClearAll && (
        <div className="modal-overlay">
          <div className="modal-box">
            <p className="modal-title">Clear All Sessions</p>
            <p className="modal-text">
              Delete all saved sessions except the current one? This cannot be undone.
            </p>
            <div className="modal-actions">
              <button className="delete-yes" onClick={handleClearAll}>Yes, Delete All</button>
              <button className="cancel-btn" onClick={() => setConfirmClearAll(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="sessions-header">
        <h2>Sessions</h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="new-session-btn" onClick={handleNewSession}>New Session</button>
          <button className="delete-btn" onClick={() => setConfirmClearAll(true)}>Clear All</button>
        </div>
      </div>

      <div className="save-section">
        <p className="save-label">Save current session</p>
        <div className="save-row">
          <input
            type="text"
            className="save-input"
            placeholder="Session name..."
            value={saveName}
            onChange={e => setSaveName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSave()}
          />
          <button className="save-btn" onClick={handleSave} disabled={saving || !saveName.trim()}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {error && <div className="sessions-error">{error}</div>}

      <div className="sessions-list">
        {sessions.length === 0 && <div className="sessions-empty">No sessions yet.</div>}
        {sessions.map(session => {
          const isCurrent = session.id === currentSessionId;
          const isExpanded = expandedSession === session.id;
          const files = sessionFiles[session.id] || [];

          return (
            <div key={session.id} className={`session-card${isCurrent ? ' current' : ''}`}>
              <div className="session-card-header" onClick={() => toggleFiles(session.id)}>
                <div className="session-info">
                  <span className="session-name">{session.name}</span>
                  {isCurrent && <span className="current-badge">Active</span>}
                  {session.persisted === 1 && !isCurrent && <span className="saved-badge">Saved</span>}
                </div>
                <div className="session-meta">
                  <span className="session-date">{formatDate(session.updated_at)}</span>
                  {session.file_count > 0 && (
                    <span className="file-count">{session.file_count} file{session.file_count !== 1 ? 's' : ''}</span>
                  )}
                  <span className="session-size">{formatSize(session.total_size)}</span>
                  <span className="expand-indicator">{isExpanded ? '\u25BC' : '\u25B6'}</span>
                </div>
              </div>

              {isExpanded && (
                <div className="session-details">
                  {session.patient_name && (
                    <p className="session-patient">Patient: {session.patient_name}</p>
                  )}
                  {files.length > 0 && (
                    <div className="session-files">
                      {files.map(f => (
                        <div key={f.id} className="file-item">
                          <span className="file-type-badge">{f.file_type}</span>
                          <span className="file-name">{f.original_name}</span>
                          <span className="file-size">{formatSize(f.file_size)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="session-actions">
                    {!isCurrent && (
                      <button className="load-btn" onClick={() => handleLoad(session.id)}>
                        Load Session
                      </button>
                    )}
                    {!isCurrent && (
                      confirmDelete === session.id ? (
                        <div className="delete-confirm">
                          <span className="delete-confirm-text">Delete this session and all its files?</span>
                          <button className="delete-yes" onClick={() => handleDelete(session.id)}>Yes, Delete</button>
                          <button className="delete-no" onClick={() => setConfirmDelete(null)}>Cancel</button>
                        </div>
                      ) : (
                        <button className="delete-btn" onClick={(e) => { e.stopPropagation(); setConfirmDelete(session.id); }}>
                          Delete
                        </button>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default Sessions;
