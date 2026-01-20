import { useState } from 'react'
import FileUpload from './components/FileUpload'
import WorkflowPanel from './components/WorkflowPanel'
import ResultsDisplay from './components/ResultsDisplay'
import './App.css'

function App() {
  const [workflowSteps, setWorkflowSteps] = useState([])
  const [results, setResults] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)

  const handleFileUpload = async (file) => {
    setIsProcessing(true)
    setWorkflowSteps([])
    setResults(null)

    const filename = file ? file.name : 'sample-patient.json'

    try {
      if (file) {
        const formData = new FormData()
        formData.append('file', file)
        await fetch('/api/upload', {
          method: 'POST',
          body: formData
        })
      }

      const eventSource = new EventSource(`/api/anonymize-stream?filename=${encodeURIComponent(filename)}`)

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data)

        if (data.type === 'step') {
          setWorkflowSteps(prev => [...prev, data])
        } else if (data.type === 'result') {
          setResults(data.payload)
          setIsProcessing(false)
          eventSource.close()
        } else if (data.type === 'error') {
          console.error('Error:', data.message)
          setIsProcessing(false)
          eventSource.close()
        }
      }

      eventSource.onerror = () => {
        setIsProcessing(false)
        eventSource.close()
      }
    } catch (error) {
      console.error('Upload error:', error)
      setIsProcessing(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agentic Health Smart Anonymizer (attempt)</h1>
      </header>

      <div className="app-container">
        <div className="left-panel">
          <FileUpload onFileUpload={handleFileUpload} isProcessing={isProcessing} />
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
