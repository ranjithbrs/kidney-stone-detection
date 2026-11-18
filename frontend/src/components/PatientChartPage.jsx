import React, { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Download,
  FileText,
  Plus,
  RefreshCw,
  Sliders,
} from 'lucide-react'
import { api } from '../api'
import {
  computeCkdepi2021Egfr,
  formatCgaStage,
  formatChronicityLabel,
  formatRuleName,
  formatStageCareGuidance,
  formatTriageTier,
  getTierBadgeClass,
} from '../clinicalMeta'

function toNullableNum(v) {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function buildCleanBiomarkers(raw) {
  const b = raw || {}
  const numKeys = ['hemo', 'sg', 'pcv', 'rc', 'al', 'sc', 'bu', 'bgr']
  const out = {}
  for (const k of numKeys) {
    out[k] = toNullableNum(b[k])
  }
  out.htn = b.htn || 'no'
  out.dm = b.dm || 'no'
  return out
}

function EgfrTrendChart({ points, slope }) {
  if (!points.length) {
    return (
      <div
        style={{
          height: 220,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--muted)',
          fontSize: '0.84rem',
          border: '1px dashed var(--border)',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        Add at least one serum creatinine reading to render eGFR trajectory.
      </div>
    )
  }

  const W = 620
  const H = 225
  const padL = 44
  const padR = 24
  const padT = 18
  const padB = 34
  const plotW = W - padL - padR
  const plotH = H - padT - padB

  const maxY = Math.max(120, ...points.map((p) => p.egfr + 10))
  const minY = 0
  const xFor = (idx) =>
    points.length === 1
      ? padL + plotW / 2
      : padL + (idx / (points.length - 1)) * plotW
  const yFor = (val) =>
    padT + plotH - ((Math.max(minY, Math.min(maxY, val)) - minY) / (maxY - minY)) * plotH

  const polylinePts = points.map((p, i) => `${xFor(i).toFixed(1)},${yFor(p.egfr).toFixed(1)}`).join(' ')
  const y60 = yFor(60)
  const y30 = yFor(30)

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: 'auto', display: 'block' }}
      role="img"
      aria-label="Longitudinal eGFR trajectory chart"
    >
      {/* Subtle G3a / G4 shading zones */}
      <rect x={padL} y={y60} width={plotW} height={y30 - y60} fill="#fef9c3" opacity="0.45" />
      <rect x={padL} y={y30} width={plotW} height={padT + plotH - y30} fill="#fee2e2" opacity="0.45" />

      {/* Reference grid lines */}
      {[0, 30, 60, 90, 120].map((tick) => {
        if (tick > maxY) return null
        const y = yFor(tick)
        const isThreshold = tick === 60 || tick === 30
        return (
          <g key={tick}>
            <line
              x1={padL}
              y1={y}
              x2={padL + plotW}
              y2={y}
              stroke={isThreshold ? '#d4d4d8' : '#e4e4e7'}
              strokeDasharray={isThreshold ? '4 4' : undefined}
              strokeWidth="1"
            />
            <text
              x={padL - 8}
              y={y + 3}
              textAnchor="end"
              fontSize="10"
              fill="#71717a"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {tick}
            </text>
          </g>
        )
      })}

      {/* Threshold labels */}
      <text x={padL + plotW - 4} y={y60 - 4} textAnchor="end" fontSize="9.5" fill="#92400e">
        60 (Stage G3a)
      </text>
      <text x={padL + plotW - 4} y={y30 - 4} textAnchor="end" fontSize="9.5" fill="#991b1b">
        30 (Stage G4)
      </text>

      {/* Trajectory Line */}
      {points.length > 1 && (
        <polyline
          fill="none"
          stroke="#0f766e"
          strokeWidth="2.4"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={polylinePts}
        />
      )}

      {/* Data Points + Date Labels */}
      {points.map((p, i) => {
        const cx = xFor(i)
        const cy = yFor(p.egfr)
        const isCurrent = p.isCurrent
        return (
          <g key={`${p.date}-${i}`}>
            <circle
              cx={cx}
              cy={cy}
              r={isCurrent ? 5.5 : 4}
              fill={isCurrent ? '#0f766e' : '#ffffff'}
              stroke="#0f766e"
              strokeWidth="2"
            />
            <text
              x={cx}
              y={cy - 10}
              textAnchor="middle"
              fontSize="10.5"
              fontWeight={isCurrent ? '700' : '600'}
              fill="#09090b"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {p.egfr.toFixed(1)}
            </text>
            <text
              x={cx}
              y={H - 10}
              textAnchor="middle"
              fontSize="10"
              fill={isCurrent ? '#0f766e' : '#71717a'}
              fontWeight={isCurrent ? '600' : '400'}
            >
              {String(p.date || '').slice(0, 10)}
            </text>
          </g>
        )
      })}

      {/* Axis border */}
      <line x1={padL} y1={padT} x2={padL} y2={padT + plotH} stroke="#d4d4d8" strokeWidth="1" />
      <line x1={padL} y1={padT + plotH} x2={padL + plotW} y2={padT + plotH} stroke="#d4d4d8" strokeWidth="1" />

      {slope != null && Number.isFinite(Number(slope)) && (
        <text x={padL + 6} y={padT + 12} fontSize="10" fill="#52525b">
          Annualized slope: {Number(slope) >= 0 ? `+${Number(slope).toFixed(2)}` : Number(slope).toFixed(2)} mL/min/yr
        </text>
      )}
    </svg>
  )
}

