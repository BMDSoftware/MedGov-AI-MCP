import { apiFetch, authEventSourceUrl } from '../apiFetch';
import { useEffect, useState } from 'react';
import './HomePage.css';

import { API_URL } from '../config.js';

const FEATURES = [
  {
    page: 'analysis',
    title: 'Analysis',
    desc: 'Chat with the AI agent to connect health data sources, run specialized tools, and orchestrate end-to-end clinical workflows.',
    iconBg: 'rgba(99,102,241,0.15)',
    iconColor: '#818cf8',
    icon: (
      <svg width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    ),
  },
  {
    page: 'workspaces',
    title: 'Workspaces',
    desc: 'Monitor health data sources and automatically trigger AI-powered clinical analysis pipelines.',
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

function HomePage({ onNavigate, onSignIn, onSignOut, currentSessionId, runningTaskCount, isPublic }) {
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
          <div className="home-topnav-icon">M</div>
          <span className="home-topnav-name">MedGov-AI</span>
        </div>
        <div className="home-topnav-links">
          <button onClick={() => onNavigate('analysis')}>Analysis</button>
          <button onClick={() => onNavigate('workspaces')}>Workspaces</button>
          <div className="home-topnav-divider" />
          <button onClick={() => onNavigate('results')}>
            Results
            {activeRunning > 0 && (
              <span className="home-topnav-badge">{activeRunning}</span>
            )}
          </button>
          <div className="home-topnav-divider" />
          <button onClick={() => onNavigate('about')}>About</button>
        </div>
        <div className="home-topnav-actions">
          {isPublic ? (
            <button className="home-topnav-cta" onClick={() => onSignIn?.()}>
              Sign in
              <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </button>
          ) : (
            <button className="home-topnav-signout" onClick={onSignOut}>Sign out</button>
          )}
        </div>
      </nav>

      {/* Hero section */}
      <section className="home-hero">
        <div className="home-hero-inner">
          <h1 className="home-hero-title">
            Agentic Health<br />
            <span className="home-hero-title-accent">Integrator</span>
          </h1>

          <p className="home-hero-subtitle">
            Connect health data sources, automate clinical workflows, and coordinate specialized health tools — all orchestrated through an AI agent designed for healthcare professionals.
          </p>

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
                <span className="home-feature-arrow" />
              </button>
            ))}
          </div>
        </div>
      </section>


      {/* Footer */}
      <footer className="home-footer">
        <span>MedGov-AI v1.0</span>
        <div className="home-footer-ack">
          <img
            src="https://www.healthfromportugal.pt/static/site/images/sponsors/footer-hfp.svg"
            alt="Health from Portugal"
            className="home-footer-ack-logo home-footer-ack-logo-hfp"
          />
          <span className="home-footer-ack-text">
            Supported by Health from Portugal - PRR grant No C644937233-00000047
          </span>
          <span className="home-footer-ack-sep" />
          <img src="Marca-UA-Complementar-PRETO.png" alt="Universidade de Aveiro" className="home-footer-ack-logo home-footer-logo-ua" style={{height: '42px', width: 'auto'}} />
          <img src="https://www.ieeta.pt/wp-content/uploads/2022/10/cropped-logo-ieeta-wordpress2-1.png" alt="IEETA" className="home-footer-ack-logo home-footer-logo-ieeta" style={{height: '28px', width: 'auto'}}/>
          <img src="https://www.bmd-software.com/wp-content/themes/pursuit/assets/images/logo.svg" alt="BMD Software" className="home-footer-ack-logo home-footer-logo-bmd" style={{height: '22px', width: 'auto'}} />
        </div>
        <button className="home-footer-settings" onClick={() => onNavigate('settings')}>
          Settings
        </button>
      </footer>
    </div>
  );
}

export default HomePage;
