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
  const [showModalitySelect, setShowModalitySelect] = useState(false);
  const [userQuery, setUserQuery] = useState("");
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
    addMessage({ type: 'user', content: `File: ${file.name}` });
    setIsProcessing(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD), {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error('Upload failed');
      const fileName = file.name.toLowerCase();
      const needsModalityInput = !fileName.endsWith('.dcm');
      setSessionContext(prev => ({ ...prev, fileUploaded: true }));
      if (needsModalityInput) {
        setShowModalitySelect(true);
        addMessage({ type: 'bot', content: `File "${file.name}" received. Please specify the image type so we can select the right AI model:`, actions: [] });
      } else {
        addMessage({ type: 'bot', content: `File "${file.name}" received. What would you like to do?`, actions: [ { id: 'analyze', label: 'Analyze Image' }, { id: 'info', label: 'System Info' } ] });
      }
    } catch (error) {
      addMessage({ type: 'bot', content: `Upload error: ${error.message}`, actions: [] });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleModalitySelect = async (modality, bodyPart) => {
    setShowModalitySelect(false);
    setSessionContext(prev => ({ ...prev, modality, bodyPart }));
    addMessage({ type: 'user', content: `Image type: ${modality} - ${bodyPart}` });
    try {
      await fetch(getApiUrl('/api/set-metadata'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modality, bodyPart })
      });
    } catch (e) {
      console.log('Metadata endpoint not available, will use query context');
    }
    const modalityText = modality || 'auto-detected';
    const bodyPartText = bodyPart || 'auto-detected';
    addMessage({ type: 'bot', content: `Got it! Modality: ${modalityText}, Body part: ${bodyPartText}. What would you like to do?`, actions: [ { id: 'analyze', label: 'Analyze Image' }, { id: 'info', label: 'System Info' } ] });
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
    setShowModalitySelect(false);
    setSessionContext({ fileUploaded: false, analysisComplete: false, lastAnalysis: null, modality: null, bodyPart: null });
    addMessage({ type: 'bot', content: 'Ready for new analysis. Upload a file to continue.', actions: [] });
  };

  const handleExport = () => {
    addMessage({ type: 'bot', content: 'Export functionality coming soon.', actions: [{ id: 'new', label: 'New Analysis' }] });
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
                        <p>{msg.content}</p>
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
                setIsProcessing(true);
                try {
                  const response = await fetch(getApiUrl('/api/process-query'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'text/plain' },
                    body: currentQuery
                  });
                  const data = await response.json();
                  if (data.result?.error) {
                    addMessage({ type: 'bot', content: `Error: ${data.result.error}` });
                  } else {
                    addMessage({ type: 'bot', content: data.result?.answer || JSON.stringify(data.result, null, 2) });
                  }
                } catch (err) {
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
                      <span className="chatbot-preview-file" style={{ position: 'relative', display: 'inline-block' }}>
                        {`Selected: ${uploadedFile.name}`}
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
                          title="Remove file"
                          style={{ marginLeft: 8 }}
                        >
                          &times;
                        </button>
                      </span>
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
