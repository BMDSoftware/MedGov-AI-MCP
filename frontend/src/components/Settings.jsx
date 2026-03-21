import { apiFetch, authEventSourceUrl } from '../apiFetch';
import React, { useEffect, useState } from 'react';
import './Settings.css';

import { API_URL } from '../config.js';


const NOTIF_COLORS = {
  server_added:    { bg: 'rgba(20,  83,  45, 0.25)', border: '#16a34a55', text: '#4ade80', label: 'Server Added'    },
  server_removed:  { bg: 'rgba(69,  10,  10, 0.25)', border: '#dc262655', text: '#f87171', label: 'Server Removed'  },
  server_enabled:  { bg: 'rgba(20,  83,  45, 0.15)', border: '#16a34a33', text: '#86efac', label: 'Server Enabled'  },
  server_disabled: { bg: 'rgba(69,  10,  10, 0.15)', border: '#dc262633', text: '#fca5a5', label: 'Server Disabled' },
  tool_added:      { bg: 'rgba(23,  37,  84, 0.25)', border: '#2563eb55', text: '#60a5fa', label: 'Tool Added'      },
  tool_removed:    { bg: 'rgba(45,  27, 105, 0.25)', border: '#7c3aed55', text: '#a78bfa', label: 'Tool Removed'    },
  tool_enabled:    { bg: 'rgba(23,  37,  84, 0.15)', border: '#2563eb33', text: '#93c5fd', label: 'Tool Enabled'    },
  tool_disabled:   { bg: 'rgba(45,  27, 105, 0.15)', border: '#7c3aed33', text: '#c4b5fd', label: 'Tool Disabled'   },
};

