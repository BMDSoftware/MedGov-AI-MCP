import React, { useEffect, useState } from 'react';
import { getApiUrl } from '../config';
import './InferenceTest.css';

const API_URL = 'http://localhost:5001';

function InferenceTest() {
  const [currentStep, setCurrentStep] = useState(1);
  const [error, setError] = useState(null);

  // Step 1: File selection
  const [sampleFiles, setSampleFiles] = useState([]);
  const [loadingSamples, setLoadingSamples] = useState(true);
  const [selectedFile, setSelectedFile] = useState(null); // {name, path, source, type}
  const [uploadingDir, setUploadingDir] = useState(false);

  // Step 1.5: Validation (for DICOM series)
  const [validationResult, setValidationResult] = useState(null);
  const [validating, setValidating] = useState(false);
  const [selectedSeries, setSelectedSeries] = useState(null);

  // Step 2: Analysis
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  // Step 3: Models
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [downloading, setDownloading] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);

  // Step 4: Inference
  const [inferenceResult, setInferenceResult] = useState(null);
  const [runningInference, setRunningInference] = useState(false);

  useEffect(() => {
    fetchSampleData();
  }, []);

  const fetchSampleData = async () => {
    setLoadingSamples(true);
    try {
      const res = await fetch(`${API_URL}/api/monai/sample-data`);
      const data = await res.json();
      setSampleFiles(data.files || []);
    } catch (e) {
      setError('Failed to load sample data.');
    }
    setLoadingSamples(false);
  };

  const resetDownstream = () => {
    setValidationResult(null);
    setSelectedSeries(null);
    setAnalysisResult(null);
    setModels([]);
    setSelectedModel(null);
    setInferenceResult(null);
    setError(null);
  };

  const handleFileSelect = (file) => {
    // Toggle: clicking the same file again unselects it
    if (selectedFile?.path === file.path) {
      setSelectedFile(null);
      setCurrentStep(1);
      resetDownstream();
      return;
    }
    setSelectedFile(file);
    resetDownstream();

    setCurrentStep(2);
    // DICOM series need validation first, image series skip validation
    if (file.type === 'dicom_series') {
      validateSeries(file.path);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_URL}/api/upload`, { method: 'POST', body: formData });
      const data = await res.json();
      if (data.stored_path) {
        handleFileSelect({ name: file.name, path: data.stored_path, source: 'upload', type: file.name.endsWith('.dcm') ? 'dcm' : 'nii.gz' });
      } else {
        setError('Upload succeeded but no stored path returned.');
      }
    } catch (e) {
      setError('Upload failed.');
    }
  };

  const handleDirectoryUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setError(null);
    setUploadingDir(true);
    try {
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i], files[i].webkitRelativePath || files[i].name);
      }
      const res = await fetch(`${API_URL}/api/upload-directory`, { method: 'POST', body: formData });
      const data = await res.json();
      if (data.dir_path) {
        handleFileSelect({
          name: `${data.dirname} (${data.file_count} files)`,
          path: data.dir_path,
          source: 'upload',
          type: 'dicom_series',
        });
        // Refresh sample list to show the new upload
        fetchSampleData();
      } else {
        setError(data.detail || 'Directory upload failed.');
      }
    } catch (e) {
      setError('Directory upload failed.');
    }
    setUploadingDir(false);
  };

  const validateSeries = async (dirPath) => {
    setValidating(true);
    setValidationResult(null);
    try {
      const res = await fetch(`${API_URL}/api/monai/validate-series`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: dirPath })
      });
      const data = await res.json();
      setValidationResult(data);
      // Auto-select if only one series
      if (data.valid && data.series?.length === 1) {
        setSelectedSeries(data.series[0]);
      }
    } catch (e) {
      setError('Series validation failed.');
    }
    setValidating(false);
  };

  const getAnalyzePath = () => {
    // For DICOM series, use the directory path (MONAI handles it)
    if (selectedFile?.type === 'dicom_series') {
      return selectedFile.path;
    }
    return selectedFile?.path;
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;
    setAnalyzing(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/monai/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: getAnalyzePath() })
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setAnalysisResult(data);
        setCurrentStep(3);
        const modality = data.analysis?.detected_modalities?.[0];
        // Don't filter by modality if detection failed
        fetchModels(modality === 'unknown' ? null : modality);
      }
    } catch (e) {
      setError('Analysis failed.');
    }
    setAnalyzing(false);
  };

  const fetchModels = async (modality) => {
    setLoadingModels(true);
    try {
      const body = {};
      if (modality) body.modality = modality;
      const res = await fetch(`${API_URL}/api/monai/list-models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      setModels(data.models || []);
    } catch (e) {
      setError('Failed to fetch models.');
    }
    setLoadingModels(false);
  };

  const handleDownload = async (modelName) => {
    setDownloading(modelName);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/monai/download-model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName })
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        const modality = analysisResult?.analysis?.detected_modalities?.[0];
        await fetchModels(modality === 'unknown' ? null : modality);
      }
    } catch (e) {
      setError('Download failed.');
    }
    setDownloading(null);
  };

  const handleSelectModel = (model) => {
    setSelectedModel(model);
    setCurrentStep(4);
    setInferenceResult(null);
  };

  const handleRunInference = async () => {
    if (!selectedFile || !selectedModel) return;
    setRunningInference(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/monai/run-inference`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_path: getAnalyzePath(),
          model_name: selectedModel.name
        })
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setInferenceResult(data);
      }
    } catch (e) {
      setError('Inference failed.');
    }
    setRunningInference(false);
  };

  const handleReset = () => {
    setCurrentStep(1);
    setSelectedFile(null);
    resetDownstream();
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const steps = [
    { num: 1, label: 'File' },
    { num: 2, label: 'Analyze' },
    { num: 3, label: 'Models' },
    { num: 4, label: 'Inference' }
  ];

  return (
    <div className="inference-test-container">
      <div className="inference-header">
        <h2>MONAI Inference Test</h2>
        <button className="reset-btn" onClick={handleReset}>Reset</button>
      </div>

      {/* Step indicator */}
      <div className="step-indicator">
        {steps.map((step, i) => (
          <React.Fragment key={step.num}>
            <div className={`step-dot ${currentStep === step.num ? 'active' : ''} ${currentStep > step.num ? 'completed' : ''}`}>
              {currentStep > step.num ? '\u2713' : step.num}
            </div>
            {i < steps.length - 1 && (
              <div className={`step-line ${currentStep > step.num ? 'completed' : ''}`} />
            )}
          </React.Fragment>
        ))}
      </div>
      <div className="step-labels">
        {steps.map(step => (
          <span key={step.num} className={`step-label ${currentStep >= step.num ? 'active' : ''}`}>
            {step.label}
          </span>
        ))}
      </div>

      {error && <div className="test-error">{error}</div>}

      {/* Step 1: File Selection */}
      <div className={`test-step ${currentStep >= 1 ? '' : 'disabled'}`}>
        <h3>1. Select File</h3>

        <div className="file-upload-section">
          <label className="upload-label">
            Upload a file (.nii.gz, .dcm)
            <input
              type="file"
              accept=".nii,.nii.gz,.dcm"
              onChange={handleFileUpload}
              className="file-input-hidden"
            />
          </label>
          <label className="upload-label upload-dir-label">
            {uploadingDir ? 'Uploading...' : 'Upload DICOM directory'}
            <input
              type="file"
              webkitdirectory=""
              directory=""
              onChange={handleDirectoryUpload}
              className="file-input-hidden"
              disabled={uploadingDir}
            />
          </label>
        </div>

        <div className="divider"><span>or select sample data</span></div>

        {loadingSamples ? (
          <p className="loading-text">Loading sample files...</p>
        ) : (
          <div className="sample-list">
            {sampleFiles.map(f => (
              <div
                key={f.path}
                className={`sample-item ${selectedFile?.path === f.path ? 'selected' : ''}`}
                onClick={() => handleFileSelect(f)}
              >
                <span className={`sample-type-badge ${(f.type === 'dicom_series' || f.type === 'image_series') ? 'series-badge' : ''}`}>
                  {f.type === 'dicom_series' ? 'SERIES' : f.type === 'image_series' ? 'IMAGES' : f.type.toUpperCase()}
                </span>
                <span className="sample-name">{f.name}</span>
                <span className="sample-size">{formatSize(f.size)}</span>
                <span className="sample-source">{f.source}</span>
              </div>
            ))}
          </div>
        )}

        {selectedFile && (
          <div className="selected-file-banner">
            Selected: <strong>{selectedFile.name}</strong>
            {selectedFile.type === 'dicom_series' && ' (DICOM Series)'}
            {selectedFile.type === 'image_series' && ' (Image Series)'}
          </div>
        )}
      </div>

      {/* Validation panel (for DICOM series) */}
      {selectedFile?.type === 'dicom_series' && currentStep >= 2 && (
        <div className="test-step">
          <h3>Series Validation</h3>
          {validating && <p className="loading-text">Validating DICOM series...</p>}
          {validationResult && !validationResult.valid && (
            <div className="test-error">{validationResult.error || 'Invalid series'}</div>
          )}
          {validationResult?.warnings?.map((w, i) => (
            <div key={i} className="validation-warning">{w}</div>
          ))}
          {validationResult?.valid && validationResult?.is_image_dir && (
            <div className="series-picker">
              <p className="loading-text">
                {validationResult.total_files} image slices detected - will be stacked into a 3D volume for inference
              </p>
            </div>
          )}
          {validationResult?.valid && !validationResult?.is_image_dir && (
            <div className="series-picker">
              <p className="loading-text">
                Found {validationResult.total_files} files in {validationResult.series_count} series
              </p>
              <div className="series-list">
                {validationResult.series.map((s, i) => (
                  <div
                    key={s.uid || i}
                    className={`series-card ${selectedSeries?.uid === s.uid ? 'selected' : ''}`}
                    onClick={() => setSelectedSeries(s)}
                  >
                    <div className="series-info">
                      <span className="series-title">
                        {s.description || `Series ${i + 1}`}
                      </span>
                      <span className="series-meta">
                        {s.modality || 'Unknown'} | {s.body_part || 'Unknown'} | {s.slice_count} slices
                      </span>
                    </div>
                    {selectedSeries?.uid === s.uid && (
                      <span className="ready-badge">Selected</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Analyze */}
      <div className={`test-step ${currentStep >= 2 ? '' : 'disabled'}`}>
        <h3>2. Analyze Image</h3>
        {currentStep >= 2 && (
          <>
            <button
              className="action-btn"
              onClick={handleAnalyze}
              disabled={analyzing || (selectedFile?.type === 'dicom_series' && !validationResult?.is_image_dir && (!validationResult?.valid || !selectedSeries))}
            >
              {analyzing ? 'Analyzing...' : 'Run Analysis'}
            </button>

            {analysisResult && (
              <div className="analysis-results">
                <div className="result-grid">
                  <div className="result-item">
                    <span className="result-label">Shape</span>
                    <span className="result-value">{JSON.stringify(analysisResult.shape)}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Format</span>
                    <span className="result-value">{analysisResult.analysis?.file_format}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Modality</span>
                    <span className="result-value">{analysisResult.analysis?.detected_modalities?.join(', ')}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">3D</span>
                    <span className="result-value">{analysisResult.analysis?.is_3d ? 'Yes' : 'No'}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Dimensions</span>
                    <span className="result-value">{analysisResult.analysis?.dimensions}D</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Intensity</span>
                    <span className="result-value">
                      {analysisResult.analysis?.intensity_range
                        ? `${analysisResult.analysis.intensity_range.min?.toFixed(0)} to ${analysisResult.analysis.intensity_range.max?.toFixed(0)}`
                        : 'N/A'}
                    </span>
                  </div>
                </div>
                {analysisResult.ready_for_inference && (
                  <div className="ready-badge">Ready for inference</div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Step 3: Models */}
      <div className={`test-step ${currentStep >= 3 ? '' : 'disabled'}`}>
        <h3>3. Select Model</h3>
        {currentStep >= 3 && (
          <>
            <button
              className="reset-btn"
              onClick={() => fetchModels(null)}
              style={{ marginBottom: '10px' }}
            >
              Show All Models
            </button>
            {loadingModels ? (
              <p className="loading-text">Loading models...</p>
            ) : (
              <div className="models-list">
                {models.length === 0 && <p className="loading-text">No matching models found.</p>}
                {models.map(m => (
                  <div key={m.name} className={`model-card ${selectedModel?.name === m.name ? 'selected' : ''}`}>
                    <div className="model-info">
                      <span className="model-name">{m.name}</span>
                      <span className="model-meta">
                        {m.modality} | {m.body_part} | {m.category}
                      </span>
                      {m.description && <span className="model-desc">{m.description}</span>}
                    </div>
                    <div className="model-actions">
                      {m.downloaded ? (
                        <span className="downloaded-badge">Downloaded</span>
                      ) : (
                        <button
                          className="download-btn"
                          onClick={() => handleDownload(m.name)}
                          disabled={downloading === m.name}
                        >
                          {downloading === m.name ? 'Downloading...' : 'Download'}
                        </button>
                      )}
                      {m.downloaded && (
                        <button className="select-model-btn" onClick={() => handleSelectModel(m)}>
                          Select
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Step 4: Inference */}
      <div className={`test-step ${currentStep >= 4 ? '' : 'disabled'}`}>
        <h3>4. Run Inference</h3>
        {currentStep >= 4 && (
          <>
            <div className="inference-summary">
              <span>File: <strong>{selectedFile?.name}</strong></span>
              <span>Model: <strong>{selectedModel?.name}</strong></span>
            </div>
            <button
              className="action-btn run-btn"
              onClick={handleRunInference}
              disabled={runningInference}
            >
              {runningInference ? 'Running Inference...' : 'Run Inference'}
            </button>

            {runningInference && (
              <p className="loading-text">This may take several minutes on CPU...</p>
            )}

            {inferenceResult && (
              <div className="inference-results">
                <div className="result-grid">
                  <div className="result-item">
                    <span className="result-label">Status</span>
                    <span className="result-value">{inferenceResult.status}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Device</span>
                    <span className="result-value">{inferenceResult.device_used}</span>
                  </div>
                  <div className="result-item">
                    <span className="result-label">Input Shape</span>
                    <span className="result-value">{JSON.stringify(inferenceResult.input_shape)}</span>
                  </div>
                </div>

                {inferenceResult.results?.detected_structures && (
                  <div className="structures-section">
                    <h4>Detected Structures</h4>
                    <table className="results-table">
                      <thead>
                        <tr>
                          <th>Structure</th>
                          <th>Detected</th>
                          <th>Voxels</th>
                          <th>Volume %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {inferenceResult.results.detected_structures.map((s, i) => (
                          <tr key={i} className={s.detected ? 'detected' : 'not-detected'}>
                            <td>{s.name}</td>
                            <td>{s.detected ? 'Yes' : 'No'}</td>
                            <td>{s.voxel_count?.toLocaleString()}</td>
                            <td>{s.volume_percentage?.toFixed(2)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default InferenceTest;
