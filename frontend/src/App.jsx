import { useState, useRef, useEffect } from 'react'
import { API_CONFIG, getApiUrl } from './config'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      content: 'Welcome to the Health Assistant. Upload a medical file to begin.',
      actions: []
    }
  ])
  const [isProcessing, setIsProcessing] = useState(false)
  const [uploadedFile, setUploadedFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [sessionContext, setSessionContext] = useState({
    fileUploaded: false,
    analysisComplete: false,
    lastAnalysis: null
  })
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const addMessage = (message) => {
    setMessages(prev => [...prev, message])
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0])
    }
  }

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0])
    }
  }

  const handleFileUpload = async (file) => {
    setUploadedFile(file)
    addMessage({ type: 'user', content: `File: ${file.name}` })
    setIsProcessing(true)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD), {
        method: 'POST',
        body: formData
      })

      if (!response.ok) throw new Error('Upload failed')

      setSessionContext(prev => ({ ...prev, fileUploaded: true }))
      addMessage({
        type: 'bot',
        content: `File "${file.name}" received. What would you like to do?`,
        actions: [
          { id: 'analyze', label: 'Analyze Image' },
          { id: 'info', label: 'System Info' }
        ]
      })
    } catch (error) {
      addMessage({
        type: 'bot',
        content: `Upload error: ${error.message}`,
        actions: []
      })
    } finally {
      setIsProcessing(false)
    }
  }

  const handleAction = async (actionId) => {
    const labels = {
      'analyze': 'Analyze Image',
      'info': 'System Info',
      'report': 'Generate Report',
      'new': 'New Analysis',
      'export': 'Export'
    }
    addMessage({ type: 'user', content: labels[actionId] || actionId })
    setIsProcessing(true)

    try {
      if (actionId === 'analyze') await handleAnalyze()
      else if (actionId === 'info') await handleGetInfo()
      else if (actionId === 'report') await handleGenerateReport()
      else if (actionId === 'new') handleNewAnalysis()
      else if (actionId === 'export') handleExport()
    } catch (error) {
      addMessage({
        type: 'bot',
        content: `Error: ${error.message}`,
        actions: sessionContext.fileUploaded ? [{ id: 'analyze', label: 'Retry' }] : []
      })
    } finally {
      setIsProcessing(false)
    }
  }

  const handleAnalyze = async () => {
    addMessage({ type: 'bot', content: 'Analyzing image...', isLoading: true })

    const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_WORKFLOW), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'analyze' })
    })

    if (!response.ok) throw new Error('Analysis failed')
    const data = await response.json()
    setMessages(prev => prev.filter(m => !m.isLoading))

    let result = 'Analysis complete.\n\n'
    if (data.result?.answer) result += data.result.answer
    else if (data.result?.error) result += `Error: ${data.result.error}`
    else result += JSON.stringify(data.result, null, 2)

    setSessionContext(prev => ({ ...prev, analysisComplete: true, lastAnalysis: data.result }))
    addMessage({
      type: 'bot',
      content: result,
      actions: [
        { id: 'report', label: 'Generate Report' },
        { id: 'new', label: 'New Analysis' },
        { id: 'export', label: 'Export' }
      ]
    })
  }

  const handleGetInfo = async () => {
    addMessage({ type: 'bot', content: 'Loading system info...', isLoading: true })
    await new Promise(r => setTimeout(r, 500))
    setMessages(prev => prev.filter(m => !m.isLoading))
    addMessage({
      type: 'bot',
      content: 'Available services:\n\n- MONAI: Medical image analysis\n- RadLex: Radiology terminology\n- FHIR: Patient data (if configured)',
      actions: [{ id: 'analyze', label: 'Analyze Image' }]
    })
  }

  const handleGenerateReport = async () => {
    addMessage({ type: 'bot', content: 'Generating report...', isLoading: true })

    const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_WORKFLOW), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'generate_report', analysis: sessionContext.lastAnalysis })
    })

    setMessages(prev => prev.filter(m => !m.isLoading))

    if (response?.ok) {
      const data = await response.json()
      addMessage({
        type: 'bot',
        content: `Report:\n\n${data.result?.report || data.result?.answer || 'Report not available'}`,
        actions: [{ id: 'export', label: 'Export PDF' }, { id: 'new', label: 'New Analysis' }]
      })
    } else {
      addMessage({
        type: 'bot',
        content: 'Report generation not available. RadLex MCP server needs to be configured.',
        actions: [{ id: 'new', label: 'New Analysis' }]
      })
    }
  }

  const handleNewAnalysis = () => {
    setUploadedFile(null)
    setSessionContext({ fileUploaded: false, analysisComplete: false, lastAnalysis: null })
    addMessage({ type: 'bot', content: 'Ready for new analysis. Upload a file to continue.', actions: [] })
  }

  const handleExport = () => {
    addMessage({
      type: 'bot',
      content: 'Export functionality coming soon.',
      actions: [{ id: 'new', label: 'New Analysis' }]
    })
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">+</span>
          <span className="logo-text">Health AI</span>
        </div>
        <nav className="nav">
          <a href="#" className="nav-item active">Analysis</a>
          <a href="#" className="nav-item">History</a>
          <a href="#" className="nav-item">Settings</a>
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
            {!sessionContext.fileUploaded ? (
              <div
                className={`dropzone ${dragActive ? 'active' : ''}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileSelect}
                  accept=".jpg,.jpeg,.png,.dcm,.nii,.nii.gz"
                  hidden
                />
                <div className="dropzone-content">
                  <span className="dropzone-icon">+</span>
                  <p>Drop file here or click to browse</p>
                  <small>JPG, PNG, DICOM, NIfTI</small>
                </div>
              </div>
            ) : (
              <div className="file-info">
                <span>{uploadedFile?.name}</span>
                <button onClick={handleNewAnalysis} disabled={isProcessing}>Change file</button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
