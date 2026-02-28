import React, { useState, useRef, useEffect } from 'react';
import { API_CONFIG, getApiUrl } from '../config';
import './AutonomousAgent.css';

const AutonomousAgent = ({ currentSessionId }) => {
  const [dragActive, setDragActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activities, setActivities] = useState([]); 
  const [pendingTool, setPendingTool] = useState(null);
  const [taskQueue, setTaskQueue] = useState([]);
  const activitiesEndRef = useRef(null);

  useEffect(() => {
    activitiesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activities]);

  const enqueueTask = (task) => {
    setTaskQueue(prev => [...prev, task]);
  };

  const addActivity = (type, content, extra = null) => {
    setActivities(prev => [...prev, {
      id: Date.now() + Math.random(),
      type,
      content,
      timestamp: new Date().toLocaleTimeString(),
      ...extra
    }]);
  };

  const isMedicalImage = (fileName) => {
    const allowedExtensions = ['.jpg', '.jpeg', '.png', '.dcm', '.nii', '.nii.gz'];
    const name = fileName.toLowerCase();
    return allowedExtensions.some(ext => name.endsWith(ext));
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  // Helper to recursively get files from directory entries
  const getFilesFromEntry = async (entry) => {
    const files = [];
    if (entry.isFile) {
      const file = await new Promise((resolve) => entry.file(resolve));
      // We need to preserve the relative path for directory uploads to work correctly on backend
      // WebkitRelativePath is read-only, so we might need to handle this differently if the backend expects it.
      // However, for dropped files, we can't easily set webkitRelativePath.
      // The backend /api/upload-directory expects 'files' with paths.
      Object.defineProperty(file, 'fullPath', {
        value: entry.fullPath,
        writable: false
      });
      files.push(file);
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      const entries = await new Promise((resolve) => {
        const allEntries = [];
        const readAll = () => {
          reader.readEntries((results) => {
            if (results.length) {
              allEntries.push(...results);
              readAll();
            } else {
              resolve(allEntries);
            }
          });
        };
        readAll();
      });
      for (const childEntry of entries) {
        files.push(...(await getFilesFromEntry(childEntry)));
      }
    }
    return files;
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const items = e.dataTransfer.items;
    if (items) {
      const filesToUpload = [];
      const entries = [];
      
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
          const entry = item.webkitGetAsEntry();
          if (entry) entries.push(entry);
        }
      }

      if (entries.length > 0) {
        // If the first entry is a directory, handle as directory upload
        if (entries[0].isDirectory) {
          const allFiles = await getFilesFromEntry(entries[0]);
          const validFiles = allFiles.filter(f => isMedicalImage(f.name));
          if (validFiles.length > 0) {
            enqueueTask({ id: Date.now() + Math.random(), type: 'directory', files: validFiles, name: entries[0].name });
          } else {
            addActivity('error', `Directory "${entries[0].name}" contains no valid medical images.`);
          }
        } else {
          // It's a single file
          const file = await new Promise(res => entries[0].file(res));
          if (isMedicalImage(file.name)) {
            enqueueTask({ id: Date.now() + Math.random(), type: 'file', file, name: file.name });
          } else {
            addActivity('error', `File "${file.name}" is not a supported medical image.`);
          }
        }
      }
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (isMedicalImage(file.name)) {
        enqueueTask({ id: Date.now() + Math.random(), type: 'file', file, name: file.name });
      } else {
        addActivity('error', `File "${file.name}" is not a supported medical image.`);
      }
    }
  };

  const handleDirectorySelect = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const allFiles = Array.from(files);
      const validFiles = allFiles.filter(f => isMedicalImage(f.name));
      const dirName = files[0].webkitRelativePath.split('/')[0];
      
      if (validFiles.length > 0) {
        enqueueTask({ id: Date.now() + Math.random(), type: 'directory', files: validFiles, name: dirName });
      } else {
        addActivity('error', `Directory "${dirName}" contains no supported medical images.`);
      }
    }
  };

  // Process task queue
  useEffect(() => {
    const processQueue = async () => {
      if (!isProcessing && !pendingTool && taskQueue.length > 0) {
        const nextTask = taskQueue[0];
        setTaskQueue(prev => prev.slice(1));
        setIsProcessing(true); // Prevent picking another task immediately
        
        try {
          // Reset session context exactly when picking from queue
          await fetch(getApiUrl('/api/reset-session'), { method: 'POST' });

          if (nextTask.type === 'file') {
            handleFileUpload(nextTask.file);
          } else if (nextTask.type === 'directory') {
            handleDirectoryUpload(nextTask.files, nextTask.name);
          }
        } catch (error) {
          addActivity('error', `Failed to initialize task: ${error.message}`);
          setIsProcessing(false);
        }
      }
    };
    
    processQueue();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isProcessing, pendingTool, taskQueue.length]);

  const handleFileUpload = async (file) => {
    addActivity('info', `Uploading file: ${file.name}...`);
    setIsProcessing(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const uploadRes = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD), {
        method: 'POST',
        body: formData
      });

      if (!uploadRes.ok) throw new Error('Failed to upload file');
      
      addActivity('success', `File ${file.name} uploaded successfully.`);
      startAutonomousWorkflow(file.name, 'file');

    } catch (error) {
      addActivity('error', `Upload error: ${error.message}`);
      setIsProcessing(false);
    }
  };

  const handleDirectoryUpload = async (files, dirName) => {
    addActivity('info', `Uploading directory: ${dirName} (${files.length} files)...`);
    setIsProcessing(true);

    try {
      const formData = new FormData();
      files.forEach(file => {
        // Use fullPath if available (from drop), otherwise webkitRelativePath (from input)
        const path = file.fullPath ? file.fullPath.substring(1) : file.webkitRelativePath;
        formData.append('files', file, path || file.name);
      });

      const res = await fetch(getApiUrl('/api/upload-directory'), {
        method: 'POST',
        body: formData
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Directory upload failed');

      // Set the directory for analysis
      await fetch(getApiUrl('/api/set-directory'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dir_path: data.dir_path }),
      });

      addActivity('success', `Directory ${dirName} uploaded and indexed successfully.`);
      startAutonomousWorkflow(dirName, 'directory', data.dir_path);

    } catch (error) {
      addActivity('error', `Directory upload error: ${error.message}`);
      setIsProcessing(false);
    }
  };

  const startAutonomousWorkflow = async (name, type, path = null) => {
    const typeLabel = type === 'directory' ? 'directory' : 'file';
    addActivity('info', `Agent is analyzing ${typeLabel} "${name}" to determine the best course of action...`);
    
    try {
      const query = type === 'directory' 
        ? `A new directory named "${name}" containing medical data has been uploaded and set as the current working directory (Path: ${path}). Please analyze its contents and autonomously perform any necessary medical workflows, such as DICOM analysis or report extraction. Explain your findings.`
        : `A new file named "${name}" has been uploaded. Please analyze it and autonomously perform any necessary medical workflows or extraction you think is best. Explain your findings.`;
      
      const response = await fetch(getApiUrl('/api/process-query'), {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: query
      });
      
      const data = await response.json();

      if (data.result?.type === 'confirmation_required') {
        setPendingTool({
          tool_name: data.result.tool_name,
          arguments: data.result.arguments
        });
        addActivity('action', `Agent wants to execute: ${data.result.tool_name}`, { toolData: data.result });
        setIsProcessing(false);
        return;
      }

      if (data.result?.error) {
        addActivity('error', `Agent encountered an error: ${data.result.error}`);
      } else {
        addActivity('success', `Agent completed task:\n${data.result?.answer || JSON.stringify(data.result, null, 2)}`);
      }
    } catch (err) {
      addActivity('error', `Agent workflow failed: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleConfirmTool = async () => {
    if (!pendingTool) return;
    addActivity('info', `Confirmed execution of ${pendingTool.tool_name}...`);
    setPendingTool(null);
    setIsProcessing(true);

    try {
      const response = await fetch(getApiUrl('/api/confirm-tool'), { method: 'POST' });
      const data = await response.json();
      
      if (data.result?.type === 'confirmation_required') {
        setPendingTool({
          tool_name: data.result.tool_name,
          arguments: data.result.arguments
        });
        addActivity('action', `Agent wants to execute next step: ${data.result.tool_name}`, { toolData: data.result });
      } else if (data.result?.error) {
        addActivity('error', `Tool error: ${data.result.error}`);
      } else {
        addActivity('success', `Tool completed:\n${data.result?.answer || JSON.stringify(data.result, null, 2)}`);
      }
    } catch (err) {
      addActivity('error', `Execution failed: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDenyTool = async () => {
    if (!pendingTool) return;
    addActivity('info', `Denied execution of ${pendingTool.tool_name}.`);
    setPendingTool(null);
    setIsProcessing(true);

    try {
      const response = await fetch(getApiUrl('/api/deny-tool'), { method: 'POST' });
      const data = await response.json();
      addActivity('info', `Agent response after denial:\n${data.result?.answer || 'Tool execution cancelled.'}`);
    } catch (err) {
      addActivity('error', `Failed to cancel tool.`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="autonomous-container">
      <div 
        className={`autonomous-dropzone ${dragActive ? "drag-active" : ""}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="dropzone-content">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <h3>Drop files or folders here</h3>
          <p>The agent will automatically process the data autonomously.</p>
          
          <div className="dropzone-buttons">
            <input
              type="file"
              id="autoFileInput"
              className="hidden-file-input"
              accept=".jpg,.jpeg,.png,.dcm,.nii,.nii.gz"
              onChange={handleFileSelect}
            />
            <label htmlFor="autoFileInput" className="browse-btn">
              Browse Files
            </label>

            <input
              type="file"
              id="autoDirInput"
              className="hidden-file-input"
              webkitdirectory=""
              directory=""
              onChange={handleDirectorySelect}
            />
            <label htmlFor="autoDirInput" className="browse-btn secondary">
              Browse Folders
            </label>
          </div>
        </div>
        
        {isProcessing && !pendingTool && (
          <div className="processing-indicator">
            <div className="spinner"></div>
            <span>Agent is working...</span>
          </div>
        )}
      </div>

      <div className="autonomous-panels">
        <div className="autonomous-log">
          <h3 className="log-header">Agent Activity Log</h3>
          <div className="log-entries">
            {activities.length === 0 ? (
              <div className="log-empty">Waiting for files or folders to begin...</div>
            ) : (
              activities.map(act => (
                <div key={act.id} className={`log-entry ${act.type}`}>
                  <span className="log-time">[{act.timestamp}]</span>
                  <div className="log-content-wrapper">
                    <span className="log-text">{act.content}</span>
                    {act.type === 'action' && pendingTool?.tool_name === act.toolData?.tool_name && (
                      <div className="tool-confirmation">
                        <div className="tool-args">
                          <pre>{JSON.stringify(act.toolData.arguments, null, 2)}</pre>
                        </div>
                        <div className="tool-actions">
                          <button onClick={handleConfirmTool} className="btn-confirm" disabled={isProcessing}>✓ Run Task</button>
                          <button onClick={handleDenyTool} className="btn-deny" disabled={isProcessing}>✗ Skip</button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={activitiesEndRef} />
          </div>
        </div>

        <div className="autonomous-queue">
          <h3 className="log-header">Task Queue {taskQueue.length > 0 && `(${taskQueue.length})`}</h3>
          <div className="queue-entries">
            {taskQueue.length === 0 ? (
              <div className="log-empty">Queue is empty</div>
            ) : (
              taskQueue.map(task => (
                <div key={task.id} className="queue-entry">
                  <span className="queue-name">{task.name}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AutonomousAgent;