function Settings({ onModeChange }) {
  const [activeTab, setActiveTab] = useState('settings');

  // Mode
  const [mode, setMode] = useState('debug');
  const [modeLoading, setModeLoading] = useState(false);

  // Notifications
  const [notifications, setNotifications] = useState([]);

  // Model selection
  const [availableModels, setAvailableModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');

  // Add MCP server form
  const [addForm, setAddForm] = useState({ name: '', transport: 'http', url: '', command: '', args: '' });
  const [addError, setAddError] = useState('');
  const [addLoading, setAddLoading] = useState(false);

  // Load existing notifications on mount and listen for new ones via SSE
  useEffect(() => {
    apiFetch(`${API_URL}/api/notifications`)
      .then(r => r.json())
      .then(d => setNotifications(d.notifications || []))
      .catch(() => {});

    const es = new EventSource(authEventSourceUrl('/api/events'));
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type in NOTIF_COLORS) {
          setNotifications(prev => [...prev, data]);
        }
      } catch {}
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    apiFetch(`${API_URL}/api/available-models`)
      .then(r => r.json())
      .then(d => setAvailableModels(d.models || []))
      .catch(() => {});
    apiFetch(`${API_URL}/api/current-model`)
      .then(r => r.json())
      .then(d => setSelectedModel(d.model_id || ''))
      .catch(() => {});
  }, []);

  const handleModelChange = async (modelId) => {
    setSelectedModel(modelId);
    await apiFetch(`${API_URL}/api/set-model`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId })
    });
  };

  // Track MCP selection state independently
  const [mcpSelected, setMcpSelected] = useState({});
  const [expandedMCPs, setExpandedMCPs] = useState({});
  const [mcpData, setMcpData] = useState({});
  const [enabledTools, setEnabledTools] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Load current mode on mount
  useEffect(() => {
    apiFetch(`${API_URL}/api/mode`)
      .then(r => r.json())
      .then(d => setMode(d.mode))
      .catch(() => {});
  }, []);

  const handleSetMode = async (newMode) => {
    setModeLoading(true);
    try {
      await apiFetch(`${API_URL}/api/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      setMode(newMode);
      if (onModeChange) onModeChange(newMode);
    } catch (e) {
      // silently fail
    }
    setModeLoading(false);
  };

  // Fetch MCPs and tools
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch available tools and enabled tools
      const [toolsRes, enabledRes] = await Promise.all([
        apiFetch(`${API_URL}/api/available-tools`),
        apiFetch(`${API_URL}/api/enabled-tools`)
      ]);
      const toolsData = await toolsRes.json();
      const enabledData = await enabledRes.json();
      // Group tools by MCP
      const grouped = {};
      Object.entries(toolsData).forEach(([toolName, tool]) => {
        const mcp = tool.server;
        if (!grouped[mcp]) grouped[mcp] = [];
        grouped[mcp].push({ name: toolName, ...tool });
      });
      setMcpData(grouped);
      setEnabledTools(new Set(enabledData));
    } catch (e) {
      setError('Failed to load tools.');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAddServer = async () => {
    setAddError('');
    if (!addForm.name.trim()) { setAddError('Name is required.'); return; }
    const cfg = { transport: addForm.transport };
    if (addForm.transport === 'http') {
      if (!addForm.url.trim()) { setAddError('URL is required.'); return; }
      cfg.url = addForm.url.trim();
    } else {
      if (!addForm.command.trim()) { setAddError('Command is required.'); return; }
      cfg.command = addForm.command.trim();
      cfg.args = addForm.args.trim() ? addForm.args.trim().split(' ') : [];
    }
    setAddLoading(true);
    try {
      const res = await apiFetch(`${API_URL}/api/add-mcp-server`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: addForm.name.trim(), config: cfg })
      });
      const data = await res.json();
      if (data.error) { setAddError(data.error); }
      else {
        setAddForm({ name: '', transport: 'http', url: '', command: '', args: '' });
        await fetchData();
      }
    } catch (e) {
      setAddError('Failed to connect to server.');
    }
    setAddLoading(false);
  };

  const handleRefreshServer = async (name) => {
    try {
      await apiFetch(`${API_URL}/api/refresh-server-tools`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      await fetchData();
    } catch (e) {
      setError('Failed to refresh server tools.');
    }
  };

  const handleRemoveServer = async (name) => {
    try {
      await apiFetch(`${API_URL}/api/remove-mcp-server`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      await fetchData();
    } catch (e) {
      setError('Failed to remove server.');
    }
  };

  // Toggle expand/collapse for an MCP
  const handleExpandToggle = (mcp) => {
    setExpandedMCPs(prev => ({ ...prev, [mcp]: !prev[mcp] }));
  };

  // Refresh config and reload tools
  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await apiFetch(`${API_URL}/api/refresh-config`, { method: 'POST' });
      await fetchData();
    } catch (e) {
      setError('Failed to refresh config.');
    }
    setRefreshing(false);
  };

  // Toggle all tools for an MCP
  const handleMcpToggle = async (mcp, enable) => {
    setMcpSelected(prev => ({ ...prev, [mcp]: enable }));
    const mcpTools = mcpData[mcp]?.map(t => t.name) || [];
    for (const toolName of mcpTools) {
      await handleToolToggle(toolName, enable, true, false);
    }
    // Push a single server-level notification instead of one per tool
    const count = mcpTools.length;
    await apiFetch(`${API_URL}/api/push-notification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: enable ? 'server_enabled' : 'server_disabled',
        message: `${mcp} server ${enable ? 'enabled' : 'disabled'} (${count} tool${count !== 1 ? 's' : ''})`
      })
    }).catch(() => {});
  };

  // Toggle a single tool
  const handleToolToggle = async (toolName, enable, silent = false, notify = true) => {
    try {
      await apiFetch(`${API_URL}/api/${enable ? 'enable' : 'disable'}-tool`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: toolName, notify })
      });
      setEnabledTools(prev => {
        const next = new Set(prev);
        if (enable) next.add(toolName);
        else next.delete(toolName);
        // After updating enabledTools, update MCP selection state
        // Find the MCP for this tool
        let mcpForTool = null;
        Object.entries(mcpData).forEach(([mcp, tools]) => {
          if (tools.some(t => t.name === toolName)) mcpForTool = mcp;
        });
        if (mcpForTool) {
          const mcpTools = mcpData[mcpForTool].map(t => t.name);
          const someEnabled = mcpTools.some(t => next.has(t));
          setMcpSelected(prevSel => ({
            ...prevSel,
            [mcpForTool]: someEnabled
          }));
        }
        return next;
      });
    } catch (e) {
      if (!silent) setError('Failed to update tool state.');
    }
  };

  if (loading) return <div className="settings-loading">Loading...</div>;
  if (error) return <div className="settings-error">{error}</div>;

  return (
    <div className="settings-container">
      <div className="settings-tabs">
        <button className={`settings-tab${activeTab === 'settings' ? ' active' : ''}`} onClick={() => setActiveTab('settings')}>Settings</button>
        <button className={`settings-tab${activeTab === 'notifications' ? ' active' : ''}`} onClick={() => setActiveTab('notifications')}>
          Notifications {notifications.length > 0 && <span className="notif-badge">{notifications.length}</span>}
        </button>
      </div>

      {activeTab === 'notifications' ? (
        <div className="notif-list">
          {notifications.length === 0 && <p className="settings-mode-desc">No notifications yet.</p>}
          {[...notifications].reverse().map((n, i) => {
            const style = NOTIF_COLORS[n.type] || { bg: '#1e293b', border: '#334155', text: '#e2e8f0', label: n.type };
            return (
              <div key={i} className="notif-item" style={{ background: style.bg, borderColor: style.border }}>
                <span className="notif-label" style={{ color: style.text }}>{style.label}</span>
                <span className="notif-message">{n.message}</span>
                <span className="notif-time">{new Date(n.timestamp).toLocaleTimeString()}</span>
              </div>
            );
          })}
        </div>
      ) : (
      <>
      {/* Mode toggle */}
      <div className="settings-mode-section">
        <div className="settings-mode-header">
          <div>
            <h3 className="settings-mode-title">Application Mode</h3>
            <p className="settings-mode-desc">
              {mode === 'normal'
                ? 'Normal mode — tools run automatically and responses use formal clinical language.'
                : 'Debug mode — each tool requires confirmation and responses include raw technical output.'}
            </p>
          </div>
        </div>
        <div className="settings-mode-buttons">
          <button
            className={`settings-mode-btn${mode === 'normal' ? ' active' : ''}`}
            onClick={() => handleSetMode('normal')}
            disabled={modeLoading}
          >
            Normal
          </button>
          <button
            className={`settings-mode-btn${mode === 'debug' ? ' active debug' : ''}`}
            onClick={() => handleSetMode('debug')}
            disabled={modeLoading}
          >
            Debug
          </button>
        </div>
      </div>

      {availableModels.length > 0 && (
        <div className="settings-mode-section">
          <div className="settings-mode-header">
            <div>
              <h3 className="settings-mode-title">LLM Model</h3>
              <p className="settings-mode-desc">Select the Gemini model to use for this session.</p>
            </div>
          </div>
          <select
            className="model-selector"
            value={selectedModel}
            onChange={e => handleModelChange(e.target.value)}
          >
            {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      )}

      <div className="mcp-section-header">
        <h2>MCP Servers</h2>
        <button className="mcp-reload-btn" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? 'Reloading...' : 'Reload config'}
        </button>
      </div>
      <div className="settings-list">
        {Object.keys(mcpData).length === 0 && <div>No MCPs found.</div>}
        {Object.entries(mcpData).map(([mcp, tools]) => {
          const allEnabled = tools.every(t => enabledTools.has(t.name));
          const someEnabled = tools.some(t => enabledTools.has(t.name));
          const mcpChecked = mcpSelected[mcp] !== undefined ? mcpSelected[mcp] : allEnabled;
          const expanded = expandedMCPs[mcp] ?? false;
          return (
            <div className="mcp-group" key={mcp}>
              <div className="mcp-header">
                <input
                  type="checkbox"
                  checked={mcpChecked}
                  indeterminate={someEnabled && !allEnabled ? 'indeterminate' : undefined}
                  onChange={e => handleMcpToggle(mcp, e.target.checked)}
                />
                <span className="mcp-name">{mcp}</span>
                <span className="mcp-tool-count">{tools.length} tool{tools.length !== 1 ? 's' : ''}</span>
                <div className="mcp-actions">
                  <button className="mcp-action-btn" title="Refresh tools" onClick={() => handleRefreshServer(mcp)}>
                    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor"><path d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/><path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/></svg>
                    Refresh
                  </button>
                  <button className="mcp-action-btn danger" title="Remove server" onClick={() => handleRemoveServer(mcp)}>
                    <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor"><path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/><path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/></svg>
                    Remove
                  </button>
                </div>
                <button className="expand-btn" onClick={() => handleExpandToggle(mcp)}>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" style={{transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s'}}>
                    <path d="M4 2l6 5-6 5V2z"/>
                  </svg>
                </button>
              </div>
              {expanded && (
                <div className="tools-list">
                  {tools.map(tool => (
                    <label className="tool-item" key={tool.name}>
                      <input
                        type="checkbox"
                        checked={enabledTools.has(tool.name)}
                        onChange={e => handleToolToggle(tool.name, e.target.checked)}
                      />
                      <span className="tool-name">{tool.original_name}</span>
                      <span className="tool-desc">{tool.description}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="add-server-section">
        <h3 className="settings-mode-title">Add MCP Server</h3>
        <p className="settings-mode-desc" style={{marginBottom: '14px'}}>Connect any MCP-compatible server live without restarting.</p>
        <div className="add-server-form">
          <div className="add-server-row">
            <input className="add-server-input" placeholder="Server name (e.g. my-server)" value={addForm.name} onChange={e => setAddForm(f => ({...f, name: e.target.value}))} />
            <select className="add-server-select" value={addForm.transport} onChange={e => setAddForm(f => ({...f, transport: e.target.value}))}>
              <option value="http">HTTP</option>
              <option value="stdio">stdio</option>
            </select>
          </div>
          {addForm.transport === 'http' ? (
            <input className="add-server-input" placeholder="URL (e.g. http://localhost:3000/mcp)" value={addForm.url} onChange={e => setAddForm(f => ({...f, url: e.target.value}))} />
          ) : (
            <div className="add-server-row">
              <input className="add-server-input" placeholder="Command (e.g. npx @modelcontextprotocol/server-filesystem)" value={addForm.command} onChange={e => setAddForm(f => ({...f, command: e.target.value}))} />
              <input className="add-server-input" placeholder="Args (space-separated, optional)" value={addForm.args} onChange={e => setAddForm(f => ({...f, args: e.target.value}))} />
            </div>
          )}
          <div className="add-server-actions">
            <button className="add-server-connect-btn" onClick={handleAddServer} disabled={addLoading}>
              {addLoading ? 'Connecting...' : 'Connect'}
            </button>
            {addError && <p className="add-server-error">{addError}</p>}
          </div>
        </div>
      </div>
      </>
      )}
    </div>
  );
}

export default Settings;