export default function PatientChartPage({
  patientId,
  formState,
  setFormState,
  assessment,
  setAssessment,
  user,
  onNavigateToScreening,
  onVaultUpdated,
}) {
  const [explainData, setExplainData] = useState(null)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState('')
  const [targetRisk, setTargetRisk] = useState(0.35)
  const [maxChanges, setMaxChanges] = useState(3)

  const [newVisit, setNewVisit] = useState({
    date: new Date().toISOString().slice(0, 10),
    scr: '',
    uacr: '',
    sbp: '125',
  })
  const [savingVisit, setSavingVisit] = useState(false)
  const [visitError, setVisitError] = useState('')
  const [downloadingFmt, setDownloadingFmt] = useState('')

  const e1 = assessment?.engine1_result || {}
  const e2 = assessment?.engine2_result || {}
  const e3 = assessment?.engine3_result || {}
  const arb = assessment?.overall_completeness?.arbitration_detail || {}
  const discrepancies = assessment?.clinical_discrepancies || []
  const sha = assessment?.provenance?.attestation_sha256

  const activePatientId = patientId || formState?.patient_id || 'Unknown Patient'

  // Build ordered eGFR points combining historical visits + current reading
  const trajectoryPoints = useMemo(() => {
    const visits = Array.isArray(formState?.visits) ? formState.visits : []
    const pts = visits
      .map((v) => {
        const val = computeCkdepi2021Egfr(v.scr, formState?.age, formState?.sex)
        return val != null
          ? {
              date: v.date,
              scr: Number(v.scr),
              uacr: v.uacr != null ? Number(v.uacr) : null,
              sbp: v.sbp != null ? Number(v.sbp) : null,
              egfr: val,
              isCurrent: false,
            }
          : null
      })
      .filter(Boolean)

    if (e2?.egfr != null) {
      const obsDate = formState?.observation_date || new Date().toISOString().slice(0, 10)
      pts.push({
        date: obsDate,
        scr: toNullableNum(formState?.serum_creatinine),
        uacr: e2.uacr != null ? Number(e2.uacr) : toNullableNum(formState?.uacr),
        sbp: null,
        egfr: Number(e2.egfr),
        isCurrent: true,
      })
    }

    return pts.sort((a, b) => String(a.date).localeCompare(String(b.date)))
  }, [formState, e2?.egfr, e2?.uacr])

  async function runExplain(customTarget = targetRisk, customMax = maxChanges) {
    if (!assessment) return
    setExplainLoading(true)
    setExplainError('')
    try {
      const payload = {
        biomarkers: buildCleanBiomarkers(formState?.biomarkers),
        uacr_mg_g: e2?.uacr ?? toNullableNum(formState?.uacr),
        target_max_risk: Number(customTarget),
        max_changes: Number(customMax),
      }
      const res = await api.explain(payload)
      setExplainData(res)
    } catch (err) {
      setExplainError(err.message || 'Unable to compute Shapley & counterfactual explanation.')
    } finally {
      setExplainLoading(false)
    }
  }

  useEffect(() => {
    if (assessment) {
      runExplain(targetRisk, maxChanges)
    } else {
      setExplainData(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assessment?.provenance?.attestation_sha256])

  async function handleDownload(fmt) {
    if (!assessment) return
    setDownloadingFmt(fmt)
    try {
      await api.downloadReport(fmt, assessment, formState?.visits || [])
    } catch (err) {
      setVisitError(err.message || `Export failed (${fmt.toUpperCase()}).`)
    } finally {
      setDownloadingFmt('')
    }
  }

  async function handleAddVisitAndRerun(e) {
    e.preventDefault()
    const scrVal = toNullableNum(newVisit.scr)
    if (scrVal == null || scrVal <= 0) {
      setVisitError('Enter a valid serum creatinine value (mg/dL) for the visit.')
      return
    }
    setSavingVisit(true)
    setVisitError('')
    try {
      const nextVisitEntry = {
        date: newVisit.date || new Date().toISOString().slice(0, 10),
        scr: scrVal,
        uacr: toNullableNum(newVisit.uacr) ?? 15.0,
        sbp: toNullableNum(newVisit.sbp) ?? 125.0,
      }
      const updatedVisits = [...(formState?.visits || []), nextVisitEntry]
      const updatedForm = { ...formState, visits: updatedVisits }
      setFormState(updatedForm)

      const assessPayload = {
        patient_id: updatedForm.patient_id,
        age: Number(updatedForm.age),
        sex: updatedForm.sex,
        observation_date: updatedForm.observation_date,
        biomarkers: buildCleanBiomarkers(updatedForm.biomarkers),
        serum_creatinine: toNullableNum(updatedForm.serum_creatinine),
        serum_creatinine_unit: updatedForm.serum_creatinine_unit || 'mg/dL',
        uacr: toNullableNum(updatedForm.uacr),
        uacr_unit: updatedForm.uacr_unit || 'mg/g',
        visits: updatedVisits,
        save_to_vault: Boolean(user),
      }
      const res = await api.assess(assessPayload)
      setAssessment(res.assessment)
      setNewVisit((prev) => ({ ...prev, scr: '', uacr: '' }))
      if (res.saved_to_vault && onVaultUpdated) onVaultUpdated()
    } catch (err) {
      setVisitError(err.message || 'Failed to add visit and recompute assessment.')
    } finally {
      setSavingVisit(false)
    }
  }

  if (!assessment) {
    return (
      <div>
        <div className="page-header">
          <div>
            <h1 className="page-title">Patient Chart</h1>
            <p className="page-subtitle">
              Longitudinal eGFR trajectory, KDIGO staging guidance, and target lab planning.
            </p>
          </div>
        </div>
        <div className="panel" style={{ textAlign: 'center', padding: '2.5rem 1.5rem' }}>
          <Activity size={28} color="var(--muted)" style={{ marginBottom: '0.6rem' }} />
          <h2 className="panel-title">No active patient evaluation loaded</h2>
          <p className="panel-desc" style={{ maxWidth: 460, margin: '0.35rem auto 1rem' }}>
            Run a new screening assessment or select a saved patient from the Patients queue to inspect their longitudinal chart.
          </p>
          <button type="button" className="btn btn-primary" onClick={onNavigateToScreening}>
            Go to New screening <ArrowRight size={14} />
          </button>
        </div>
      </div>
    )
  }

  const careGuidance = formatStageCareGuidance(e2?.gfr_category, e2?.albuminuria_category)
  const drivers = explainData?.treeshap?.top_drivers || []
  const maxAbsShap = Math.max(0.01, ...drivers.map((d) => Math.abs(d.shap_value || 0)))
  const cf = explainData?.counterfactual
  const akiAssess = e3?.chronicity_aki_assessment || {}

  return (
    <div>
      {/* Chart Header */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
            <h1 className="page-title tabular">{activePatientId}</h1>
            <span className="badge badge-neutral">
              {formState?.age || '—'} yrs · {String(formState?.sex || '').toLowerCase() === 'female' ? 'Female' : 'Male'}
            </span>
            <span className="badge badge-teal">
              {formatCgaStage(e2?.gfr_category, e2?.albuminuria_category, e2?.cga_string)}
            </span>
            <span className={`badge ${getTierBadgeClass(arb.tier)}`}>
              {formatTriageTier(arb.tier)}
            </span>
          </div>
          <p className="page-subtitle">
            {arb.recommended_action || 'Clinical screening summary and multi-visit renal progression chart.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-sm" onClick={onNavigateToScreening}>
            Edit intake
          </button>
          {['pdf', 'json', 'txt'].map((fmt) => (
            <button
              key={fmt}
              type="button"
              className="btn btn-sm"
              disabled={downloadingFmt === fmt}
              onClick={() => handleDownload(fmt)}
            >
              <Download size={13} /> {downloadingFmt === fmt ? '...' : fmt.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* 4-Column Clinical KPI Strip */}
      <div className="metric-strip">
        <div className="metric-cell">
          <div className="metric-label">Current eGFR (CKD-EPI 2021)</div>
          <div className="metric-val tabular">
            {e2?.egfr != null ? `${Number(e2.egfr).toFixed(1)}` : '—'}
            <span style={{ fontSize: '0.82rem', fontWeight: 500, color: 'var(--muted)', marginLeft: 4 }}>
              mL/min/1.73m²
            </span>
          </div>
          <div className="metric-sub">
            {e2?.gfr_category || 'Pending'} — {e2?.gfr_description || 'Creatinine required'}
          </div>
        </div>

        <div className="metric-cell">
          <div className="metric-label">Urine ACR (Albuminuria)</div>
          <div className="metric-val tabular">
            {e2?.uacr != null ? `${Number(e2.uacr).toFixed(1)}` : '—'}
            <span style={{ fontSize: '0.82rem', fontWeight: 500, color: 'var(--muted)', marginLeft: 4 }}>
              mg/g
            </span>
          </div>
          <div className="metric-sub">
            Category: {e2?.albuminuria_category || 'Not measured'}
          </div>
        </div>

        <div className="metric-cell">
          <div className="metric-label">5-Year Kidney Failure Risk</div>
          <div className="metric-val tabular">
            {e3?.kfre_5year_risk != null ? `${(Number(e3.kfre_5year_risk) * 100).toFixed(1)}%` : 'N/A'}
          </div>
          <div className="metric-sub tabular">
            {e3?.kfre_2year_risk != null
              ? `2-year KFRE: ${(Number(e3.kfre_2year_risk) * 100).toFixed(1)}%`
              : e3?.kfre_applicability_explanation || 'Tangri KFRE (G3–G5, age 18–90)'}
          </div>
        </div>

        <div className="metric-cell">
          <div className="metric-label">CKD Screening Model Risk</div>
          <div className="metric-val tabular">
            {e1?.risk_probability != null ? `${(Number(e1.risk_probability) * 100).toFixed(1)}%` : 'Held'}
          </div>
          <div className="metric-sub">
            Panel quality {e1?.clinical_reliability_index != null ? `${Math.round(Number(e1.clinical_reliability_index) * 100)}%` : '—'} · {formatChronicityLabel(e2?.cga_string)}
          </div>
        </div>
      </div>

      {/* Discrepancy / AKI Alerts if present */}
      {(discrepancies.length > 0 || akiAssess.aki_velocity_alert) && (
        <div className="notice notice-warn">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontWeight: 600, marginBottom: '0.35rem' }}>
            <AlertTriangle size={15} /> Active Clinical Safety Notices
          </div>
          {akiAssess.aki_velocity_alert && (
            <div style={{ fontSize: '0.82rem', marginBottom: '0.25rem' }}>
              <strong>AKI Velocity Alert:</strong> {akiAssess.classification || 'Rapid creatinine elevation detected — rule out acute kidney injury before confirming CKD chronicity.'}
            </div>
          )}
          {discrepancies.map((d) => (
            <div key={d.discrepancy_id} style={{ fontSize: '0.82rem', marginTop: '0.2rem' }}>
              <strong>{d.title}:</strong> {d.clinical_action || d.description}
            </div>
          ))}
        </div>
      )}

      {/* Main Chart + Care Plan Grid */}
      <div className="grid-2">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Longitudinal eGFR Trajectory</h2>
              <p className="panel-desc">
                {trajectoryPoints.length} timepoint{trajectoryPoints.length === 1 ? '' : 's'} ·{' '}
                {e3?.slope_status || akiAssess.classification || 'CKD-EPI 2021 trajectory'}
              </p>
            </div>
            {e3?.lmm_annual_slope != null && (
              <span className="badge badge-neutral tabular">
                LMM slope {Number(e3.lmm_annual_slope).toFixed(2)} /yr
              </span>
            )}
          </div>
          <EgfrTrendChart
            points={trajectoryPoints}
            slope={e3?.lmm_annual_slope ?? e3?.historical_egfr_slope}
          />
          {e3?.trajectory_backtest?.evaluated && (
            <div style={{ marginTop: '0.65rem', fontSize: '0.78rem', color: 'var(--muted)' }} className="tabular">
              Walk-forward trajectory check: MAE {Number(e3.trajectory_backtest.mae).toFixed(2)} mL/min · RMSE{' '}
              {Number(e3.trajectory_backtest.rmse).toFixed(2)} mL/min
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Stage-Specific Clinical Guidance</h2>
              <p className="panel-desc">
                Triage Protocol: <strong>{formatRuleName(arb.safety_rule_applied)}</strong>
              </p>
            </div>
          </div>

          <ul style={{ margin: 0, paddingLeft: '1.15rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {careGuidance.map((note, idx) => (
              <li key={idx} style={{ marginBottom: '0.5rem' }}>{note}</li>
            ))}
          </ul>

          {Array.isArray(arb.trigger_reasons) && arb.trigger_reasons.length > 0 && (
            <div style={{ marginTop: '0.9rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)' }}>
              <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                Clinical Findings Flagged
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                {arb.trigger_reasons.map((r, i) => (
                  <span key={i} className="badge badge-neutral badge-wrap">
                    {String(r).replace(/C:\s*UNAVAILABLE_CROSS_SECTIONAL\s*\|\s*/gi, '')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {sha && (
            <div style={{ marginTop: '0.9rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)', fontSize: '0.77rem', color: 'var(--muted)' }}>
              <FileText size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              Signed record digest: <code>{sha.slice(0, 14)}…</code>
            </div>
          )}
        </div>
      </div>

      {/* Biomarker Drivers + What-If Counterfactual Target Planner */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Key Risk Drivers &amp; Target Lab Goals</h2>
            <p className="panel-desc">
              Biomarker contributions and achievable laboratory targets (age, sex, and history kept fixed).
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
            <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <Sliders size={13} /> Target max risk:
              <strong className="tabular">{(targetRisk * 100).toFixed(0)}%</strong>
              <input
                type="range"
                min="0.15"
                max="0.50"
                step="0.05"
                value={targetRisk}
                onChange={(e) => setTargetRisk(Number(e.target.value))}
                style={{ width: 90 }}
              />
            </label>
            <select
              className="input-inline"
              style={{ width: 'auto', minWidth: 136, padding: '0.32rem 0.55rem', fontSize: '0.79rem', whiteSpace: 'nowrap' }}
              value={maxChanges}
              onChange={(e) => setMaxChanges(Number(e.target.value))}
            >
              {[1, 2, 3, 4].map((n) => (
                <option key={n} value={n}>Max {n} change{n > 1 ? 's' : ''}</option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-sm"
              disabled={explainLoading}
              onClick={() => runExplain(targetRisk, maxChanges)}
            >
              <RefreshCw size={13} /> {explainLoading ? 'Computing...' : 'Recalculate'}
            </button>
          </div>
        </div>

        {explainError && <div className="notice notice-warn">{explainError}</div>}

        <div className="grid-2">
          {/* Left: Top Shapley Attributions */}
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Primary Biomarker Drivers
            </div>
            {drivers.length === 0 ? (
              <div style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
                {explainLoading ? 'Computing attributions...' : 'No biomarker drivers available.'}
              </div>
            ) : (
              drivers.slice(0, 7).map((d) => {
                const val = Number(d.shap_value || 0)
                const pct = Math.min(100, (Math.abs(val) / maxAbsShap) * 100)
                const isRisk = val >= 0
                return (
                  <div className="attr-row" key={d.feature}>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={d.label}>
                      <span style={{ fontWeight: 500, color: 'var(--text)' }}>{d.label}</span>{' '}
                      <span style={{ color: 'var(--muted)', fontSize: '0.75rem' }} className="tabular">
                        ({d.clinical_value ?? '—'})
                      </span>
                    </div>
                    <div className="attr-track">
                      <div
                        style={{
                          width: `${pct.toFixed(1)}%`,
                          height: '100%',
                          background: isRisk ? '#dc2626' : '#0f766e',
                          borderRadius: '999px',
                        }}
                      />
                    </div>
                    <div
                      className="tabular"
                      style={{
                        textAlign: 'right',
                        fontWeight: 600,
                        color: isRisk ? 'var(--danger-fg)' : 'var(--ok-fg)',
                      }}
                    >
                      {val >= 0 ? `+${val.toFixed(3)}` : val.toFixed(3)}
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Right: Constrained Counterfactual Target Table */}
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Modifiable Target Lab Goals
            </div>
            {!cf ? (
              <div style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
                {explainLoading ? 'Searching feasible clinical recourse...' : 'Counterfactual guidance unavailable.'}
              </div>
            ) : (
              <>
                <div style={{ fontSize: '0.81rem', color: 'var(--text-secondary)', marginBottom: '0.55rem' }}>
                  {cf.notes ? String(cf.notes).replace(/`/g, '') : (cf.target_achieved ? 'Target risk achievable with modifiable biomarkers:' : 'Closest feasible reduction found:')}
                  {cf.initial_probability != null && cf.target_probability != null && (
                    <span className="tabular" style={{ marginLeft: 6, fontWeight: 600, color: 'var(--accent)' }}>
                      {(cf.initial_probability * 100).toFixed(1)}% → {(cf.target_probability * 100).toFixed(1)}%
                    </span>
                  )}
                </div>

                {(cf.suggested_shifts || []).length > 0 ? (
                  <div className="table-wrap">
                    <table className="clean-table">
                      <thead>
                        <tr>
                          <th>Biomarker</th>
                          <th>Current</th>
                          <th>Target</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cf.suggested_shifts.map((s) => (
                          <tr key={s.feature}>
                            <td style={{ fontWeight: 500, color: 'var(--text)' }}>{s.label || s.feature}</td>
                            <td className="tabular">{s.current_value}</td>
                            <td className="tabular" style={{ fontWeight: 600, color: 'var(--accent)' }}>
                              {s.target_value}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="notice" style={{ marginBottom: 0 }}>
                    No biomarker adjustments needed — patient is already below the {(targetRisk * 100).toFixed(0)}% risk target.
                  </div>
                )}

                {Array.isArray(cf.locked_immutable_features) && cf.locked_immutable_features.length > 0 && (
                  <div style={{ marginTop: '0.45rem', fontSize: '0.74rem', color: 'var(--muted)' }}>
                    Locked clinical history: {cf.locked_immutable_features.join(', ')}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Visit History + Add Follow-up Visit */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Recorded Lab Visits</h2>
            <p className="panel-desc">Append a visit below to recalculate eGFR slope and re-evaluate chronicity.</p>
          </div>
        </div>

        {visitError && <div className="notice notice-danger">{visitError}</div>}

        <div className="table-wrap" style={{ marginBottom: '0.9rem' }}>
          <table className="clean-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Serum Creatinine</th>
                <th>Estimated eGFR</th>
                <th>uACR</th>
                <th>Systolic BP</th>
                <th>Record Type</th>
              </tr>
            </thead>
            <tbody>
              {trajectoryPoints.map((pt, idx) => (
                <tr key={`${pt.date}-${idx}`}>
                  <td className="tabular">{String(pt.date).slice(0, 10)}</td>
                  <td className="tabular">{pt.scr != null ? `${Number(pt.scr).toFixed(2)} mg/dL` : '—'}</td>
                  <td className="tabular" style={{ fontWeight: 600 }}>{pt.egfr.toFixed(1)} mL/min</td>
                  <td className="tabular">{pt.uacr != null ? `${Number(pt.uacr).toFixed(1)} mg/g` : '—'}</td>
                  <td className="tabular">{pt.sbp != null ? `${Number(pt.sbp).toFixed(0)} mmHg` : '—'}</td>
                  <td>
                    <span className={`badge ${pt.isCurrent ? 'badge-teal' : 'badge-neutral'}`}>
                      {pt.isCurrent ? 'Current Intake' : 'Historical Visit'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <form onSubmit={handleAddVisitAndRerun} className="grid-4" style={{ alignItems: 'end' }}>
          <div className="field">
            <label>Visit date</label>
            <input
              type="date"
              value={newVisit.date}
              onChange={(e) => setNewVisit((v) => ({ ...v, date: e.target.value }))}
            />
          </div>
          <div className="field">
            <label>Creatinine <span className="field-hint">mg/dL</span></label>
            <input
              type="number"
              step="0.01"
              placeholder="e.g. 1.35"
              value={newVisit.scr}
              onChange={(e) => setNewVisit((v) => ({ ...v, scr: e.target.value }))}
            />
          </div>
          <div className="field">
            <label>uACR <span className="field-hint">mg/g</span></label>
            <input
              type="number"
              step="1"
              placeholder="e.g. 45"
              value={newVisit.uacr}
              onChange={(e) => setNewVisit((v) => ({ ...v, uacr: e.target.value }))}
            />
          </div>
          <div style={{ display: 'flex', gap: '0.45rem' }}>
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={savingVisit}>
              <Plus size={14} /> {savingVisit ? 'Updating...' : 'Add visit & re-run'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
