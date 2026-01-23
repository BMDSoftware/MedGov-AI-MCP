import { useState, useRef } from 'react'
import WorkflowPanel from './components/WorkflowPanel'
import ResultsDisplay from './components/ResultsDisplay'
import { API_CONFIG, getApiUrl } from './config'
import './App.css'

function App() {
  const [workflowSteps, setWorkflowSteps] = useState([])
  const [results, setResults] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [query, setQuery] = useState('')
  const [attachedFile, setAttachedFile] = useState(null)
  const fileInputRef = useRef(null)

  const handleSubmit = async () => {
    if (!query.trim() && !attachedFile) return
    
    setIsProcessing(true)
    setWorkflowSteps([])
    setResults(null)

    try {
      // Upload file if attached
      if (attachedFile) {
        const formData = new FormData()
        formData.append('file', attachedFile)
        await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD), {
          method: 'POST',
          body: formData
        })
      }

      // Process query with regular fetch (matching backend's GET endpoint)
      const response = await fetch(
        `${getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_QUERY)}?query=${encodeURIComponent(query.trim())}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          }
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      
      // Handle the backend response format {"result": result}
      if (data.result) {
        setResults(data.result)
      } else if (data.error) {
        setResults({ error: data.error })
      } else {
        setResults(data)
      }
      
    } catch (error) {
      console.error('Processing error:', error)
      setResults({ error: error.message })
    } finally {
      setIsProcessing(false)
      
      // Clear the attached file after processing
      if (attachedFile) {
        setAttachedFile(null)
      }
    }
  }

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setAttachedFile(e.target.files[0])
    }
  }

  const handleRemoveFile = () => {
    setAttachedFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isProcessing) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agentic Health Assistant</h1>
      </header>

      <div className="app-container">
        <div className="left-panel">
          <div className="query-section">
            <h2>Ask a Question or Upload a File</h2>
            
            {attachedFile && (
              <div className="attached-file">
                <svg className="file-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                </svg>
                <span className="file-name">{attachedFile.name}</span>
                <button 
                  className="remove-file-btn"
                  onClick={handleRemoveFile}
                  disabled={isProcessing}
                  title="Remove file"
                >
                  ✕
                </button>
              </div>
            )}
            
            <div className="query-input-group">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="e.g., Analyze patient data, Get MONAI info, List available tools..."
                disabled={isProcessing}
                rows={3}
              />
              <div className="input-actions">
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileSelect}
                  style={{ display: 'none' }}
                  accept=".json,.dcm,.nii,.nii.gz,.png,.jpg,.jpeg"
                  disabled={isProcessing}
                />
                <button 
                  className="attach-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing}
                  title="Attach file"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                  </svg>
                  Attach
                </button>
                <button 
                  className="submit-btn"
                  onClick={handleSubmit} 
                  disabled={isProcessing || (!query.trim() && !attachedFile)}
                >
                  {isProcessing ? 'Processing...' : 'Submit'}
                </button>
              </div>
            </div>
          </div>
          
          <WorkflowPanel steps={workflowSteps} isProcessing={isProcessing} />
        </div>

        <div className="right-panel">
          <ResultsDisplay results={results} />
        </div>
      </div>
    </div>
  )
}

export default App
