import { apiFetch, authEventSourceUrl } from '../apiFetch';
import { getToken } from '../auth';
import { useEffect, useState } from 'react';
import './Results.css';

import { API_URL } from '../config.js';

const STATUS_LABELS = {
  queued: 'Queued',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

function Results({ refreshSignal, currentSessionId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(new Set()); // set of expanded task ids
  const [filter, setFilter] = useState('all'); // all | inference | report | done | failed
  const [cancelling, setCancelling] = useState({}); // task id -> true while cancel request in flight

  const fetchTasks = async () => {
    try {
      const url = currentSessionId
        ? `${API_URL}/api/tasks?session_id=${currentSessionId}`
        : `${API_URL}/api/tasks`;
      const res = await apiFetch(url);
      const data = await res.json();
      setTasks(data.tasks || []);
    } catch {
      // silently fail - backend may not be up yet
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchTasks();
  }, [currentSessionId]);

  // Re-fetch whenever a task event arrives via SSE (parent passes refreshSignal)
  useEffect(() => {
    if (refreshSignal) fetchTasks();
  }, [refreshSignal]);

  const toggle = (id) => setExpanded(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const handleCancel = async (e, taskId) => {
    e.stopPropagation();
    setCancelling(prev => ({ ...prev, [taskId]: true }));
    try {
      await apiFetch(`${API_URL}/api/tasks/${taskId}/cancel`, { method: 'POST' });
      await fetchTasks();
    } catch {
      // silently fail — task may have already finished
    }
    setCancelling(prev => ({ ...prev, [taskId]: false }));
  };

  const filteredTasks = tasks.filter(t => {
    if (filter === 'all') return true;
    if (filter === 'queued') return t.status === 'queued' || t.status === 'running';
    if (filter === 'done') return t.status === 'done';
    if (filter === 'failed') return t.status === 'failed';
    return t.task_type === filter;
  });

  const formatTime = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
  };

  const formatDuration = (task) => {
    if (!task.created_at || !task.completed_at) return null;
    const ms = new Date(task.completed_at) - new Date(task.created_at);
    if (ms < 60000) return `${Math.round(ms / 1000)}s`;
    return `${Math.round(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
  };

  return (
    <div className="results-container">
      <div className="results-header">
        <h2>Background Tasks</h2>
        <button className="results-refresh-btn" onClick={fetchTasks}>Refresh</button>
      </div>

      <div className="results-filters">
        {['all', 'inference', 'cellpose', 'report', 'queued', 'done', 'failed'].map(f => (
          <button
            key={f}
            className={`filter-btn ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading && <p className="results-loading">Loading tasks...</p>}

      {!loading && filteredTasks.length === 0 && (
        <div className="results-empty">
          <p>No tasks yet. Ask the assistant to analyze a scan or generate a report.</p>
        </div>
      )}

      <div className="task-list">
        {filteredTasks.map(task => (
          <div key={task.id} className={`task-card task-${task.status}`}>
            <div className="task-card-header" onClick={() => toggle(task.id)}>
              <div className="task-card-left">
                <span className={`status-badge status-${task.status}`}>
                  {(task.status === 'running' || task.status === 'queued') && (
                    <span className="status-spinner" />
                  )}
                  {STATUS_LABELS[task.status] || task.status}
                </span>
                <span className="task-type-badge">{task.task_type}</span>
                <span className="task-description">{task.description}</span>
                {task.input_data?.modality && (
                  <span className="task-meta-tag">{task.input_data.modality}</span>
                )}
                {task.input_data?.body_part && (
                  <span className="task-meta-tag">{task.input_data.body_part}</span>
                )}
              </div>
              <div className="task-card-right">
                {formatDuration(task) && (
                  <span className="task-duration">{formatDuration(task)}</span>
                )}
                <span className="task-time">{formatTime(task.created_at)}</span>
                {(task.status === 'queued' || task.status === 'running') && (
                  <button
                    className="task-cancel-btn"
                    onClick={(e) => handleCancel(e, task.id)}
                    disabled={cancelling[task.id]}
                    title="Cancel task"
                  >
                    {cancelling[task.id] ? '...' : '✕'}
                  </button>
                )}
                <span className="task-chevron">{expanded.has(task.id) ? '▲' : '▼'}</span>
              </div>
            </div>

            {expanded.has(task.id) && (
              <div className="task-card-body">
                {/* Inference summary */}
                {task.task_type === 'inference' && (
                  <div className="task-inference-summary">
                    <div className="task-inference-summary-row">
                      <span className="task-summary-label">File</span>
                      <span className="task-summary-value">
                        {task.input_data?.image_path
                          ? task.input_data.image_path.split('/').pop()
                          : '—'}
                      </span>
                    </div>
                    <div className="task-inference-summary-row">
                      <span className="task-summary-label">Model</span>
                      <span className="task-summary-value">{task.input_data?.model_name || '—'}</span>
                    </div>
                    {task.input_data?.modality && (
                      <div className="task-inference-summary-row">
                        <span className="task-summary-label">Modality</span>
                        <span className="task-summary-value">{task.input_data.modality}</span>
                      </div>
                    )}
                    {task.input_data?.body_part && (
                      <div className="task-inference-summary-row">
                        <span className="task-summary-label">Body Part</span>
                        <span className="task-summary-value">{task.input_data.body_part}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Cellpose summary */}
                {task.task_type === 'cellpose' && (
                  <div className="task-inference-summary">
                    <div className="task-inference-summary-row">
                      <span className="task-summary-label">File</span>
                      <span className="task-summary-value">
                        {task.input_data?.image_path
                          ? task.input_data.image_path.split('/').pop()
                          : '—'}
                      </span>
                    </div>
                    <div className="task-inference-summary-row">
                      <span className="task-summary-label">Model</span>
                      <span className="task-summary-value">{task.input_data?.model_type || '—'}</span>
                    </div>
                  </div>
                )}

                {task.status === 'failed' && task.error && (
                  <div className="task-error">{task.error}</div>
                )}

                {task.status === 'done' && task.result && (
                  <TaskResult task={task} />
                )}

                {(task.status === 'queued' || task.status === 'running') && (
                  <p className="task-pending-msg">
                    {task.status === 'queued' ? 'Waiting to start...' : (task.message || 'Running in background...')}
                  </p>
                )}

                <div className="task-meta">
                  <span>Session: {task.session_id?.slice(0, 8)}...</span>
                  {task.completed_at && (
                    <span>Completed: {formatTime(task.completed_at)}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


function TaskResult({ task }) {
  const result = task.result;

  if (task.task_type === 'inference') {
    // If the result itself contains an error (e.g. task was marked done but MCP returned error)
    if (result?.error) {
      return (
        <div className="task-result-inference">
          <div className="task-error">{result.error}</div>
        </div>
      );
    }

    const structures = result?.results?.detected_structures || [];
    const hasVolume = structures.some(s => s.volume_cm3 != null);
    return (
      <div className="task-result-inference">
        <div className="result-meta-row">
          <span>Model: <strong>{result.model_used || '—'}</strong></span>
          <span>Device: <strong>{result.device_used || '—'}</strong></span>
          <span>Input: <strong>{result.input_image?.split('/').pop() || '—'}</strong></span>
        </div>
        {structures.length > 0 ? (
          <table className="result-structures-table">
            <thead>
              <tr>
                <th>Structure</th>
                <th>Voxels</th>
                {hasVolume && <th>Volume (cm³)</th>}
                <th>% of scan</th>
              </tr>
            </thead>
            <tbody>
              {structures.map((s, i) => (
                <tr key={i}>
                  <td>{s.name}</td>
                  <td>{s.voxel_count?.toLocaleString()}</td>
                  {hasVolume && <td>{s.volume_cm3 != null ? s.volume_cm3 : '—'}</td>}
                  <td>{s.volume_percentage?.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="task-pending-msg">No structures detected.</p>
        )}
      </div>
    );
  }

  if (task.task_type === 'cellpose') {
    if (result?.error) {
      return (
        <div className="task-result-inference">
          <div className="task-error">{result.error}</div>
        </div>
      );
    }
    const token = getToken();
    const imageUrl = result?.output_path
      ? `${API_URL}/api/files/image?path=${encodeURIComponent(result.output_path)}${token ? `&token=${encodeURIComponent(token)}` : ''}`
      : null;
    return (
      <div className="task-result-inference">
        <div className="result-meta-row">
          <span>Cells detected: <strong>{result?.cells_detected ?? '—'}</strong></span>
          <span>Model: <strong>{task.input_data?.model_type || '—'}</strong></span>
          {result?.diameter != null && (
            <span>Diameter: <strong>{result.diameter.toFixed(1)} px</strong></span>
          )}
        </div>
        {result?.mask_shape && (
          <div className="task-inference-summary-row">
            <span className="task-summary-label">Mask shape</span>
            <span className="task-summary-value">{result.mask_shape.join(' × ')}</span>
          </div>
        )}
        {imageUrl && (
          <div style={{ marginTop: '1rem' }}>
            <img
              src={imageUrl}
              alt="Segmentation mask"
              style={{ width: '30%', borderRadius: '6px', border: '1px solid var(--border)', display: 'block' }}
            />
          </div>
        )}
        {result?.output_path && (
          <div className="task-inference-summary-row" style={{ marginTop: '0.5rem' }}>
            <span className="task-summary-label">Mask saved</span>
            <span className="task-summary-value" style={{ wordBreak: 'break-all' }}>
              {result.output_path}
            </span>
          </div>
        )}
      </div>
    );
  }

  if (task.task_type === 'report') {
    const narrative = result?.narrative || {};
    const findings = result?.findings || [];
    return (
      <div className="task-result-report">
        {findings.map((f, i) => (
          <div key={i} className="report-finding-block">
            <h4>{f.description}</h4>
            {f.structures?.length > 0 && (
              <table className="result-structures-table">
                <thead>
                  <tr><th>Structure</th><th>Volume</th><th>% of scan</th></tr>
                </thead>
                <tbody>
                  {f.structures.map((s, j) => (
                    <tr key={j}>
                      <td>{s.name}</td>
                      <td>{s.volume_cm3 != null ? `${s.volume_cm3} cm³` : `${s.voxel_count?.toLocaleString()} vox`}</td>
                      <td>{s.volume_percentage?.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
        {narrative.findings_narrative && (
          <div className="report-narrative-section">
            <h4>Findings</h4>
            <p>{narrative.findings_narrative}</p>
          </div>
        )}
        {narrative.impression && (
          <div className="report-narrative-section">
            <h4>Impression</h4>
            <p>{narrative.impression}</p>
          </div>
        )}
        {narrative.recommendations && (
          <div className="report-narrative-section">
            <h4>Recommendations</h4>
            <p>{narrative.recommendations}</p>
          </div>
        )}
      </div>
    );
  }

  // Generic fallback
  return (
    <pre className="task-result-raw">{JSON.stringify(result, null, 2)}</pre>
  );
}

export default Results;
