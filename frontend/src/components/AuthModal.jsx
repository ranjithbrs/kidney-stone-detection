import React, { useState } from 'react'
import { ShieldCheck, X } from 'lucide-react'
import { api, setStoredToken } from '../api'

export default function AuthModal({ initialMode = 'signin', storageBackend, onClose, onSuccess }) {
  const [mode, setMode] = useState(initialMode)
  const [username, setUsername] = useState('')
  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('Nephrologist')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      let data
      if (mode === 'signin') {
        data = await api.signin({
          username_or_email: usernameOrEmail.trim(),
          password,
        })
      } else {
        if (password.length < 6) {
          throw new Error('Password must be at least 6 characters long.')
        }
        if (password !== confirmPassword) {
          throw new Error('Password confirmation does not match.')
        }
        data = await api.signup({
          username: username.trim(),
          password,
          full_name: fullName.trim() || username.trim(),
          role,
          email: email.trim(),
        })
      }
      setStoredToken(data.access_token)
      onSuccess(data.user, data.storage_backend)
    } catch (err) {
      setError(err.message || 'Authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Clinician Authentication">
      <div className="modal-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ShieldCheck size={22} color="#0f4c81" />
            <h3 style={{ margin: 0 }}>
              {mode === 'signin' ? 'Sign In to NEFROAI-X' : 'Create Clinician Account'}
            </h3>
          </div>
          <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close authentication modal">
            <X size={16} />
          </button>
        </div>

        <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: '0.9rem' }}>
          Storage Engine: <strong>{storageBackend === 'postgresql' ? 'Cloud PostgreSQL (Supabase)' : 'Local SQLite Vault (Cloud Ready)'}</strong>.
          Signed-in accounts save CKD evaluations permanently and unlock the audit vault.
        </p>

        <div className="tabs" style={{ marginBottom: '0.9rem' }}>
          <button
            type="button"
            className={`tab-btn ${mode === 'signin' ? 'active' : ''}`}
            onClick={() => { setMode('signin'); setError('') }}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`tab-btn ${mode === 'signup' ? 'active' : ''}`}
            onClick={() => { setMode('signup'); setError('') }}
          >
            Create Account
          </button>
        </div>

        {error && <div className="alert alert-danger" style={{ padding: '0.65rem 0.85rem' }}>{error}</div>}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
          {mode === 'signin' ? (
            <div className="field">
              <label htmlFor="auth-user-email">Username or Email</label>
              <input
                id="auth-user-email"
                type="text"
                required
                placeholder="dr.sharma or dr.sharma@hospital.org"
                value={usernameOrEmail}
                onChange={(e) => setUsernameOrEmail(e.target.value)}
              />
            </div>
          ) : (
            <>
              <div className="grid-2" style={{ gap: '0.6rem' }}>
                <div className="field">
                  <label htmlFor="auth-username">Username</label>
                  <input
                    id="auth-username"
                    type="text"
                    required
                    minLength={3}
                    placeholder="dr_nephro"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="auth-role">Clinical Role</label>
                  <select id="auth-role" value={role} onChange={(e) => setRole(e.target.value)}>
                    <option value="Nephrologist">Nephrologist</option>
                    <option value="Physician">Primary Care Physician</option>
                    <option value="Clinical Researcher">Clinical Researcher</option>
                    <option value="Lab Coordinator">Lab Coordinator</option>
                  </select>
                </div>
              </div>
              <div className="field">
                <label htmlFor="auth-fullname">Full Name</label>
                <input
                  id="auth-fullname"
                  type="text"
                  required
                  placeholder="Dr. A. Sharma"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="auth-email">Work / Clinical Email</label>
                <input
                  id="auth-email"
                  type="email"
                  placeholder="dr.sharma@hospital.org"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </>
          )}

          <div className="field">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              required
              minLength={6}
              placeholder="Minimum 6 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {mode === 'signup' && (
            <div className="field">
              <label htmlFor="auth-confirm">Confirm Password</label>
              <input
                id="auth-confirm"
                type="password"
                required
                minLength={6}
                placeholder="Re-enter password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ marginTop: '0.35rem' }}>
            {loading ? 'Authenticating...' : mode === 'signin' ? 'Sign In & Unlock Cloud Vault' : 'Create Account & Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}

