import { useState, useRef, useEffect } from 'react';
import { API_CONFIG, getApiUrl } from './config';
import './App.css';
import Settings from './components/Settings';
import { useState as useReactRouterState } from 'react';

function App() {
  // --- State and refs ---
  const [page, setPage] = useState('analysis');
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      content: 'Welcome to the Health Assistant. Upload a medical file to begin.',
      actions: []
    }
  ]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [sessionContext, setSessionContext] = useState({
    fileUploaded: false,
    analysisComplete: false,
    lastAnalysis: null,
    modality: null,
    bodyPart: null
  });
  const [userQuery, setUserQuery] = useState("");
  const [pendingTool, setPendingTool] = useState(null); // {tool_name, arguments}
  const [runningTool, setRunningTool] = useState(null); // tool currently executing
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // --- Effects ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --- Logic functions ---
  const addMessage = (message) => setMessages(prev => [...prev, message]);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) handleFileUpload(e.dataTransfer.files[0]);
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) handleFileUpload(e.target.files[0]);
  };

  const handleFileUpload = async (file) => {
    setUploadedFile(file);
    setIsProcessing(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD), {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error('Upload failed');
      setSessionContext(prev => ({ ...prev, fileUploaded: true }));
      addMessage({ type: 'bot', content: `File "${file.name}" uploaded. You can now ask me to analyze it.` });
    } catch (error) {
      addMessage({ type: 'bot', content: `Upload error: ${error.message}` });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAction = async (actionId) => {
    const labels = { 'analyze': 'Analyze Image', 'info': 'System Info', 'report': 'Generate Report', 'new': 'New Analysis', 'export': 'Export' };
    addMessage({ type: 'user', content: labels[actionId] || actionId });
    setIsProcessing(true);
    try {
      if (actionId === 'analyze') await handleAnalyze();
      else if (actionId === 'info') await handleGetInfo();
      else if (actionId === 'report') await handleGenerateReport();
      else if (actionId === 'new') handleNewAnalysis();
      else if (actionId === 'export') handleExport();
    } catch (error) {
      addMessage({ type: 'bot', content: `Error: ${error.message}`, actions: sessionContext.fileUploaded ? [{ id: 'analyze', label: 'Retry' }] : [] });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAnalyze = async () => {
    addMessage({ type: 'bot', content: 'Analyzing image...', isLoading: true });
    const requestBody = { action: 'analyze', modality: sessionContext.modality, bodyPart: sessionContext.bodyPart };
    const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_WORKFLOW), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    if (!response.ok) throw new Error('Analysis failed');
    const data = await response.json();
    setMessages(prev => prev.filter(m => !m.isLoading));
    let result = 'Analysis complete.\n\n';
    if (data.result?.answer) result += data.result.answer;
    else if (data.result?.error) result += `Error: ${data.result.error}`;
    else result += JSON.stringify(data.result, null, 2);
    setSessionContext(prev => ({ ...prev, analysisComplete: true, lastAnalysis: data.result }));
    addMessage({ type: 'bot', content: result, actions: [ { id: 'report', label: 'Generate Report' }, { id: 'new', label: 'New Analysis' }, { id: 'export', label: 'Export' } ] });
  };

  const handleGetInfo = async () => {
    addMessage({ type: 'bot', content: 'Loading system info...', isLoading: true });
    await new Promise(r => setTimeout(r, 500));
    setMessages(prev => prev.filter(m => !m.isLoading));
    addMessage({ type: 'bot', content: 'Available services:\n\n- MONAI: Medical image analysis\n- RadLex: Radiology terminology\n- FHIR: Patient data (if configured)', actions: [{ id: 'analyze', label: 'Analyze Image' }] });
  };

  const handleGenerateReport = async () => {
    addMessage({ type: 'bot', content: 'Generating report...', isLoading: true });
    const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_WORKFLOW), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'generate_report', analysis: sessionContext.lastAnalysis })
    });
    setMessages(prev => prev.filter(m => !m.isLoading));
    if (response?.ok) {
      const data = await response.json();
      addMessage({ type: 'bot', content: `Report:\n\n${data.result?.report || data.result?.answer || 'Report not available'}`, actions: [{ id: 'export', label: 'Export PDF' }, { id: 'new', label: 'New Analysis' }] });
    } else {
      addMessage({ type: 'bot', content: 'Report generation not available. RadLex MCP server needs to be configured.', actions: [{ id: 'new', label: 'New Analysis' }] });
    }
  };

  const handleNewAnalysis = () => {
    setUploadedFile(null);
    setSessionContext({ fileUploaded: false, analysisComplete: false, lastAnalysis: null, modality: null, bodyPart: null });
    addMessage({ type: 'bot', content: 'Ready for new analysis. Upload a file to continue.' });
  };

  const handleExport = () => {
    addMessage({ type: 'bot', content: 'Export functionality coming soon.', actions: [{ id: 'new', label: 'New Analysis' }] });
  };

  const handleConfirmTool = async () => {
    if (!pendingTool) return;
    const toolName = pendingTool.tool_name;
    addMessage({ type: 'user', content: `✓ Confirmed` });
    setPendingTool(null);
    setRunningTool(toolName);
    setIsProcessing(true);
    try {
      const response = await fetch(getApiUrl('/api/confirm-tool'), { method: 'POST' });
      const data = await response.json();
      setRunningTool(null);
      if (data.result?.type === 'confirmation_required') {
        // Another tool needs confirmation
        setPendingTool({
          tool_name: data.result.tool_name,
          arguments: data.result.arguments
        });
        addMessage({
          type: 'bot',
          content: `I want to execute: **${data.result.tool_name}**\n\nWith parameters:\n\`\`\`json\n${JSON.stringify(data.result.arguments, null, 2)}\n\`\`\``,
          isConfirmation: true
        });
      } else if (data.result?.error) {
        addMessage({ type: 'bot', content: `Error: ${data.result.error}` });
      } else {
        addMessage({ type: 'bot', content: data.result?.answer || JSON.stringify(data.result, null, 2) });
      }
    } catch (err) {
      setRunningTool(null);
      addMessage({ type: 'bot', content: `Error: ${err.message}` });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDenyTool = async () => {
    if (!pendingTool) return;
    addMessage({ type: 'user', content: `Denied: ${pendingTool.tool_name}` });
    setPendingTool(null);
    try {
      const response = await fetch(getApiUrl('/api/deny-tool'), { method: 'POST' });
      const data = await response.json();
      addMessage({ type: 'bot', content: data.result?.answer || 'Tool execution cancelled.' });
    } catch (err) {
      addMessage({ type: 'bot', content: 'Tool execution cancelled.' });
    }
  };

  // --- Render ---
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">H</span>
          <span className="logo-text">HealthMCP</span>
        </div>
        <nav className="nav">
          <a href="#" className={`nav-item${page === 'analysis' ? ' active' : ''}`} onClick={e => { e.preventDefault(); setPage('analysis'); }}>Analysis</a>
          <a href="#" className={`nav-item${page === 'history' ? ' active' : ''}`} onClick={e => { e.preventDefault(); setPage('history'); }}>History</a>
          <a href="#" className={`nav-item${page === 'settings' ? ' active' : ''}`} onClick={e => { e.preventDefault(); setPage('settings'); }}>Settings</a>
        </nav>
        <div className="sidebar-footer">
          <p className="version">v1.0.0</p>
        </div>
      </aside>

      <main className="main">
        {/* Running Tool Indicator */}
        {runningTool && (
          <div style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            backgroundColor: '#1e1e2e',
            border: '1px solid #6366f1',
            borderRadius: '8px',
            padding: '10px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            zIndex: 1000,
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
          }}>
            <div style={{
              width: '8px',
              height: '8px',
              backgroundColor: '#6366f1',
              borderRadius: '50%',
              animation: 'pulse 1s infinite'
            }} />
            <span style={{ color: '#e2e8f0', fontSize: '13px' }}>
              Running: <strong>{runningTool}</strong>
            </span>
          </div>
        )}

        <header className="header">
          <h1>Medical Image Analysis</h1>
          <p>Multi-Agent Orchestrator for Healthcare</p>
        </header>

        {page === 'settings' ? (
          <Settings />
        ) : (
          <div className="chat">
            <div className="messages">
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.type}`}>
                  <div className="message-avatar">{msg.type === 'bot' ? 'AI' : 'U'}</div>
                  <div className="message-body">
                    {msg.isLoading ? (
                      <div className="loading">
                        <span></span><span></span><span></span>
                      </div>
                    ) : (
                      <>
                        <p style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</p>
                        {msg.isConfirmation && pendingTool && i === messages.length - 1 && (
                          <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
                            <button
                              onClick={handleConfirmTool}
                              disabled={isProcessing}
                              style={{
                                backgroundColor: '#10b981',
                                color: 'white',
                                border: 'none',
                                padding: '8px 20px',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontWeight: '500'
                              }}
                            >
                              ✓ Run
                            </button>
                            <button
                              onClick={handleDenyTool}
                              disabled={isProcessing}
                              style={{
                                backgroundColor: 'transparent',
                                color: '#9ca3af',
                                border: '1px solid #4b5563',
                                padding: '8px 20px',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontWeight: '500'
                              }}
                            >
                              ✗ Skip
                            </button>
                          </div>
                        )}
                        {msg.actions?.length > 0 && (
                          <div className="actions">
                            {msg.actions.map(a => (
                              <button key={a.id} onClick={() => handleAction(a.id)} disabled={isProcessing}>
                                {a.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="input-area">
              {/* Replace drag-and-drop with text box and file upload */}
              {/* Chatbot-style input area */}
              <form className="chatbot-input-row" onSubmit={async e => {
                e.preventDefault();
                if (!userQuery.trim()) return;
                const currentQuery = userQuery;
                setUserQuery(""); // Limpa imediatamente
                addMessage({ type: 'user', content: currentQuery });
                addMessage({ type: 'bot', content: '', isLoading: true });
                setIsProcessing(true);
                try {
                  const response = await fetch(getApiUrl('/api/process-query'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'text/plain' },
                    body: currentQuery
                  });
                  const data = await response.json();

                  // Remove loading message
                  setMessages(prev => prev.filter(m => !m.isLoading));

                  // Check if tool confirmation is required
                  if (data.result?.type === 'confirmation_required') {
                    setPendingTool({
                      tool_name: data.result.tool_name,
                      arguments: data.result.arguments
                    });
                    addMessage({
                      type: 'bot',
                      content: `I want to execute: **${data.result.tool_name}**\n\nWith parameters:\n\`\`\`json\n${JSON.stringify(data.result.arguments, null, 2)}\n\`\`\``,
                      isConfirmation: true
                    });
                    setIsProcessing(false);
                    return;
                  }

                  if (data.result?.error) {
                    addMessage({ type: 'bot', content: `Error: ${data.result.error}` });
                  } else {
                    addMessage({ type: 'bot', content: data.result?.answer || JSON.stringify(data.result, null, 2) });
                  }
                } catch (err) {
                  setMessages(prev => prev.filter(m => !m.isLoading));
                  addMessage({ type: 'bot', content: `Error: ${err.message}` });
                } finally {
                  setIsProcessing(false);
                }
              }}>
                {/* Always render preview above the input row */}
                {uploadedFile && (
                  <div className="chatbot-preview">
                    {uploadedFile.type && uploadedFile.type.startsWith('image/') ? (
                      <div style={{ position: 'relative', display: 'inline-block' }}>
                        <img
                          src={URL.createObjectURL(uploadedFile)}
                          alt="preview"
                          className="chatbot-preview-img"
                        />
                        <button
                          type="button"
                          className="chatbot-remove-btn"
                          onClick={async () => {
                            if (uploadedFile?.name) {
                              try {
                                await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD) + `?filename=${encodeURIComponent(uploadedFile.name)}`, {
                                  method: 'DELETE'
                                });
                              } catch (e) {
                                // Optionally handle error
                              }
                            }
                            setUploadedFile(null);
                          }}
                          title="Remove image"
                        >
                          &times;
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', backgroundColor: 'var(--bg-secondary)', borderRadius: '8px' }}>
                        <span style={{ fontSize: '14px' }}>📄 {uploadedFile.name}</span>
                        <button
                          type="button"
                          onClick={async () => {
                            if (uploadedFile?.name) {
                              try {
                                await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD) + `?filename=${encodeURIComponent(uploadedFile.name)}`, {
                                  method: 'DELETE'
                                });
                              } catch (e) {}
                            }
                            setUploadedFile(null);
                          }}
                          title="Remove file"
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#ef4444',
                            cursor: 'pointer',
                            fontSize: '18px',
                            padding: '0 4px',
                            lineHeight: 1
                          }}
                        >
                          ✕
                        </button>
                      </div>
                    )}
                  </div>
                )}
                <div className="chatbot-input-controls">
                  <textarea
                    placeholder="Type your query..."
                    rows={3}
                    className="chatbot-textarea"
                    value={userQuery}
                    onChange={e => setUserQuery(e.target.value)}
                    disabled={isProcessing}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        e.target.form.requestSubmit();
                      }
                    }}
                  />
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.dcm,.nii,.nii.gz"
                    id="fileInput"
                    className="chatbot-file-input"
                    onChange={handleFileSelect}
                  />
                  <label htmlFor="fileInput" className="chatbot-file-label" title="Attach image">
                    <svg width="22" height="22" fill="none" stroke="#6366f1" strokeWidth="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
                  </label>
                  <button type="submit" className="chatbot-send-btn">
                    <span>Send</span>
                    <svg width="18" height="18" fill="none" stroke="#fff" strokeWidth="2" viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App
