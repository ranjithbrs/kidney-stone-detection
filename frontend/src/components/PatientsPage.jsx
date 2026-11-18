import React, { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  ClipboardPlus,
  FileSpreadsheet,
  Lock,
  Plus,
  RefreshCw,
  Search,
  Stethoscope,
} from 'lucide-react'
import { api, setStoredToken } from '../api'
import { formatTriageTier, getTierBadgeClass } from '../clinicalMeta'

export default function PatientsPage({
  user,
  vaultRefreshKey,
  onNewScreening,
  onOpenBatchScreening,
  onOpenVaultPatient,
  onOpenAuth,
  onSignedIn,
}) {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  // Inline clinician sign-in form when signed out
  const [loginUser, setLoginUser] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginError, setLoginError] = useState('')

  async function fetchPatients() {
    if (!user) return
    setLoading(true)
    setError('')
    try {
      const res = await api.history()
      setRecords(res.records || [])
    } catch (err) {
      setError(err.message || 'Unable to load clinic patient records.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPatients()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, vaultRefreshKey])

  async function handleInlineSignIn(e) {
    e.preventDefault()
    setLoginError('')
    setLoginLoading(true)
    try {
      const data = await api.signin({
        username_or_email: loginUser.trim(),
        password: loginPassword,
      })
      setStoredToken(data.access_token)
      setLoginPassword('')
      if (onSignedIn) onSignedIn(data.user, data.storage_backend)
    } catch (err) {
      setLoginError(err.message || 'Invalid credentials.')
    } finally {
      setLoginLoading(false)
    }
  }

  const filteredRecords = useMemo(() => {
    const q = search.trim().toLowerCase()
    return records.filter((r) => {
      const pid = String(r.patient_id || '').toLowerCase()
      if (q && !pid.includes(q)) return false
      const tierCls = getTierBadgeClass(r.arbitration_tier)
      if (statusFilter === 'urgent') return tierCls === 'badge-danger'
      if (statusFilter === 'review') return tierCls === 'badge-warn'
      if (statusFilter === 'stable') return tierCls === 'badge-ok'
      return true
    })
  }, [records, search, statusFilter])

  const summary = useMemo(() => {
    const total = records.length
    const urgent = records.filter((r) => getTierBadgeClass(r.arbitration_tier) === 'badge-danger').length
    const review = records.filter((r) => getTierBadgeClass(r.arbitration_tier) === 'badge-warn').length
    const stable = records.filter((r) => getTierBadgeClass(r.arbitration_tier) === 'badge-ok').length
    return { total, urgent, review, stable }
  }, [records])

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Patients</h1>
          <p className="page-subtitle">
            {user
              ? 'Active renal screening queue, KDIGO staging status, and longitudinal patient charts.'
              : 'Clinician portal for renal function staging, KFRE prognosis, and longitudinal follow-up.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {user && (
            <button type="button" className="btn" onClick={fetchPatients} disabled={loading}>
              <RefreshCw size={14} /> Refresh
            </button>
          )}
          <button type="button" className="btn" onClick={onOpenBatchScreening}>
            <FileSpreadsheet size={14} /> Batch CSV
          </button>
          <button type="button" className="btn btn-primary" onClick={onNewScreening}>
            <Plus size={15} /> New screening
          </button>
        </div>
      </div>

      {user ? (
        <>
          <div className="metric-strip">
            <div className="metric-cell">
              <div className="metric-label">Saved assessments</div>
              <div className="metric-val tabular">{summary.total}</div>
              <div className="metric-sub">Assigned to clinician registry</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Urgent referrals</div>
              <div className="metric-val tabular" style={{ color: summary.urgent > 0 ? 'var(--danger-fg)' : 'var(--text)' }}>
                {summary.urgent}
              </div>
              <div className="metric-sub">Priority nephrology evaluation</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Pending review</div>
              <div className="metric-val tabular" style={{ color: summary.review > 0 ? 'var(--warn-fg)' : 'var(--text)' }}>
                {summary.review}
              </div>
              <div className="metric-sub">Incomplete or repeat lab workup</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Routine follow-up</div>
              <div className="metric-val tabular" style={{ color: summary.stable > 0 ? 'var(--ok-fg)' : 'var(--text)' }}>
                {summary.stable}
              </div>
              <div className="metric-sub">Stable or standard monitoring</div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Patient screening registry</h2>
                <p className="panel-desc">Select a patient row to inspect eGFR trend, stage guidance, and visit history.</p>
              </div>
              <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', minWidth: '210px' }}>
                  <Search
                    size={14}
                    style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }}
                  />
                  <input
                    type="text"
                    className="input-inline"
                    placeholder="Search patient ID..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ paddingLeft: '1.9rem' }}
                  />
                </div>
                <div className="segmented">
                  {[
                    { id: 'all', label: 'All' },
                    { id: 'urgent', label: 'Urgent' },
                    { id: 'review', label: 'Review' },
                    { id: 'stable', label: 'Routine' },
                  ].map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      className={`seg-btn ${statusFilter === f.id ? 'active' : ''}`}
                      onClick={() => setStatusFilter(f.id)}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {error && <div className="notice notice-danger">{error}</div>}

            {loading ? (
              <div style={{ padding: '2rem', color: 'var(--muted)', textAlign: 'center' }}>
                Loading patient records…
              </div>
            ) : filteredRecords.length === 0 ? (
              <div style={{ padding: '2.25rem 1rem', textAlign: 'center' }}>
                <p style={{ color: 'var(--text-secondary)', fontWeight: 500, marginBottom: '0.35rem' }}>
                  {records.length === 0
                    ? 'No patient records saved under this clinician account yet.'
                    : 'No patient records match your current search or filter.'}
                </p>
                <p style={{ color: 'var(--muted)', fontSize: '0.83rem', marginBottom: '1rem' }}>
                  {records.length === 0
                    ? 'Run a single-patient screening or import a laboratory CSV to populate your clinic queue.'
                    : 'Clear the search box or filter to see all saved patients.'}
                </p>
                {records.length === 0 && (
                  <div style={{ display: 'inline-flex', gap: '0.5rem' }}>
                    <button type="button" className="btn btn-primary" onClick={onNewScreening}>
                      <Plus size={14} /> Start patient screening
                    </button>
                    <button type="button" className="btn" onClick={onOpenBatchScreening}>
                      <FileSpreadsheet size={14} /> Batch CSV import
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="table-wrap">
                <table className="clean-table">
                  <thead>
                    <tr>
                      <th>Patient ID</th>
                      <th>Visit Date</th>
                      <th>eGFR</th>
                      <th>KDIGO Stage</th>
                      <th>Risk Score</th>
                      <th>Clinical Status</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRecords.map((r) => (
                      <tr
                        key={r.assessment_id}
                        className="clickable-row"
                        onClick={() => onOpenVaultPatient(r.patient_id, r.assessment_id)}
                      >
                        <td style={{ fontWeight: 600, color: 'var(--text)' }}>{r.patient_id}</td>
                        <td className="tabular">{String(r.recorded_at || r.observation_date || '').slice(0, 10) || '—'}</td>
                        <td className="tabular">{r.egfr != null ? `${Number(r.egfr).toFixed(1)} mL/min` : '—'}</td>
                        <td>
                          <span className="badge badge-neutral">{r.kdigo_stage || 'Pending'}</span>
                        </td>
                        <td className="tabular">
                          {r.e1_risk_probability != null ? `${(r.e1_risk_probability * 100).toFixed(1)}%` : 'Review'}
                        </td>
                        <td>
                          <span className={`badge ${getTierBadgeClass(r.arbitration_tier)}`}>
                            {formatTriageTier(r.arbitration_tier)}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--accent)', fontWeight: 500 }}>
                            Open chart <ArrowRight size={13} />
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="grid-2" style={{ alignItems: 'start' }}>
          {/* Direct Real-World Clinician Sign In */}
          <div className="panel">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--accent)', fontWeight: 600, fontSize: '0.82rem', marginBottom: '0.35rem' }}>
              <Lock size={14} /> Clinician Sign In
            </div>
            <h2 className="panel-title">Access patient registry</h2>
            <p className="panel-desc" style={{ marginBottom: '1rem' }}>
              Sign in to save encounters, review multi-visit eGFR trends, and manage clinic follow-ups.
            </p>

            {loginError && <div className="notice notice-danger">{loginError}</div>}

            <form onSubmit={handleInlineSignIn} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="field">
                <label htmlFor="home-signin-user">Username or email</label>
                <input
                  id="home-signin-user"
                  type="text"
                  required
                  placeholder="dr.sharma or dr.sharma@hospital.org"
                  value={loginUser}
                  onChange={(e) => setLoginUser(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="home-signin-pass">Password</label>
                <input
                  id="home-signin-pass"
                  type="password"
                  required
                  placeholder="Enter password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.2rem' }}>
                <button type="submit" className="btn btn-primary" disabled={loginLoading}>
                  {loginLoading ? 'Signing in…' : 'Sign in'}
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => onOpenAuth('signup')}>
                  Register new clinician
                </button>
              </div>
            </form>
          </div>

          {/* Direct Point-of-Care Entry */}
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.82rem', marginBottom: '0.35rem' }}>
                <Stethoscope size={14} /> Point-of-Care Assessment
              </div>
              <h2 className="panel-title">Begin clinical screening</h2>
              <p className="panel-desc" style={{ marginTop: '0.25rem' }}>
                Evaluate individual laboratory panels or import a hospital cohort CSV immediately.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
              <button
                type="button"
                className="btn btn-primary"
                style={{ justifyContent: 'space-between', padding: '0.7rem 0.95rem' }}
                onClick={onNewScreening}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ClipboardPlus size={16} /> New Patient Lab Intake
                </span>
                <ArrowRight size={15} />
              </button>

              <button
                type="button"
                className="btn"
                style={{ justifyContent: 'space-between', padding: '0.7rem 0.95rem' }}
                onClick={onOpenBatchScreening}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <FileSpreadsheet size={16} /> Batch Laboratory CSV Screening
                </span>
                <ArrowRight size={15} />
              </button>
            </div>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
              Supports conventional US (mg/dL, mg/g) and international SI (µmol/L, mg/mmol) laboratory units, CKD-EPI 2021 eGFR, KDIGO staging, and printable PDF reports.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
