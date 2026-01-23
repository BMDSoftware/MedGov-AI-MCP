import { useState } from 'react'
import './ResultsDisplay.css'

function ResultsDisplay({ results }) {
  const [activeTab, setActiveTab] = useState('answer')

  if (!results) {
    return (
      <div className="results-display-card">
        <h2>Results</h2>
        <div className="empty-state">
          <p>Results will appear here after processing</p>
        </div>
      </div>
    )
  }

  // Handle error results
  if (results.error) {
    return (
      <div className="results-display-card">
        <h2>Results</h2>
        <div className="error-state">
          <p className="error-message">Error: {results.error}</p>
        </div>
      </div>
    )
  }

  // Handle new agent response format
  if (results.type === 'agent_response') {
    return (
      <div className="results-display-card">
        <div className="results-header">
          <h2>Agent Response</h2>
          <button
            className="download-btn"
            onClick={() => downloadJSON(results, 'agent_response.json')}
          >
            Download Full Response
          </button>
        </div>

        <div className="agent-response">
          <div className="user-query">
            <h3>Your Question:</h3>
            <p>"{results.original_query}"</p>
          </div>
          
          <div className="agent-answer">
            <h3>Answer:</h3>
            <div className="answer-content">
              {results.answer.split('\n').map((line, index) => (
                <p key={index}>{line}</p>
              ))}
            </div>
          </div>

          {results.tools_used && results.tools_used.length > 0 && (
            <div className="tools-used">
              <h4>Tools Used:</h4>
              <div className="tool-badges">
                {results.tools_used.map((tool, index) => (
                  <span key={index} className="tool-badge">{tool}</span>
                ))}
              </div>
            </div>
          )}

          {results.raw_results && results.raw_results.length > 0 && (
            <div className="raw-data-section">
              <button
                className="toggle-raw-data"
                onClick={() => setActiveTab(activeTab === 'answer' ? 'raw' : 'answer')}
              >
                {activeTab === 'answer' ? 'View Raw Data' : 'Hide Raw Data'}
              </button>
              
              {activeTab === 'raw' && (
                <div className="raw-data">
                  <h4>Raw Tool Results:</h4>
                  {results.raw_results.map((result, index) => (
                    <details key={index} className="raw-result">
                      <summary>{result.tool} - {result.summary}</summary>
                      <pre className="raw-json">{JSON.stringify(result.result, null, 2)}</pre>
                    </details>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  const downloadJSON = (data, filename) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  // Analyze the result structure to provide better display
  const getResultSummary = (data) => {
    if (!data) return null
    
    if (data.resourceType) {
      // FHIR resource
      if (data.resourceType === 'Bundle') {
        const entryCount = data.entry ? data.entry.length : 0
        return {
          type: 'FHIR Bundle',
          details: `Contains ${entryCount} entries`,
          entries: entryCount
        }
      } else if (data.resourceType === 'Patient') {
        return {
          type: 'FHIR Patient',
          details: `Patient ID: ${data.id || 'Unknown'}`,
          name: data.name?.[0] ? `${data.name[0].given?.[0] || ''} ${data.name[0].family || ''}`.trim() : 'Unknown'
        }
      } else {
        return {
          type: `FHIR ${data.resourceType}`,
          details: `ID: ${data.id || 'Unknown'}`,
          id: data.id
        }
      }
    } else if (Array.isArray(data)) {
      return {
        type: 'Array',
        details: `Contains ${data.length} items`,
        count: data.length
      }
    } else if (typeof data === 'object') {
      const keys = Object.keys(data)
      return {
        type: 'Object',
        details: `Contains ${keys.length} properties`,
        properties: keys.slice(0, 5).join(', ') + (keys.length > 5 ? '...' : '')
      }
    }
    
    return {
      type: typeof data,
      details: String(data).substring(0, 100)
    }
  }

  const summary = getResultSummary(results)

  return (
    <div className="results-display-card">
      <div className="results-header">
        <h2>Agent Results</h2>
        <button
          className="download-btn"
          onClick={() => downloadJSON(results, 'agent_results.json')}
        >
          Download JSON
        </button>
      </div>

      {summary && (
        <div className="result-summary">
          <div className="summary-card">
            <h3>{summary.type}</h3>
            <p>{summary.details}</p>
          </div>
        </div>
      )}

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'formatted' ? 'active' : ''}`}
          onClick={() => setActiveTab('formatted')}
        >
          Formatted View
        </button>
        <button
          className={`tab ${activeTab === 'raw' ? 'active' : ''}`}
          onClick={() => setActiveTab('raw')}
        >
          Raw JSON
        </button>
        {results.resourceType === 'Bundle' && (
          <button
            className={`tab ${activeTab === 'entries' ? 'active' : ''}`}
            onClick={() => setActiveTab('entries')}
          >
            Bundle Entries ({results.entry?.length || 0})
          </button>
        )}
      </div>

      <div className="tab-content">
        {activeTab === 'formatted' && (
          <div className="formatted-view">
            {results.resourceType === 'Patient' ? (
              <div className="patient-details">
                <h3>Patient Information</h3>
                <div className="detail-grid">
                  <div className="detail-item">
                    <label>ID:</label>
                    <span>{results.id || 'Unknown'}</span>
                  </div>
                  <div className="detail-item">
                    <label>Name:</label>
                    <span>
                      {results.name?.[0] 
                        ? `${results.name[0].given?.join(' ') || ''} ${results.name[0].family || ''}`.trim()
                        : 'Unknown'
                      }
                    </span>
                  </div>
                  <div className="detail-item">
                    <label>Gender:</label>
                    <span>{results.gender || 'Unknown'}</span>
                  </div>
                  <div className="detail-item">
                    <label>Birth Date:</label>
                    <span>{results.birthDate || 'Unknown'}</span>
                  </div>
                </div>
              </div>
            ) : results.resourceType === 'Bundle' ? (
              <div className="bundle-overview">
                <h3>Bundle Overview</h3>
                <p>Total entries: {results.entry?.length || 0}</p>
                <p>Bundle ID: {results.id || 'Unknown'}</p>
                <p>Type: {results.type || 'Unknown'}</p>
              </div>
            ) : (
              <div className="generic-view">
                <pre className="data-json">{JSON.stringify(results, null, 2)}</pre>
              </div>
            )}
          </div>
        )}

        {activeTab === 'raw' && (
          <div className="single-view">
            <pre className="data-json">{JSON.stringify(results, null, 2)}</pre>
          </div>
        )}

        {activeTab === 'entries' && results.resourceType === 'Bundle' && (
          <div className="entries-view">
            <h3>Bundle Entries</h3>
            {results.entry?.map((entry, index) => (
              <div key={index} className="entry-card">
                <h4>Entry {index + 1}</h4>
                <p><strong>Resource Type:</strong> {entry.resource?.resourceType || 'Unknown'}</p>
                <p><strong>ID:</strong> {entry.resource?.id || 'Unknown'}</p>
                <details>
                  <summary>View Details</summary>
                  <pre className="entry-json">{JSON.stringify(entry, null, 2)}</pre>
                </details>
              </div>
            )) || <p>No entries found</p>}
          </div>
        )}
      </div>
    </div>
  )
}

export default ResultsDisplay
