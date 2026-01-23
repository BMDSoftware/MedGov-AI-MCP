import { useState, useRef } from 'react'
import './FileUpload.css'

function FileUpload({ onFileUpload, isProcessing }) {
  const [dragActive, setDragActive] = useState(false)
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
    onFileUpload(file)
  }

  const onButtonClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="file-upload-card">
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
          disabled={isProcessing}
        />

        <div className="upload-prompt">
          <div className="upload-icon"></div>
          <p className="upload-text">Drop medical image here or click to browse</p>
          <p className="upload-subtext">Supports: .jpg, .png, .jpeg</p>
        </div>
      </div>
    </div>
  )
}

export default FileUpload
