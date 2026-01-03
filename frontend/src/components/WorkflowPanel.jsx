import { useEffect, useRef } from 'react'
import './WorkflowPanel.css'

function WorkflowPanel({ steps, isProcessing }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [steps])

  const renderStep = (step, index) => {
    switch (step.stepType) {
      case 'thinking':
        return (
          <div key={index} className="workflow-step thinking">
            <div className="step-icon">•</div>
            <div className="step-content">
              <div className="step-title">AI Thinking</div>
              <div className="step-message">{step.message}</div>
            </div>
          </div>
        )

      case 'tool_call':
        return (
          <div key={index} className="workflow-step tool-call">
            <div className="step-icon">→</div>
            <div className="step-content">
              <div className="step-title">
                Tool: <code>{step.toolName}</code>
              </div>
              <div className="step-message">{step.message}</div>
              {step.arguments && (
                <details className="step-details">
                  <summary>Arguments</summary>
                  <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
                </details>
              )}
            </div>
          </div>
        )

      case 'tool_result':
        return (
          <div key={index} className="workflow-step tool-result">
            <div className="step-icon">✓</div>
            <div className="step-content">
              <div className="step-title">Tool Result</div>
              <div className="step-message success">{step.message}</div>
              {step.result && (
                <details className="step-details">
                  <summary>Result</summary>
                  <pre>{JSON.stringify(step.result, null, 2)}</pre>
                </details>
              )}
            </div>
          </div>
        )

      case 'anonymization':
        return (
          <div key={index} className="workflow-step anonymization">
            <div className="step-icon">*</div>
            <div className="step-content">
              <div className="step-title">Anonymization Applied</div>
              <div className="step-message">{step.message}</div>
              {step.fields && (
                <div className="anonymized-fields">
                  {step.fields.map((field, i) => (
                    <span key={i} className="field-badge">{field}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )

      case 'info':
        return (
          <div key={index} className="workflow-step info">
            <div className="step-icon">i</div>
            <div className="step-content">
              <div className="step-message">{step.message}</div>
            </div>
          </div>
        )

      default:
        return (
          <div key={index} className="workflow-step">
            <div className="step-content">
              <div className="step-message">{step.message}</div>
            </div>
          </div>
        )
    }
  }

  return (
    <div className="workflow-panel-card">
      <h2>Workflow Steps</h2>

      <div className="workflow-steps">
        {steps.length === 0 && !isProcessing ? (
          <div className="empty-state">
            <p>Upload a file to see the AI workflow in action</p>
          </div>
        ) : (
          <>
            {steps.map((step, index) => renderStep(step, index))}
            {isProcessing && (
              <div className="workflow-step processing">
                <div className="step-icon spinner">...</div>
                <div className="step-content">
                  <div className="step-message">Processing...</div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </>
        )}
      </div>
    </div>
  )
}

export default WorkflowPanel
