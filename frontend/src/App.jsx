import { useState } from 'react'
import WorkflowPanel from './components/WorkflowPanel'
import ResultsDisplay from './components/ResultsDisplay'
import FileUpload from './components/FileUpload'
import { API_CONFIG, getApiUrl } from './config'
import './App.css'

function App() {
  const [workflowSteps, setWorkflowSteps] = useState([])
  const [results, setResults] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)

  const handleStartWorkflow = async () => {
    if (!selectedFile) return
    
    setIsProcessing(true)
    setWorkflowSteps([])
    setResults(null)

    try {
      // Upload the selected file
      const formData = new FormData()
      formData.append('file', selectedFile)
      await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD), {
        method: 'POST',
        body: formData
      })

      // Start the predefined workflow
      const response = await fetch(
        getApiUrl(API_CONFIG.ENDPOINTS.PROCESS_WORKFLOW),
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      
      if (data.result) {
        setResults(data.result)
      } else if (data.error) {
        setResults({ error: data.error })
      } else {
        setResults(data)
      }
      
    } catch (error) {
      console.error('Workflow processing error:', error)
      setResults({ error: error.message })
    } finally {
      setIsProcessing(false)
    }
  }

  const handleFileUpload = (file) => {
    setSelectedFile(file)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agentic Health Assistant</h1>
      </header>

      <div className="app-container">
        <div className="left-panel">
          <div className="upload-section">
            <h2>Medical Image Analysis</h2>
            
            <FileUpload 
              onFileUpload={handleFileUpload}
              isProcessing={isProcessing}
            />
            
            {selectedFile && (
              <div className="selected-file-info">
                <p>Selected: {selectedFile.name}</p>
                <button 
                  className="workflow-btn"
                  onClick={handleStartWorkflow}
                  disabled={isProcessing}
                >
                  {isProcessing ? 'Analyzing Image...' : 'Analyze Image'}
                </button>
              </div>
            )}
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
