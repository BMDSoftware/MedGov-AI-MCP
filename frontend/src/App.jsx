import { useState, useRef, useEffect } from 'react';
import { API_CONFIG, getApiUrl } from './config';
import { isAuthenticated, getToken, getUsername, setAuth, clearAuth } from './auth';
import { apiFetch, safeJson, authEventSourceUrl } from './apiFetch';
import './App.css';
import Login from './components/Login';
import Settings from './components/Settings';
import Sessions from './components/Sessions';
import InferenceTest from './components/InferenceTest';
import Results from './components/Results';
import Report from './components/Report';
import Toast from './components/Toast';
import HomePage from './components/HomePage';
import AutonomousAgent from './components/AutonomousAgent';
import Workspaces from './components/Workspaces';
import NavDock from './components/NavDock';
import { MdHome, MdSmartToy, MdBiotech, MdBarChart, MdDescription, MdFolder, MdSettings, MdHistory, MdScience } from 'react-icons/md';

function App() {
  // ── Auth state ──────────────────────────────────────────────────────────────
  // ALL hooks must be declared here, before any conditional return.
  // Moving them after an early `return` violates the Rules of Hooks and causes
  // React error #310 ("rendered more hooks than previous render").
  const [authToken, setAuthToken] = useState(getToken());
  const [currentUsername, setCurrentUsername] = useState(getUsername());
  const [showLogin, setShowLogin] = useState(false);

  // --- State and refs ---
  const [page, setPage] = useState('analysis');
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      content: 'Welcome to the Health Assistant. You can select a patient from the Patients tab or upload a medical file to begin.',
      actions: []
    }
  ]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]); // [{name, file, fileType}]
  const [uploadedDirs, setUploadedDirs] = useState([]);   // [{name, path}]
  const [dragActive, setDragActive] = useState(false);
  const [sessionContext, setSessionContext] = useState({
    fileUploaded: false,
    analysisComplete: false,
    lastAnalysis: null,
    modality: null,
    bodyPart: null,
    selectedPatient: null,
    patientContext: null
  });
  const [userQuery, setUserQuery] = useState("");
  const [pendingTool, setPendingTool] = useState(null); // {tool_name, arguments}
  const [runningTool, setRunningTool] = useState(null); // tool currently executing
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [taskRefreshSignal, setTaskRefreshSignal] = useState(null);
  const [runningTaskCount, setRunningTaskCount] = useState(0);
  const [unreadTaskCount, setUnreadTaskCount] = useState(0);
  const [appMode, setAppMode] = useState('debug'); // 'normal' | 'debug'
  const pageRef = useRef(page);
  const [uploadingDir, setUploadingDir] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // --- Auth functions ---
  const WELCOME_MESSAGE = {
    type: 'bot',
    content: 'Welcome to the Health Assistant. You can select a patient from the Patients tab or upload a medical file to begin.',
    actions: []
  };

  function resetChatState() {
    setMessages([WELCOME_MESSAGE]);
    setCurrentSessionId(null);
    setUploadedFiles([]);
    setUploadedDirs([]);
    setSessionContext({ fileUploaded: false, analysisComplete: false, lastAnalysis: null, modality: null, bodyPart: null, selectedPatient: null, patientContext: null });
    setSelectedPatient(null);
    setPendingTool(null);
    setRunningTool(null);
    setRunningTaskCount(0);
    setUnreadTaskCount(0);
  }

  function handleLogin(token, username) {
    setAuth(token, username);
    resetChatState();
    setAuthToken(token);
    setCurrentUsername(username);
    setShowLogin(false);
    setPage('analysis');
  }

  function handleLogout() {
    clearAuth();
    resetChatState();
    setAuthToken(null);
    setCurrentUsername(null);
    setShowLogin(false);
    setPage('analysis');
  }

  // --- Effects (all gated on authToken to avoid 401 loops) ---
  useEffect(() => {
    if (!authToken) return;
    pageRef.current = page;
    if (page === 'results') setUnreadTaskCount(0);

    if (page === 'autonomous') {
      apiFetch(getApiUrl('/api/change-agent-type'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify('autonomous')
      }).catch(() => {});
    } else if (page === 'analysis') {
      apiFetch(getApiUrl('/api/change-agent-type'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify('analysis')
      }).catch(() => {});
    }
  }, [page, authToken]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Fetch initial session ID on mount (auth required)
  useEffect(() => {
    if (!authToken) return;
    apiFetch(getApiUrl('/api/sessions'))
      .then(r => r.json())
      .then(d => setCurrentSessionId(d.current_session_id))
      .catch(() => {});
  }, [authToken]);

  // Load app mode on mount (auth required)
  useEffect(() => {
    if (!authToken) return;
    apiFetch(getApiUrl('/api/mode'))
      .then(r => r.json())
      .then(d => setAppMode(d.mode))
      .catch(() => {});
  }, [authToken]);

  // Initialise running task count from DB on mount (auth required)
  useEffect(() => {
    if (!authToken) return;
    apiFetch(getApiUrl('/api/tasks'))
      .then(r => r.json())
      .then(d => {
        const active = (d.tasks || []).filter(t => t.status === 'queued' || t.status === 'running').length;
        setRunningTaskCount(active);
      })
      .catch(() => {});
  }, [authToken]);

  // Persist messages to localStorage whenever they change (filter out transient states)
  useEffect(() => {
    if (!currentSessionId) return;
    const toSave = messages.filter(m => !m.isLoading);
    localStorage.setItem(`messages_${currentSessionId}`, JSON.stringify(toSave));
  }, [messages, currentSessionId]);

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
    if (e.target.files) {
      Array.from(e.target.files).forEach(f => handleFileUpload(f));
    }
  };

  const handleFileUpload = async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiFetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD), {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error('Upload failed');
      setUploadedFiles(prev => [...prev, { name: file.name, file, fileType: file.type }]);
      setSessionContext(prev => ({ ...prev, fileUploaded: true }));
    } catch (error) {
      addMessage({ type: 'bot', content: `Upload error: ${error.message}` });
    }
  };

  const handleChatDirectoryUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploadingDir(true);
    try {
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i], files[i].webkitRelativePath || files[i].name);
      }
      const res = await apiFetch(getApiUrl('/api/upload-directory'), { method: 'POST', body: formData });
      const data = await res.json();
      if (data.dir_path) {
        await apiFetch(getApiUrl('/api/set-directory'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dir_path: data.dir_path }),
        });
        const shortName = data.dirname.length > 24
          ? `${data.dirname.slice(0, 12)}\u2026${data.dirname.slice(-8)}`
          : data.dirname;
        setUploadedDirs(prev => [...prev, { name: `${shortName} (${data.file_count})`, path: data.dir_path }]);
      } else {
        addMessage({ type: 'bot', content: `Directory upload failed: ${data.detail || 'unknown error'}` });
      }
    } catch {
      addMessage({ type: 'bot', content: 'Directory upload failed.' });
    }
    setUploadingDir(false);
  };

  const handleRemoveDir = async (dirPath) => {
    await apiFetch(getApiUrl('/api/set-directory'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir_path: dirPath, remove: true }),
    }).catch(() => {});
    setUploadedDirs(prev => prev.filter(d => d.path !== dirPath));
  };

  const handleRemoveFile = async (fileName) => {
    try {
      await apiFetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD) + `?filename=${encodeURIComponent(fileName)}`, {
        method: 'DELETE'
      });
    } catch {}
    setUploadedFiles(prev => prev.filter(f => f.name !== fileName));
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
    const response = await apiFetch(getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_WORKFLOW), {
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
    const response = await apiFetch(getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_WORKFLOW), {
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
      const response = await apiFetch(getApiUrl('/api/confirm-tool'), { method: 'POST' });
      const text = await response.text();
      const jsonLine = text.split('\n').filter(l => l.trim() && !l.startsWith(':')).pop();
      const data = jsonLine ? JSON.parse(jsonLine) : { result: { error: 'Empty response' } };
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
      const response = await apiFetch(getApiUrl('/api/deny-tool'), { method: 'POST' });
      const data = await safeJson(response);
      addMessage({ type: 'bot', content: data.result?.answer || 'Tool execution cancelled.' });
    } catch (err) {
      addMessage({ type: 'bot', content: 'Tool execution cancelled.' });
    }
  };

  // --- Render ---
  // ── Unauthenticated views (no hooks after this point) ──────────────────────
  if (!authToken) {
    if (showLogin) return <Login onLogin={handleLogin} />;
    return (
      <HomePage
        onNavigate={(p) => {
          if (p === 'analysis' || p === 'autonomous' || p === 'results') {
            setShowLogin(true);
          }
        }}
        onSignIn={() => setShowLogin(true)}
        currentSessionId={null}
        runningTaskCount={0}
        isPublic
      />
    );
  }

  return (
    <div className="app">
      {/* Global SSE toast notifications - lives outside tab routing */}
      <Toast authToken={authToken} onTaskUpdate={(event) => {
        setTaskRefreshSignal(event);
        if (event.type === 'task_queued') setRunningTaskCount(n => n + 1);
        if (event.type === 'task_done' || event.type === 'task_failed' || event.type === 'task_cancelled') {
          setRunningTaskCount(n => Math.max(0, n - 1));
          if (pageRef.current !== 'results') setUnreadTaskCount(n => n + 1);
        }
      }} />

      {page !== 'home' && <aside className="sidebar">
        <div className="logo" style={{ cursor: 'pointer' }} onClick={() => setPage('home')}>
          <span className="logo-icon">H</span>
          <span className="logo-text">HealthMCP</span>
        </div>
        <nav className="nav">
          <NavDock
            activePage={page}
            items={[
              { page: 'home',       label: 'Home',       icon: <MdHome />,      onClick: () => setPage('home') },
              { page: 'autonomous', label: 'Autonomous', icon: <MdSmartToy />,  onClick: () => setPage('autonomous') },
              { page: 'analysis',   label: 'Analysis',   icon: <MdBiotech />,   onClick: () => setPage('analysis') },
              { page: 'results',    label: 'Results',    icon: <MdBarChart />,  onClick: () => setPage('results'), badge: runningTaskCount, unread: unreadTaskCount > 0 },
              { page: 'workspaces', label: 'Workspaces', icon: <MdFolder />,    onClick: () => setPage('workspaces') },
              { page: 'settings',   label: 'Settings',   icon: <MdSettings />,  onClick: () => setPage('settings') },
              ...(appMode === 'debug' ? [
                { page: 'history', label: 'Sessions', icon: <MdHistory />,     onClick: () => setPage('history') },
                { page: 'test',    label: 'Test',     icon: <MdScience />,     onClick: () => setPage('test') },
                { page: 'report',  label: 'Report',   icon: <MdDescription />, onClick: () => setPage('report') },
              ] : []),
            ]}
          />
        </nav>
        <div className="sidebar-footer">
          {currentUsername && (
            <div className="sidebar-user">
              <span className="sidebar-username">{currentUsername}</span>
              <button className="sidebar-logout" onClick={handleLogout}>Sign out</button>
            </div>
          )}
          {appMode === 'debug' && (
            <div className="sidebar-debug-badge">DEBUG</div>
          )}
          <p className="version">v1.0.0</p>
        </div>
      </aside>}

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

        {page !== 'home' && (
        <header className="header">
          <h1>Medical Image Analysis</h1>
          {selectedPatient ? (
            <p>Healthcare Agent for <strong>{selectedPatient.name}</strong> ({selectedPatient.gender}, Born: {selectedPatient.birthDate})</p>
          ) : (
            <p>Multi-Agent Orchestrator for Healthcare</p>
          )}

          {runningTaskCount > 0 && (
            <div className="header-task-indicator">
              <span className="header-task-dot" />
              {runningTaskCount} task{runningTaskCount > 1 ? 's' : ''} running in background
            </div>
          )}
        </header>
        )}

        {page === 'home' ? (
          <HomePage
            onNavigate={setPage}
            currentSessionId={currentSessionId}
            runningTaskCount={runningTaskCount}
          />
        ) : page === 'autonomous' ? (
          <AutonomousAgent currentSessionId={currentSessionId} />
        ) : page === 'settings' ? (
          <Settings onModeChange={setAppMode} />
        ) : page === 'test' ? (
          <InferenceTest />
        ) : page === 'results' ? (
          <Results refreshSignal={taskRefreshSignal} currentSessionId={currentSessionId} />
        ) : page === 'report' ? (
          <Report refreshSignal={taskRefreshSignal} currentSessionId={currentSessionId} />
        ) : page === 'workspaces' ? (
          <Workspaces appMode={appMode} />
        ) : page === 'history' ? (
          <Sessions onLoadSession={(data) => {
            if (!data) return;
            if (data.isNew) {
              // New session created - clear everything
              setCurrentSessionId(data.session_id);
              setMessages([{
                type: 'bot',
                content: 'New session started. Select a patient or upload a file to begin.',
                actions: []
              }]);
              setSelectedPatient(null);
              setUploadedFiles([]);
              setUploadedDirs([]);
              setSessionContext({ fileUploaded: false, analysisComplete: false, lastAnalysis: null, modality: null, bodyPart: null, selectedPatient: null, patientContext: null });
            } else {
              // Existing session loaded - restore chat history
              setCurrentSessionId(data.session_id);
              // Prefer messages from DB (returned by load-session), fall back to localStorage
              if (data.messages && data.messages.length > 0) {
                const restored = data.messages.map(m => ({
                  type: m.role === 'user' ? 'user' : 'bot',
                  content: m.content,
                  actions: []
                }));
                setMessages(restored);
              } else {
                const saved = localStorage.getItem(`messages_${data.session_id}`);
                if (saved) {
                  try {
                    setMessages(JSON.parse(saved));
                  } catch {
                    setMessages([{ type: 'bot', content: `Session "${data.name}" loaded.`, actions: [] }]);
                  }
                } else {
                  setMessages([{ type: 'bot', content: `Session "${data.name}" loaded. No previous chat history found.`, actions: [] }]);
                }
              }
              // Restore uploaded directories from session
              const dirEntries = (data.files || []).filter(f => f.file_type === 'dicom_dir');
              setUploadedDirs(dirEntries.map(f => ({ name: f.original_name, path: f.stored_path })));
              setUploadedFiles([]);
            }
            setPage('analysis');
          }} />
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
              <form className="chatbot-input-row" onSubmit={async e => {
                e.preventDefault();
                if (!userQuery.trim()) return;
                const currentQuery = userQuery;
                setUserQuery("");
                addMessage({ type: 'user', content: currentQuery });
                addMessage({ type: 'bot', content: '', isLoading: true });
                setIsProcessing(true);
                try {
                  const response = await apiFetch(getApiUrl('/api/process-query'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'text/plain' },
                    body: currentQuery
                  });
                  // Response is ndjson: keepalive comment lines followed by one JSON line.
                  const text = await response.text();
                  const jsonLine = text.split('\n').filter(l => l.trim() && !l.startsWith(':')).pop();
                  if (!jsonLine) throw new Error('Empty response from server');
                  let data;
                  try { data = JSON.parse(jsonLine); }
                  catch { throw new Error(`Unexpected response: ${jsonLine.slice(0, 120)}`); }

                  setMessages(prev => prev.filter(m => !m.isLoading));

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
                {/* Attachment strip — only shown when something is attached */}
                {(uploadedFiles.length > 0 || uploadedDirs.length > 0) && (
                  <div className="attachment-strip">
                    {uploadedDirs.map(d => (
                      <div key={d.path} className="attachment-chip dir-chip" title={d.name}>
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                        <span className="attachment-chip-name">{d.name}</span>
                        <button type="button" className="attachment-chip-remove" onClick={() => handleRemoveDir(d.path)}>×</button>
                      </div>
                    ))}
                    {uploadedFiles.map(f => (
                      <div key={f.name} className="attachment-chip file-chip" title={f.name}>
                        {f.fileType && f.fileType.startsWith('image/') ? (
                          <img src={URL.createObjectURL(f.file)} alt="" className="attachment-chip-thumb" />
                        ) : (
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                          </svg>
                        )}
                        <span className="attachment-chip-name">{f.name}</span>
                        <button type="button" className="attachment-chip-remove" onClick={() => handleRemoveFile(f.name)}>×</button>
                      </div>
                    ))}
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
                    multiple
                    onChange={handleFileSelect}
                  />
                  <label htmlFor="fileInput" className="chatbot-file-label" title="Attach files">
                    <svg width="22" height="22" fill="none" stroke="#6366f1" strokeWidth="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
                  </label>
                  <input
                    type="file"
                    id="dirInput"
                    className="chatbot-file-input"
                    webkitdirectory=""
                    directory=""
                    onChange={handleChatDirectoryUpload}
                    disabled={uploadingDir}
                  />
                  <label htmlFor="dirInput" className="chatbot-file-label" title="Attach directory" style={{ opacity: uploadingDir ? 0.5 : 1 }}>
                    <svg width="22" height="22" fill="none" stroke="#10b981" strokeWidth="2" viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
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
