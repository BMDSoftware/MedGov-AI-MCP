import { useState, useRef } from 'react'
import './FileUpload.css'

function FileUpload({ onFileUpload, isProcessing }) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const fileInputRef = useRef(null)

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
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const handleFile = (file) => {
    setSelectedFile(file)
  }

  const handleUpload = (file) => {
    if (!isProcessing) {
      onFileUpload(file)
    }
  }

  const onButtonClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="file-upload-card">
      <h2>Upload Patient Data</h2>

      <div
        className={`upload-area ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={onButtonClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="file-input"
          onChange={handleChange}
          accept=".jpg,.jpeg,.png"
        />

        {!selectedFile ? (
          <div className="upload-prompt">
            <div className="upload-icon">+</div>
            <p className="upload-text">Drop file here or click to browse</p>
            <p className="upload-subtext">Supports: Images</p>
          </div>
        ) : (
          <div className="file-selected">
            <div className="file-icon">✓</div>
            <div className="file-info">
              <p className="file-name">{selectedFile.name}</p>
              <p className="file-size">{(selectedFile.size / 1024).toFixed(2)} KB</p>
            </div>
          </div>
        )}
      </div>

      <button
        className="upload-button"
        onClick={() => handleUpload(selectedFile)}
        disabled={isProcessing}
      >
        {isProcessing ? 'Processing...' : selectedFile ? 'Anonymize File' : 'Anonymize from FHIR'}
      </button>

      {!selectedFile && (
        <p style={{ textAlign: 'center', marginTop: '1rem', color: '#999', fontSize: '0.9rem' }}>
          Click button to fetch and anonymize a patient from FHIR server
        </p>
      )}
    </div>
  )
}

export default FileUpload
