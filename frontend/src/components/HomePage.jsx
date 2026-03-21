import { apiFetch, authEventSourceUrl } from '../apiFetch';
import { useEffect, useState } from 'react';
import './HomePage.css';

import { API_URL } from '../config.js';

const FEATURES = [
  {
    page: 'analysis',
    title: 'Analysis',
    desc: 'Chat with the AI agent to upload scans, extract metadata, and orchestrate inference workflows.',
    iconBg: 'rgba(99,102,241,0.15)',
    iconColor: '#818cf8',
    icon: (
      <svg width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    ),
  },
  {
    page: 'results',
    title: 'Results',
    desc: 'Monitor background inference tasks, view detected structures, volumes, and analysis outputs.',
    iconBg: 'rgba(16,185,129,0.15)',
    iconColor: '#34d399',
    icon: (
      <svg width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
        <rect x="3" y="3" width="18" height="18" rx="2"/>
        <path d="M3 9h18M9 21V9"/>
      </svg>
    ),
  },
  {
    page: 'autonomous',
    title: 'Autonomous',
    desc: 'Let the AI agent run continuously, watching workspaces and processing new files automatically.',
    iconBg: 'rgba(6,182,212,0.15)',
    iconColor: '#06b6d4',
    icon: (
      <svg width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    ),
  },
  {
    page: 'workspaces',
    title: 'Workspaces',
    desc: 'Watch directories for new DICOM files and trigger automatic AI analysis pipelines.',
    iconBg: 'rgba(245,158,11,0.15)',
    iconColor: '#fbbf24',
    icon: (
      <svg width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
    ),
  },
];

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function HomePage({ onNavigate, onSignIn, currentSessionId, runningTaskCount, isPublic }) {
  const [sessions, setSessions] = useState([]);
  const [taskStats, setTaskStats] = useState({ done: 0, failed: 0, running: 0 });
  const [loading, setLoading] = useState(!isPublic);

  useEffect(() => {
    if (isPublic) return;
    Promise.all([
      apiFetch(`${API_URL}/api/sessions`).then(r => r.json()).catch(() => ({ sessions: [] })),
      apiFetch(`${API_URL}/api/tasks`).then(r => r.json()).catch(() => ({ tasks: [] })),
    ]).then(([sessData, taskData]) => {
      setSessions((sessData.sessions || []).slice(0, 4));
      const tasks = taskData.tasks || [];
      setTaskStats({
        done: tasks.filter(t => t.status === 'done').length,
        failed: tasks.filter(t => t.status === 'failed').length,
        running: tasks.filter(t => t.status === 'queued' || t.status === 'running').length,
      });
      setLoading(false);
    });
  }, [currentSessionId, isPublic]);

  const isRunning = taskStats.running > 0 || runningTaskCount > 0;
  const activeRunning = Math.max(taskStats.running, runningTaskCount);

  return (
    <div className="home-root">
      {/* Background gradient orbs */}
      <div className="home-orb home-orb-1" />
      <div className="home-orb home-orb-2" />
      <div className="home-orb home-orb-3" />

      {/* Top navigation */}
      <nav className="home-topnav">
        <div className="home-topnav-brand">
          <div className="home-topnav-icon">H</div>
          <span className="home-topnav-name">HealthMCP</span>
        </div>
        <div className="home-topnav-links">
          <button onClick={() => onNavigate('autonomous')}>Autonomous</button>
          <button onClick={() => onNavigate('analysis')}>Analysis</button>
          <button onClick={() => onNavigate('results')}>
            Results
            {activeRunning > 0 && (
              <span className="home-topnav-badge">{activeRunning}</span>
            )}
          </button>
          <button onClick={() => onNavigate('workspaces')}>Workspaces</button>
        </div>
        <button className="home-topnav-cta" onClick={() => isPublic ? onSignIn?.() : onNavigate('analysis')}>
          {isPublic ? 'Sign in' : 'Open App'}
          <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>
      </nav>

      {/* Hero section */}
      <section className="home-hero">
        <div className="home-hero-inner">
          <div className={`home-status-pill ${isRunning ? 'running' : 'ready'}`}>
            <span className="home-status-dot" />
            {isRunning
              ? `${activeRunning} inference task${activeRunning > 1 ? 's' : ''} running`
              : 'System ready'}
          </div>

          <h1 className="home-hero-title">
            AI-Powered Medical<br />
            <span className="home-hero-title-accent">Imaging Analysis</span>
          </h1>

          <p className="home-hero-subtitle">
            Upload DICOM scans, run MONAI segmentation models, and generate structured radiology reports — all through a conversational AI agent.
          </p>

          <div className="home-hero-actions">
            <button className="home-btn-primary" onClick={() => isPublic ? onSignIn?.() : onNavigate('analysis')}>
              {isPublic ? 'Sign in to start' : 'Start Analysis'}
              <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </button>
            <button className="home-btn-secondary" onClick={() => onNavigate('results')}>
              View Results
              {activeRunning > 0 && (
                <span className="home-btn-running-badge">{activeRunning}</span>
              )}
            </button>
          </div>

        </div>
      </section>

      {/* Feature cards */}
      <section className="home-features">
        <div className="home-features-inner">
          <p className="home-section-label">What you can do</p>
          <div className="home-features-grid">
            {FEATURES.map(f => (
              <button
                key={f.page}
                className="home-feature-card"
                onClick={() => onNavigate(f.page)}
              >
                <div
                  className="home-feature-icon"
                  style={{ background: f.iconBg, color: f.iconColor }}
                >
                  {f.icon}
                </div>
                <h3 className="home-feature-title">{f.title}</h3>
                <p className="home-feature-desc">{f.desc}</p>
                <span className="home-feature-arrow">→</span>
              </button>
            ))}
          </div>
        </div>
      </section>


      {/* Footer */}
      <footer className="home-footer">
        <span>HealthMCP v1.0</span>
        <span className="home-footer-stack">MONAI · RadLex · FHIR</span>
        <button className="home-footer-settings" onClick={() => onNavigate('settings')}>
          Settings
        </button>
      </footer>
    </div>
  );
}

export default HomePage;
