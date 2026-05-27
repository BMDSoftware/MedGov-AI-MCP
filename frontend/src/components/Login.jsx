import { useState } from 'react';
import { MdLocalHospital, MdLock, MdPerson, MdEmail, MdArrowForward, MdCheckCircle, MdVisibility, MdVisibilityOff } from 'react-icons/md';
import { getApiUrl } from '../config';
import { setAuth } from '../auth';
import './Login.css';

const HIGHLIGHTS = [
  'Autonomous clinical imaging analysis',
  'Structured radiology and pathology reports',
  'Workspace monitoring with event-driven pipelines',
  'Per-user sessions and workspace isolation',
];

export default function Login({ onLogin, onBack }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const url = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body = mode === 'login'
        ? { username, password }
        : { username, email, password };

      const res = await fetch(getApiUrl(url), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Authentication failed');
        return;
      }
      setAuth(data.access_token, data.username);
      onLogin(data.access_token, data.username);
    } catch {
      setError('Network error — is the server running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="sl-root">

      {/* ── Left panel ── */}
      <div className="sl-left">
        <div className="sl-left-inner">
          <div className="sl-brand" onClick={onBack} style={{ cursor: onBack ? 'pointer' : 'default' }}>
            <div className="sl-brand-icon"><MdLocalHospital /></div>
            <span className="sl-brand-name">MedGov-AI</span>
          </div>

          <div className="sl-left-body">
            <h1 className="sl-left-title">
              Clinical workflows,<br />
              <span className="sl-left-accent">automated.</span>
            </h1>
            <p className="sl-left-sub">
              An AI-powered application for autonomous workflows and task resolution, with integrated medical tools for imaging, reporting, and general clinical support.
            </p>

            <ul className="sl-features">
              {HIGHLIGHTS.map(h => (
                <li key={h}>
                  <MdCheckCircle className="sl-feature-icon" />
                  {h}
                </li>
              ))}
            </ul>
          </div>

          <p className="sl-left-footer">Supported by Health from Portugal · PRR</p>
        </div>
      </div>

      {/* ── Right panel ── */}
      <div className="sl-right">
        <div className="sl-form-wrap">

          <div className="sl-form-header">
            <h2>{mode === 'login' ? 'Sign in' : 'Create account'}</h2>
            <p>
              {mode === 'login' ? (
                <>
                  Enter your credentials to access your workspace. Just exploring?{' '}
                  <button
                    type="button"
                    className="sl-demo-link"
                    onClick={() => { setUsername('demo'); setPassword('demodemo'); setError(''); }}
                  >
                    Use demo credentials
                  </button>
                </>
              ) : 'Set up your account to get started.'}
            </p>
          </div>

          <form className="sl-form" onSubmit={handleSubmit}>
            <div className="sl-field">
              <label htmlFor="sl-username">Username</label>
              <div className="sl-input-wrap">
                <MdPerson className="sl-input-icon" />
                <input
                  id="sl-username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="your_username"
                  autoComplete="username"
                  required
                />
              </div>
            </div>

            {mode === 'register' && (
              <div className="sl-field">
                <label htmlFor="sl-email">Email</label>
                <div className="sl-input-wrap">
                  <MdEmail className="sl-input-icon" />
                  <input
                    id="sl-email"
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@hospital.com"
                    autoComplete="email"
                    required
                  />
                </div>
              </div>
            )}

            <div className="sl-field">
              <label htmlFor="sl-password">Password</label>
              <div className="sl-input-wrap">
                <MdLock className="sl-input-icon" />
                <input
                  id="sl-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  className="sl-password-input"
                  required
                />
                <button
                  type="button"
                  className="sl-pw-toggle"
                  onClick={() => setShowPassword(v => !v)}
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <MdVisibilityOff /> : <MdVisibility />}
                </button>
              </div>
            </div>

            {error && <p className="sl-error">{error}</p>}

            <button className="sl-submit" type="submit" disabled={loading}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
              {!loading && <MdArrowForward />}
            </button>
          </form>

          <p className="sl-switch">
            {mode === 'login' ? (
              <>No account?{' '}
                <button onClick={() => { setMode('register'); setError(''); }}>Register</button>
              </>
            ) : (
              <>Already registered?{' '}
                <button onClick={() => { setMode('login'); setError(''); }}>Sign in</button>
              </>
            )}
          </p>

        </div>
      </div>
    </div>
  );
}
