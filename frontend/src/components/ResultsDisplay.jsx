import { useState } from 'react'
import './ResultsDisplay.css'

function ResultsDisplay({ results }) {
  const [activeTab, setActiveTab] = useState('comparison')

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

  const downloadJSON = (data, filename) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="results-display-card">
      <div className="results-header">
        <h2>Results</h2>
        <button
          className="download-btn"
          onClick={() => downloadJSON(results.anonymized, 'anonymized_data.json')}
        >
          Download Anonymized
        </button>
      </div>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'comparison' ? 'active' : ''}`}
          onClick={() => setActiveTab('comparison')}
        >
          Comparison
        </button>
        <button
          className={`tab ${activeTab === 'original' ? 'active' : ''}`}
          onClick={() => setActiveTab('original')}
        >
          Original
        </button>
        <button
          className={`tab ${activeTab === 'anonymized' ? 'active' : ''}`}
          onClick={() => setActiveTab('anonymized')}
        >
          Anonymized
        </button>
        <button
          className={`tab ${activeTab === 'summary' ? 'active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          Summary
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'comparison' && (
          <div className="comparison-view">
            <div className="data-column">
              <h3>Original Data</h3>
              <pre className="data-json">{JSON.stringify(results.original, null, 2)}</pre>
            </div>
            <div className="divider"></div>
            <div className="data-column">
              <h3>Anonymized Data</h3>
              <pre className="data-json">{JSON.stringify(results.anonymized, null, 2)}</pre>
            </div>
          </div>
        )}

        {activeTab === 'original' && (
          <div className="single-view">
            <pre className="data-json">{JSON.stringify(results.original, null, 2)}</pre>
          </div>
        )}

        {activeTab === 'anonymized' && (
          <div className="single-view">
            <pre className="data-json">{JSON.stringify(results.anonymized, null, 2)}</pre>
          </div>
        )}

        {activeTab === 'summary' && (
          <div className="summary-view">
            <div className="summary-section">
              <h3>Anonymization Summary</h3>
              <div className="summary-stats">
                <div className="stat-card">
                  <div className="stat-value">{results.summary?.fieldsRemoved || 0}</div>
                  <div className="stat-label">Fields Removed</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{results.summary?.fieldsGeneralized || 0}</div>
                  <div className="stat-label">Fields Generalized</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{results.summary?.fieldsKept || 0}</div>
                  <div className="stat-label">Fields Kept</div>
                </div>
              </div>

              {results.summary?.changes && results.summary.changes.length > 0 && (
                <div className="changes-list">
                  <h4>Changes Applied:</h4>
                  {results.summary.changes.map((change, index) => (
                    <div key={index} className="change-item">
                      <span className="change-icon">
                        {change.type === 'removed' ? '-' :
                         change.type === 'generalized' ? '~' : '✓'}
                      </span>
                      <span className="change-field">{change.field}</span>
                      <span className="change-description">{change.description}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ResultsDisplay
