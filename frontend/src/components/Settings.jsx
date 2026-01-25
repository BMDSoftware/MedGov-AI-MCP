import React, { useEffect, useState } from 'react';
import './Settings.css';

const API_URL = 'http://localhost:5001';


function Settings() {
  // Track MCP selection state independently
  const [mcpSelected, setMcpSelected] = useState({});
  const [expandedMCPs, setExpandedMCPs] = useState({});
  const [mcpData, setMcpData] = useState({});
  const [enabledTools, setEnabledTools] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Fetch MCPs and tools
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch available tools and enabled tools
      const [toolsRes, enabledRes] = await Promise.all([
        fetch(`${API_URL}/api/available-tools`),
        fetch(`${API_URL}/api/enabled-tools`)
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

  // Toggle expand/collapse for an MCP
  const handleExpandToggle = (mcp) => {
    setExpandedMCPs(prev => ({ ...prev, [mcp]: !prev[mcp] }));
  };

  // Refresh config and reload tools
  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await fetch(`${API_URL}/api/refresh-config`, { method: 'POST' });
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
      await handleToolToggle(toolName, enable, true);
    }
  };

  // Toggle a single tool
  const handleToolToggle = async (toolName, enable, silent = false) => {
    try {
      await fetch(`${API_URL}/api/${enable ? 'enable' : 'disable'}-tool`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: toolName })
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2>Tool & MCP Settings</h2>
        <button className="refresh-btn" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
      <div className="settings-list">
        {Object.keys(mcpData).length === 0 && <div>No MCPs found.</div>}
        {Object.entries(mcpData).map(([mcp, tools]) => {
          const allEnabled = tools.every(t => enabledTools.has(t.name));
          const someEnabled = tools.some(t => enabledTools.has(t.name));
          // MCP selection is independent, defaults to allEnabled if not set
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
                <button
                  className="expand-btn"
                  onClick={() => handleExpandToggle(mcp)}
                  aria-label={expanded ? 'Collapse tools' : 'Expand tools'}
                >
                  {expanded ? (
                    <span style={{fontSize: '1.2em'}}>&#x25BC;</span>
                  ) : (
                    <span style={{fontSize: '1.2em'}}>&#x25B6;</span>
                  )}
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
    </div>
  );
}

export default Settings;
