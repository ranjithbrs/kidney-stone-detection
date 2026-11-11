import React, { useEffect, useState } from 'react'
import { CheckCircle2, Database, FileCheck2, Lock, RefreshCw, ShieldAlert, TrendingUp } from 'lucide-react'
import { api } from '../api'

export function VaultPage({
  user,
  storageBackend,
  activeAssessment,
  onOpenAuth,
  onLoadPatientVisits,
  vaultRefreshKey,
}) {
  const [records, setRecords] = useState([])
  const [filterPid, setFilterPid] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [attestResult, setAttestResult] = useState(null)
  const [selectedDetail, setSelectedDetail] = useState(null)

  async function loadRecords(pid = filterPid) {
    if (!user) return
    setLoading(true)
    setError('')
    try {
      const res = await api.history(pid.trim())
      setRecords(res.records || [])
    } catch (err) {
      setError(err.message || 'Could not load clinical history.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRecords()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, vaultRefreshKey])

  async function verifyRecordById(aid) {
    setError('')
    try {
      const res = await api.historyDetail(aid)
      setSelectedDetail(res)
      setAttestResult({
        verified: res.attestation_verified,
        expected_sha256: res.expected_sha256,
        recomputed_sha256: res.recomputed_sha256,
        label: `Vault Record ${aid}`,
      })
    } catch (err) {
      setError(err.message || 'Record verification failed.')
    }
  }

  async function verifyUploadedJson(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    try {
      const txt = await file.text()
      const parsed = JSON.parse(txt)
      const res = await api.verifyAttestation(parsed)
      setAttestResult({ ...res, label: file.name })
    } catch (err) {
      setError(`Could not verify uploaded JSON: ${err.message}`)
    } finally {
      e.target.value = ''
    }
  }

  async function handleLoadVisits(patientId) {
    try {
      const res = await api.patientVisits(patientId)
      onLoadPatientVisits(patientId, res.visits || [])
    } catch (err) {
      setError(err.message || 'Could not load longitudinal visits.')
    }
  }

  return (
    <div>
      {/* Storage Header Card */}
      <div className="card card-accent">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.8rem' }}>
          <div>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <Database size={18} color="#0f4c81" />
              Cloud Patient History &amp; SHA-256 Tamper-Evident Audit Vault
            </h3>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
              Active Backend: <strong>{storageBackend === 'postgresql' ? 'Supabase Cloud PostgreSQL (TLS + RLS)' : 'SQLite Vault (Cloud Ready)'}</strong>.
              Records are strictly isolated per authenticated clinician account.
            </div>
          </div>
          {!user ? (
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn btn-primary" onClick={() => onOpenAuth('signin')}>
                <Lock size={15} /> Sign In to Unlock Vault
              </button>
              <button type="button" className="btn" onClick={() => onOpenAuth('signup')}>
                Create Account
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Filter by Patient ID..."
                value={filterPid}
                onChange={(e) => setFilterPid(e.target.value)}
                style={{ padding: '0.42rem 0.65rem', borderRadius: '8px', border: '1px solid var(--border-strong)' }}
              />
              <button type="button" className="btn btn-sm" onClick={() => loadRecords()}>
                <RefreshCw size={14} /> Refresh
              </button>
            </div>
          )}
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {/* Saved History Table */}
      {user ? (
        <div className="card">
          <h3>Saved Evaluations for {user.full_name} ({records.length})</h3>
          {loading ? (
            <div>Loading saved evaluations...</div>
          ) : records.length === 0 ? (
            <div style={{ fontSize: '0.86rem', color: 'var(--muted)' }}>
              No saved assessments found yet. Run any assessment while signed in with Auto-Save enabled to persist it here.
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Patient ID</th>
                    <th>CKD Risk</th>
                    <th>eGFR</th>
                    <th>KDIGO CGA</th>
                    <th>Arbitration Tier</th>
                    <th>SHA-256 Prefix</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <tr key={r.assessment_id}>
                      <td>{String(r.recorded_at || r.observation_date || '').slice(0, 19).replace('T', ' ')}</td>
                      <td><strong>{r.patient_id}</strong></td>
                      <td>{r.e1_risk_probability != null ? `${(r.e1_risk_probability * 100).toFixed(1)}%` : 'Abstain'}</td>
                      <td>{r.egfr != null ? Number(r.egfr).toFixed(1) : '—'}</td>
                      <td><code style={{ fontSize: '0.75rem' }}>{r.kdigo_stage || '—'}</code></td>
                      <td>{r.arbitration_tier || '—'}</td>
                      <td><code>{String(r.attestation_sha256 || '').slice(0, 12)}...</code></td>
                      <td style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                        <button type="button" className="btn btn-sm" onClick={() => verifyRecordById(r.assessment_id)}>
                          Verify Hash
                        </button>
                        <button type="button" className="btn btn-sm btn-primary" onClick={() => handleLoadVisits(r.patient_id)}>
                          Load Visits
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="alert alert-info">
          Sign in or create an account above to view permanently stored patient trajectories and clinician-scoped assessments.
        </div>
      )}

      {/* Standalone SHA-256 Attestation Verifier */}
      <div className="card">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <FileCheck2 size={18} color="#0f4c81" />
          Cryptographic SHA-256 Report Attestation Verifier
        </h3>
        <p style={{ fontSize: '0.84rem', color: 'var(--muted)' }}>
          Upload any exported NEFROAI-X <code>.json</code> assessment report (or inspect a saved record above) to verify whether any
          clinical probability, eGFR, or arbitration field was altered after generation.
        </p>
        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
          <label className="btn btn-sm" style={{ cursor: 'pointer' }}>
            Upload JSON Report to Verify
            <input type="file" accept=".json,application/json" onChange={verifyUploadedJson} style={{ display: 'none' }} />
          </label>
          {activeAssessment && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={async () => {
                const res = await api.verifyAttestation(activeAssessment)
                setAttestResult({ ...res, label: `Active Session (${activeAssessment.assessment_id})` })
              }}
            >
              Verify Current Session Assessment
            </button>
          )}
        </div>

        {attestResult && (
          <div className={`alert ${attestResult.verified ? 'alert-ok' : 'alert-danger'}`} style={{ marginTop: '0.85rem', marginBottom: 0 }}>
            <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              {attestResult.verified ? <CheckCircle2 size={16} /> : <ShieldAlert size={16} />}
              {attestResult.label}: {attestResult.verified ? 'AUTHENTIC — SHA-256 MATCHES' : 'TAMPER DETECTED — HASH MISMATCH'}
            </div>
            <div style={{ fontSize: '0.78rem', marginTop: '0.3rem', fontFamily: 'monospace' }}>
              Expected: {attestResult.expected_sha256 || 'None'}
              <br />
              Computed: {attestResult.recomputed_sha256 || 'None'}
            </div>
          </div>
        )}

        {selectedDetail?.payload && (
          <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
            Loaded full attested payload for <strong>{selectedDetail.payload.patient_id}</strong> (Engine versions:{' '}
            <code>{JSON.stringify(selectedDetail.payload.engine_versions)}</code>).
          </div>
        )}
      </div>
    </div>
  )
}

export function ProgressionGuidePage({ onNavigate }) {
  return (
    <div>
      <div className="card card-accent">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <TrendingUp size={18} color="#0f4c81" />
          Engine 3 Longitudinal Progression, AKI Velocity Guard &amp; Survival ML Status
        </h3>
        <p style={{ fontSize: '0.88rem', color: 'var(--muted)' }}>
          Engine 3 tracks repeated serum creatinine / eGFR measurements over time to separate genuine KDIGO chronicity
          (&gt;=90 days persistence) from sudden acute creatinine spikes (AKI velocity guard), computes Linear Mixed Model (LMM) BLUP
          annual slopes, runs leave-last-out walk-forward trajectory backtests, and estimates 2-year / 5-year Tangri Kidney Failure Risk (KFRE).
        </p>
        <div className="alert alert-warn">
          <strong>Regulatory Governance — Survival ML Deferred:</strong> Deep/Cox survival ML extensions remain explicitly gated as{' '}
          <code>DEFERRED_PENDING_APPROVED_COHORT</code> until CRIC/UK Biobank longitudinal data-use approval is active.
        </div>
        <button type="button" className="btn btn-primary" onClick={() => onNavigate('assessment')}>
          Open Multi-Visit Trajectory Editor in CKD Assessment
        </button>
      </div>
    </div>
  )
}

export function GovernanceGuidePage({ health }) {
  return (
    <div>
      <div className="card card-accent">
        <h3>Clinical Governance, Research Boundaries &amp; Safety Rules</h3>
        <div className="grid-2" style={{ gap: '0.85rem', marginTop: '0.6rem' }}>
          <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: '0.92rem' }}>1. No Silent Healthy Imputation</h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: 0 }}>
              Missing lab analytes reduce the Clinical Reliability Index (CRI) and can trigger automatic conformal abstention rather
              than silently coercing missing measurements to healthy lab defaults.
            </p>
          </div>
          <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: '0.92rem' }}>2. Strict Schema &amp; Leak-Free Split</h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: 0 }}>
              Non-renal datasets (such as calcium-oxalate stone CSVs) are rejected before inference. All SMOTE, scalers, and conformal
              quantiles fit strictly inside UCI training partitions (N=320), keeping N=80 isolated.
            </p>
          </div>
          <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: '0.92rem' }}>3. Non-Compensatory Safety-Max Arbitration</h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: 0 }}>
              Even when Engine 1 ML predicts low risk, severe KDIGO albuminuria (A3) or contradictory hematology ratios escalate the
              unified Safety-Max tier via explicit rules DISC-01 through DISC-10.
            </p>
          </div>
          <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: '0.92rem' }}>4. Cryptographic Model Provenance</h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: 0 }}>
              Protected Champion Random Forest artifact SHA-256: <br />
              <code style={{ wordBreak: 'break-all', fontSize: '0.73rem' }}>{health?.protected_model_sha256 || 'Verifying...'}</code>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
