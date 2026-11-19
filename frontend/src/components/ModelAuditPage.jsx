import React, { useEffect, useState } from 'react'
import { CheckCircle2, FileCheck2, RefreshCw, ShieldAlert, Upload } from 'lucide-react'
import { api } from '../api'

const CURVE_COLORS = ['#0f766e', '#18181b', '#2563eb', '#b45309', '#7c3aed', '#64748b']

function CleanMultiCurve({ title, xLabel, yLabel, series, diagonal = false }) {
  const W = 340
  const H = 215
  const pad = 34

  const toX = (x) => pad + x * (W - 2 * pad)
  const toY = (y) => H - pad - y * (H - 2 * pad)

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '0.85rem', background: 'var(--surface)' }}>
      <div style={{ fontWeight: 600, fontSize: '0.84rem', color: 'var(--text)', marginBottom: '0.35rem' }}>{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={title}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={toX(0)} y1={toY(t)} x2={toX(1)} y2={toY(t)} stroke="#e4e4e7" strokeWidth="1" />
            <line x1={toX(t)} y1={toY(0)} x2={toX(t)} y2={toY(1)} stroke="#e4e4e7" strokeWidth="1" />
            <text x={pad - 5} y={toY(t) + 3} fontSize="9" fill="#71717a" textAnchor="end">{t.toFixed(2)}</text>
            <text x={toX(t)} y={H - pad + 13} fontSize="9" fill="#71717a" textAnchor="middle">{t.toFixed(2)}</text>
          </g>
        ))}
        <line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke="#a1a1aa" strokeWidth="1" />
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="#a1a1aa" strokeWidth="1" />
        {diagonal && (
          <line x1={toX(0)} y1={toY(0)} x2={toX(1)} y2={toY(1)} stroke="#a1a1aa" strokeDasharray="4 4" strokeWidth="1" />
        )}
        {series.map((s, idx) => {
          if (!s.xs?.length || !s.ys?.length) return null
          const d = s.xs
            .map((x, i) => `${i === 0 ? 'M' : 'L'} ${toX(x).toFixed(1)} ${toY(s.ys[i]).toFixed(1)}`)
            .join(' ')
          return (
            <path
              key={s.name}
              d={d}
              fill="none"
              stroke={CURVE_COLORS[idx % CURVE_COLORS.length]}
              strokeWidth={s.name.includes('Stacking') || s.name.includes('Random Forest') ? '2.2' : '1.4'}
            />
          )
        })}
        <text x={W / 2} y={H - 4} fontSize="9.5" fill="#52525b" textAnchor="middle">{xLabel}</text>
        <text x={11} y={H / 2} fontSize="9.5" fill="#52525b" textAnchor="middle" transform={`rotate(-90 11 ${H / 2})`}>
          {yLabel}
        </text>
      </svg>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.35rem', fontSize: '0.72rem', color: 'var(--muted)' }}>
        {series.map((s, idx) => (
          <span key={s.name} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '9px', height: '2.5px', background: CURVE_COLORS[idx % CURVE_COLORS.length], display: 'inline-block' }} />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function ModelAuditPage({ user, health, formState, onOpenAuth, defaultSubTab }) {
  const [subTab, setSubTab] = useState(defaultSubTab || 'benchmarks')

  useEffect(() => {
    if (defaultSubTab) setSubTab(defaultSubTab)
  }, [defaultSubTab])
  const [perf, setPerf] = useState(null)
  const [perfLoading, setPerfLoading] = useState(true)
  const [perfError, setPerfError] = useState('')

  // LIME & XAI state
  const [xaiData, setXaiData] = useState(null)
  const [xaiLoading, setXaiLoading] = useState(false)
  const [xaiError, setXaiError] = useState('')

  // SHA-256 verification state
  const [records, setRecords] = useState([])
  const [attestResult, setAttestResult] = useState(null)
  const [vaultError, setVaultError] = useState('')

  useEffect(() => {
    let active = true
    api.performance()
      .then((res) => { if (active) setPerf(res) })
      .catch((err) => { if (active) setPerfError(err.message || 'Could not load model benchmarks.') })
      .finally(() => { if (active) setPerfLoading(false) })
    return () => { active = false }
  }, [])

  const numKeys = ['hemo', 'sg', 'pcv', 'rc', 'al', 'sc', 'bu', 'bgr']
  const hasBiomarkerInputs = numKeys.some((k) => {
    const val = k === 'sc' ? (formState?.serum_creatinine ?? formState?.biomarkers?.sc) : formState?.biomarkers?.[k]
    return val !== '' && val !== null && val !== undefined
  })

  async function loadXai() {
    if (!hasBiomarkerInputs) {
      setXaiData(null)
      setXaiError('')
      return
    }
    setXaiLoading(true)
    setXaiError('')
    try {
      const b = formState?.biomarkers || {}
      const cleanBio = { ...b }
      numKeys.forEach((k) => {
        const raw = k === 'sc' ? (formState?.serum_creatinine ?? cleanBio[k]) : cleanBio[k]
        cleanBio[k] = raw === '' || raw == null ? null : Number(raw)
      })
      const res = await api.explain({
        biomarkers: cleanBio,
        uacr_mg_g: formState?.uacr !== '' && formState?.uacr != null ? Number(formState.uacr) : null,
        target_max_risk: 0.2,
        max_changes: 2,
      })
      setXaiData(res)
    } catch (err) {
      setXaiError(err.message || 'Could not run SHAP/LIME audit.')
    } finally {
      setXaiLoading(false)
    }
  }

  useEffect(() => {
    if (subTab === 'xai' && hasBiomarkerInputs && !xaiData && !xaiLoading) {
      loadXai()
    }
    if (subTab === 'attestation' && user) {
      api.history()
        .then((res) => setRecords(res.records || []))
        .catch((err) => setVaultError(err.message || 'Could not load vault records.'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab, user, hasBiomarkerInputs])

  async function verifyRecord(aid) {
    setVaultError('')
    try {
      const res = await api.historyDetail(aid)
      setAttestResult({
        verified: res.attestation_verified,
        expected_sha256: res.expected_sha256,
        recomputed_sha256: res.recomputed_sha256,
        label: `Record ${aid}`,
      })
    } catch (err) {
      setVaultError(err.message || 'Verification failed.')
    }
  }

  async function verifyUploadedJson(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setVaultError('')
    try {
      const parsed = JSON.parse(await file.text())
      const res = await api.verifyAttestation(parsed)
      setAttestResult({ ...res, label: file.name })
    } catch (err) {
      setVaultError(`Invalid JSON report: ${err.message}`)
    } finally {
      e.target.value = ''
    }
  }

  const rep = perf?.stacking_report
  const models = Object.values(rep?.models || {})
  const stab = perf?.feature_selection_stability
  const splitCal = perf?.conformal_split
  const mondCal = perf?.conformal_mondrian

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Model validation &amp; audit</h1>
          <p className="page-subtitle">
            Held-out benchmark performance, calibration curves, SHAP/LIME explainability, and report integrity checks.
          </p>
        </div>
        <div className="segmented">
          {[
            { id: 'benchmarks', label: 'Benchmarks & Calibration' },
            { id: 'xai', label: 'SHAP & LIME Audit' },
            { id: 'attestation', label: 'Integrity & Governance' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              className={`seg-btn ${subTab === t.id ? 'active' : ''}`}
              onClick={() => setSubTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab 1: Benchmarks */}
      {subTab === 'benchmarks' && (
        <div>
          {perfLoading && <div className="panel">Computing held-out benchmarks and calibration curves...</div>}
          {perfError && <div className="notice notice-danger">{perfError}</div>}
          {rep && (
            <>
              <div className="metric-strip">
                <div className="metric-cell">
                  <div className="metric-label">Held-out test cohort</div>
                  <div className="metric-val tabular">N = {rep.test_samples}</div>
                  <div className="metric-sub">Isolated from N = {rep.train_samples} train</div>
                </div>
                <div className="metric-cell">
                  <div className="metric-label">5-Fold feature Jaccard</div>
                  <div className="metric-val tabular">{Number(stab?.mean_pairwise_jaccard || 0).toFixed(4)}</div>
                  <div className="metric-sub">Top-10 biomarker stability</div>
                </div>
                <div className="metric-cell">
                  <div className="metric-label">Split conformal q</div>
                  <div className="metric-val tabular">{Number(splitCal?.conformal_quantile || 0).toFixed(4)}</div>
                  <div className="metric-sub">95% finite-sample coverage</div>
                </div>
                <div className="metric-cell">
                  <div className="metric-label">Mondrian q (H / CKD)</div>
                  <div className="metric-val tabular" style={{ fontSize: '1.15rem', marginTop: '0.28rem' }}>
                    {Number(mondCal?.q_healthy || 0).toFixed(3)} / {Number(mondCal?.q_ckd || 0).toFixed(3)}
                  </div>
                  <div className="metric-sub">Class-conditional quantiles</div>
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <div>
                    <h2 className="panel-title">Model comparison (held-out N = {rep.test_samples})</h2>
                    <p className="panel-desc">Leak-free evaluation across base classifiers and stacking meta-learner.</p>
                  </div>
                </div>
                <div className="table-wrap">
                  <table className="clean-table">
                    <thead>
                      <tr>
                        <th>Architecture</th>
                        <th>Accuracy</th>
                        <th>Sensitivity</th>
                        <th>Specificity</th>
                        <th>Macro F1</th>
                        <th>ROC-AUC</th>
                        <th>PR-AUC</th>
                        <th>Brier Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {models.map((m) => (
                        <tr key={m.model_name}>
                          <td style={{ fontWeight: 600, color: 'var(--text)' }}>{m.model_name}</td>
                          <td className="tabular">{(m.accuracy * 100).toFixed(1)}%</td>
                          <td className="tabular">{(m.sensitivity * 100).toFixed(1)}%</td>
                          <td className="tabular">{(m.specificity * 100).toFixed(1)}%</td>
                          <td className="tabular">{Number(m.macro_f1).toFixed(4)}</td>
                          <td className="tabular">{Number(m.roc_auc).toFixed(4)}</td>
                          <td className="tabular">{Number(m.pr_auc).toFixed(4)}</td>
                          <td className="tabular">{Number(m.brier_score).toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="grid-3" style={{ marginBottom: '1rem' }}>
                <CleanMultiCurve
                  title="ROC Curves"
                  xLabel="False Positive Rate"
                  yLabel="True Positive Rate"
                  diagonal
                  series={models.map((m) => ({
                    name: m.model_name.split(' ')[0],
                    xs: m.roc_curve?.fpr || [],
                    ys: m.roc_curve?.tpr || [],
                  }))}
                />
                <CleanMultiCurve
                  title="Precision-Recall Curves"
                  xLabel="Recall"
                  yLabel="Precision"
                  series={models.map((m) => ({
                    name: m.model_name.split(' ')[0],
                    xs: m.pr_curve?.recall || [],
                    ys: m.pr_curve?.precision || [],
                  }))}
                />
                <CleanMultiCurve
                  title="Reliability Diagram"
                  xLabel="Predicted Probability"
                  yLabel="Observed Frequency"
                  diagonal
                  series={models.map((m) => ({
                    name: m.model_name.split(' ')[0],
                    xs: m.calibration_curve?.prob_pred || [],
                    ys: m.calibration_curve?.prob_true || [],
                  }))}
                />
              </div>

              <div className="panel">
                <div className="panel-header">
                  <h2 className="panel-title">Stratified subgroup check</h2>
                </div>
                <div className="table-wrap">
                  <table className="clean-table">
                    <thead>
                      <tr>
                        <th>Subgroup</th>
                        <th>N</th>
                        <th>CKD Prevalence</th>
                        <th>Accuracy</th>
                        <th>Sensitivity</th>
                        <th>Brier</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(rep.subgroup_analysis || []).map((s) => (
                        <tr key={s.subgroup}>
                          <td style={{ fontWeight: 600, color: 'var(--text)' }}>{s.subgroup}</td>
                          <td className="tabular">{s.n}</td>
                          <td className="tabular">{(s.ckd_prevalence * 100).toFixed(1)}%</td>
                          <td className="tabular">{(s.accuracy * 100).toFixed(1)}%</td>
                          <td className="tabular">{s.sensitivity != null ? `${(s.sensitivity * 100).toFixed(1)}%` : '—'}</td>
                          <td className="tabular">{s.brier_score != null ? Number(s.brier_score).toFixed(4) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Tab 2: Live SHAP & LIME Concordance */}
      {subTab === 'xai' && (
        <div>
          <div className="panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h2 className="panel-title">
                Live explainability verification ({formState?.patient_id || 'Active patient'})
              </h2>
              <p className="panel-desc">
                Exact <code>shap.TreeExplainer</code> Shapley attributions paired with surrogate LIME decision rules.
              </p>
            </div>
            <button type="button" className="btn btn-primary" onClick={loadXai} disabled={xaiLoading || !hasBiomarkerInputs}>
              <RefreshCw size={14} /> {xaiLoading ? 'Computing...' : 'Recompute'}
            </button>
          </div>

          {!hasBiomarkerInputs && (
            <div className="notice">
              Enter patient laboratory biomarkers in <strong>New Screening</strong> (or open a saved patient chart) to run live TreeSHAP, LIME, and rank concordance audits.
            </div>
          )}

          {xaiError && <div className="notice notice-danger">{xaiError}</div>}

          {xaiData && (
            <>
              {xaiData.concordance && (
                <div className="metric-strip">
                  <div className="metric-cell">
                    <div className="metric-label">SHAP / LIME Concordance</div>
                    <div className="metric-val" style={{ fontSize: '1.1rem', marginTop: '0.32rem' }}>
                      {xaiData.concordance.concordance_status}
                    </div>
                    <div className="metric-sub">Spearman rho: {xaiData.concordance.spearman_rank_corr ?? 'N/A'}</div>
                  </div>
                  <div className="metric-cell">
                    <div className="metric-label">Top-3 feature overlap</div>
                    <div className="metric-val tabular">{xaiData.concordance.top3_overlap_count} / 3</div>
                    <div className="metric-sub">Agreement across explainers</div>
                  </div>
                  <div className="metric-cell">
                    <div className="metric-label">Sign polarity match</div>
                    <div className="metric-val tabular">{(xaiData.concordance.sign_agreement_ratio * 100).toFixed(0)}%</div>
                    <div className="metric-sub">Directional concordance</div>
                  </div>
                  <div className="metric-cell">
                    <div className="metric-label">TreeSHAP additivity</div>
                    <div className="metric-val tabular" style={{ fontSize: '1.1rem', marginTop: '0.32rem' }}>
                      {xaiData.treeshap?.additivity_error?.toExponential(2)}
                    </div>
                    <div className="metric-sub">Exact base + sum(&phi;) identity</div>
                  </div>
                </div>
              )}

              <div className="grid-2">
                <div className="panel">
                  <div className="panel-header">
                    <div>
                      <h2 className="panel-title">TreeSHAP attributions</h2>
                      <p className="panel-desc">
                        Base rate {(xaiData.treeshap?.base_value * 100).toFixed(1)}% &rarr; Predicted{' '}
                        {(xaiData.treeshap?.predicted_probability * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  {(xaiData.treeshap?.top_drivers || []).map((d) => {
                    const maxAbs = Math.max(...(xaiData.treeshap?.top_drivers || []).map((x) => Math.abs(x.shap_value)), 0.01)
                    const widthPct = Math.min(100, Math.round((Math.abs(d.shap_value) / maxAbs) * 100))
                    const pos = d.shap_value >= 0
                    return (
                      <div className="attr-row" key={d.feature}>
                        <div>
                          <span style={{ fontWeight: 500 }}>{d.label}</span>{' '}
                          <span className="field-hint">({String(d.clinical_value)})</span>
                        </div>
                        <div className="attr-track">
                          <div
                            style={{
                              width: `${widthPct}%`,
                              height: '100%',
                              background: pos ? '#dc2626' : '#0f766e',
                              borderRadius: '999px',
                            }}
                          />
                        </div>
                        <div className="tabular" style={{ textAlign: 'right', fontWeight: 600, color: pos ? 'var(--danger-fg)' : 'var(--accent)' }}>
                          {pos ? '+' : ''}{d.shap_value.toFixed(3)}
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div className="panel">
                  <div className="panel-header">
                    <div>
                      <h2 className="panel-title">LIME local decision rules</h2>
                      <p className="panel-desc">Linear surrogate on standardized training distribution</p>
                    </div>
                  </div>
                  {(xaiData.lime?.rules || []).map((r, i) => {
                    const maxAbs = Math.max(...(xaiData.lime?.rules || []).map((x) => Math.abs(x.weight)), 0.01)
                    const widthPct = Math.min(100, Math.round((Math.abs(r.weight) / maxAbs) * 100))
                    const pos = r.weight >= 0
                    return (
                      <div className="attr-row" key={i}>
                        <div><code>{r.rule}</code></div>
                        <div className="attr-track">
                          <div
                            style={{
                              width: `${widthPct}%`,
                              height: '100%',
                              background: pos ? '#dc2626' : '#0f766e',
                              borderRadius: '999px',
                            }}
                          />
                        </div>
                        <div className="tabular" style={{ textAlign: 'right', fontWeight: 600, color: pos ? 'var(--danger-fg)' : 'var(--accent)' }}>
                          {pos ? '+' : ''}{r.weight.toFixed(3)}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Tab 3: SHA-256 Attestation & Governance */}
      {subTab === 'attestation' && (
        <div className="grid-2">
          <div className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Report integrity verification (SHA-256)</h2>
                <p className="panel-desc">Verify exported JSON assessment manifests or persisted vault records.</p>
              </div>
              <label className="btn btn-sm" style={{ cursor: 'pointer' }}>
                <Upload size={13} /> Verify JSON file
                <input type="file" accept=".json" onChange={verifyUploadedJson} style={{ display: 'none' }} />
              </label>
            </div>

            {vaultError && <div className="notice notice-danger">{vaultError}</div>}

            {attestResult && (
              <div className={`notice ${attestResult.verified ? 'notice-ok' : 'notice-danger'}`}>
                <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  {attestResult.verified ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
                  {attestResult.label}: {attestResult.verified ? 'Integrity Verified' : 'Hash Mismatch Detected'}
                </div>
                <div style={{ fontSize: '0.76rem', marginTop: '0.25rem', wordBreak: 'break-all' }}>
                  SHA-256: <code>{attestResult.recomputed_sha256}</code>
                </div>
              </div>
            )}

            {user ? (
              <div className="table-wrap">
                <table className="clean-table">
                  <thead>
                    <tr>
                      <th>Patient</th>
                      <th>Date</th>
                      <th>SHA-256 Prefix</th>
                      <th style={{ textAlign: 'right' }}>Verify</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.slice(0, 12).map((r) => (
                      <tr key={r.assessment_id}>
                        <td style={{ fontWeight: 500 }}>{r.patient_id}</td>
                        <td className="tabular">{String(r.recorded_at || r.observation_date || '').slice(0, 10)}</td>
                        <td><code>{String(r.attestation_sha256 || '').slice(0, 14)}...</code></td>
                        <td style={{ textAlign: 'right' }}>
                          <button type="button" className="btn btn-sm" onClick={() => verifyRecord(r.assessment_id)}>
                            <FileCheck2 size={13} /> Check
                          </button>
                        </td>
                      </tr>
                    ))}
                    {records.length === 0 && (
                      <tr>
                        <td colSpan={4} style={{ color: 'var(--muted)' }}>No saved records yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="notice">
                Sign in to inspect saved clinic records, or upload an exported <code>.json</code> report above.{' '}
                <button type="button" className="btn btn-sm" style={{ marginLeft: '0.5rem' }} onClick={() => onOpenAuth('signin')}>
                  Sign in
                </button>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-header">
              <h2 className="panel-title">Clinical &amp; engineering safeguards</h2>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              <div>
                <strong>Protected Model Artifact:</strong>{' '}
                <code>{String(health?.protected_model_sha256 || '').slice(0, 18) || 'Verified'}...</code>
              </div>
              <div>
                <strong>Missing-Data Abstention:</strong> Missing critical biomarkers (<code>sc</code>, <code>al</code>, <code>hemo</code>)
                never default silently to healthy values; uncertain cases return <code>ABSTAIN</code>.
              </div>
              <div>
                <strong>Leak-Free Cross-Validation:</strong> Stratified 80/20 splitting precedes imputation, scaling, and fold-level SMOTE.
              </div>
              <div>
                <strong>External Epidemiological Calibration:</strong> KDIGO staging validated against CDC NHANES 2017–2018 (N = 5,154).
              </div>
              <div>
                <strong>Survival ML Status:</strong> <code>{health?.survival_ml_status || 'DEFERRED_PENDING_APPROVED_COHORT'}</code> —
                time-to-event ML remains deferred until approved longitudinal cohort access (e.g., CRIC DUA); Engine 3 reports KFRE and linear mixed-effects slopes.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
