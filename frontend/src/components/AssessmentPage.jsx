import React, { useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Download,
  Play,
  Plus,
  RotateCcw,
  Trash2,
} from 'lucide-react'
import { api } from '../api'
import {
  BIOMARKER_META,
  formatCgaStage,
  formatChronicityLabel,
  formatCoherenceStatus,
  formatRuleName,
  formatTriageTier,
  getTierBadgeClass,
} from '../clinicalMeta'

function toNullableNum(v) {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const LAB_BAR_KEYS = ['sc', 'hemo', 'pcv', 'rc', 'sg', 'bu', 'bgr', 'al']

function LabRangeBar({ biomarkerKey, value, reconciledValue }) {
  const meta = BIOMARKER_META[biomarkerKey]
  if (!meta) return null

  const displayVal = reconciledValue != null ? Number(reconciledValue) : toNullableNum(value)
  if (displayVal == null) {
    return (
      <div className="range-row">
        <div className="range-head">
          <span style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>{meta.label}</span>
          <span className="badge badge-neutral">Not entered</span>
        </div>
      </div>
    )
  }

  const { scaleMin, scaleMax, normalLow, normalHigh, unit } = meta
  const span = Math.max(0.0001, scaleMax - scaleMin)
  const clampPct = (v) => Math.max(0, Math.min(100, ((v - scaleMin) / span) * 100))

  const normStart = clampPct(normalLow)
  const normEnd = clampPct(normalHigh)
  const normWidth = Math.max(3, normEnd - normStart)
  const markerPct = clampPct(displayVal)
  const inRange = displayVal >= normalLow && displayVal <= normalHigh

  return (
    <div className="range-row">
      <div className="range-head">
        <span style={{ fontWeight: 500, color: 'var(--text)' }}>{meta.label}</span>
        <span className="tabular" style={{ fontSize: '0.8rem' }}>
          <strong style={{ color: inRange ? 'var(--ok-fg)' : 'var(--danger-fg)' }}>
            {biomarkerKey === 'sg' ? displayVal.toFixed(3) : displayVal}
          </strong>{' '}
          <span style={{ color: 'var(--muted)' }}>
            {unit} (ref {normalLow === normalHigh ? `${normalLow}` : `${normalLow}–${normalHigh}`})
          </span>
        </span>
      </div>
      <div className="range-track">
        <div
          className="range-normal-band"
          style={{ left: `${normStart.toFixed(1)}%`, width: `${normWidth.toFixed(1)}%` }}
        />
        <div
          className="range-marker"
          style={{
            left: `${markerPct.toFixed(1)}%`,
            background: inRange ? '#047857' : '#dc2626',
          }}
        />
      </div>
    </div>
  )
}

const KDIGO_ROWS = [
  { g: 'G1', label: 'G1 ≥90', tiers: ['low', 'mod', 'high'] },
  { g: 'G2', label: 'G2 60–89', tiers: ['low', 'mod', 'high'] },
  { g: 'G3a', label: 'G3a 45–59', tiers: ['mod', 'high', 'vhigh'] },
  { g: 'G3b', label: 'G3b 30–44', tiers: ['high', 'vhigh', 'vhigh'] },
  { g: 'G4', label: 'G4 15–29', tiers: ['vhigh', 'vhigh', 'vhigh'] },
  { g: 'G5', label: 'G5 <15', tiers: ['vhigh', 'vhigh', 'vhigh'] },
]
const ALB_COLS = ['A1', 'A2', 'A3']

function KdigoCompactGrid({ gCat, aCat }) {
  const normG = String(gCat || '').toLowerCase()
  const normA = String(aCat || '').toUpperCase()
  return (
    <div className="kdigo-matrix" aria-label="KDIGO CGA risk matrix">
      <div className="kdigo-hdr">eGFR \ ACR</div>
      <div className="kdigo-hdr">A1 (&lt;30)</div>
      <div className="kdigo-hdr">A2 (30–300)</div>
      <div className="kdigo-hdr">A3 (&gt;300)</div>
      {KDIGO_ROWS.map((row) => (
        <React.Fragment key={row.g}>
          <div className="kdigo-hdr" style={{ textAlign: 'left', paddingLeft: '0.4rem' }}>
            {row.label}
          </div>
          {ALB_COLS.map((col, idx) => {
            const isActive = normG === row.g.toLowerCase() && normA === col
            const tierCls = `kdigo-${row.tiers[idx]}`
            return (
              <div
                key={`${row.g}-${col}`}
                className={`kdigo-cell ${tierCls} ${isActive ? 'active-cell' : ''}`}
              >
                {row.g}·{col}
              </div>
            )
          })}
        </React.Fragment>
      ))}
    </div>
  )
}

export default function AssessmentPage({
  formState,
  setFormState,
  assessment,
  setAssessment,
  user,
  onOpenChart,
  onVaultUpdated,
}) {
  const [showVisits, setShowVisits] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [saveNotice, setSaveNotice] = useState('')
  const [downloadingFmt, setDownloadingFmt] = useState('')

  function updateField(field, value) {
    setFormState((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'serum_creatinine') {
        next.biomarkers = { ...(prev.biomarkers || {}), sc: value }
      }
      return next
    })
  }

  function updateBiomarker(key, value) {
    setFormState((prev) => ({
      ...prev,
      biomarkers: { ...(prev.biomarkers || {}), [key]: value },
    }))
  }

  function clearForm() {
    setError('')
    setSaveNotice('')
    setAssessment(null)
    setFormState((prev) => ({
      ...prev,
      patient_id: '',
      age: '',
      serum_creatinine: '',
      uacr: '',
      biomarkers: {
        hemo: '',
        sg: '',
        pcv: '',
        rc: '',
        al: '',
        sc: '',
        bu: '',
        bgr: '',
        htn: 'no',
        dm: 'no',
      },
      visits: [],
    }))
  }

  function addVisitRow() {
    setFormState((prev) => ({
      ...prev,
      visits: [
        ...(prev.visits || []),
        { date: '', scr: '', uacr: '', sbp: '' },
      ],
    }))
  }

  function updateVisitRow(idx, key, val) {
    setFormState((prev) => ({
      ...prev,
      visits: (prev.visits || []).map((v, i) => (i === idx ? { ...v, [key]: val } : v)),
    }))
  }

  function removeVisitRow(idx) {
    setFormState((prev) => ({
      ...prev,
      visits: (prev.visits || []).filter((_, i) => i !== idx),
    }))
  }

  async function handleRunAssessment(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSaveNotice('')

    try {
      const b = formState.biomarkers || {}
      const cleanBiomarkers = {
        hemo: toNullableNum(b.hemo),
        sg: toNullableNum(b.sg),
        pcv: toNullableNum(b.pcv),
        rc: toNullableNum(b.rc),
        al: toNullableNum(b.al),
        sc: toNullableNum(formState.serum_creatinine),
        bu: toNullableNum(b.bu),
        bgr: toNullableNum(b.bgr),
        htn: b.htn || 'no',
        dm: b.dm || 'no',
      }

      const cleanVisits = (formState.visits || [])
        .map((v) => ({
          date: v.date,
          scr: toNullableNum(v.scr),
          uacr: toNullableNum(v.uacr) ?? 15.0,
          sbp: toNullableNum(v.sbp) ?? 120.0,
        }))
        .filter((v) => v.date && v.scr != null && v.scr > 0)

      const payload = {
        patient_id: (formState.patient_id || '').trim() || 'PT-UNASSIGNED',
        age: Number(formState.age),
        sex: formState.sex || 'male',
        observation_date: formState.observation_date || new Date().toISOString().slice(0, 10),
        biomarkers: cleanBiomarkers,
        serum_creatinine: toNullableNum(formState.serum_creatinine),
        serum_creatinine_unit: formState.serum_creatinine_unit || 'mg/dL',
        uacr: toNullableNum(formState.uacr),
        uacr_unit: formState.uacr_unit || 'mg/g',
        visits: cleanVisits,
        save_to_vault: Boolean(user),
      }

      const res = await api.assess(payload)
      setAssessment(res.assessment)
      if (res.saved_to_vault) {
        setSaveNotice('Assessment recorded in patient registry.')
        if (onVaultUpdated) onVaultUpdated()
      } else if (!user) {
        setSaveNotice('Evaluation ready. Sign in to save this encounter to the patient registry.')
      }
    } catch (err) {
      setError(err.message || 'Clinical assessment could not be completed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDownloadReport(fmt) {
    if (!assessment) return
    setDownloadingFmt(fmt)
    try {
      await api.downloadReport(fmt, assessment, formState.visits || [])
    } catch (err) {
      setError(err.message || `Unable to export ${fmt.toUpperCase()} report.`)
    } finally {
      setDownloadingFmt('')
    }
  }

  const e1 = assessment?.engine1_result || {}
  const e2 = assessment?.engine2_result || {}
  const e3 = assessment?.engine3_result || {}
  const arb = assessment?.overall_completeness?.arbitration_detail || {}
  const discrepancies = assessment?.clinical_discrepancies || []
  const unitAudit = e1.unit_reconciliation_audit || {}
  const reconciledSc = unitAudit?.sc?.converted_value ?? unitAudit?.sc?.reconciled_value
  const arbCls = getTierBadgeClass(arb.tier)
  const noticeCls =
    arbCls === 'badge-danger'
      ? 'notice-danger'
      : arbCls === 'badge-warn'
        ? 'notice-warn'
        : 'notice-ok'

  const stageLabel = formatCgaStage(e2.gfr_category, e2.albuminuria_category, e2.cga_string)
  const chronicityText = formatChronicityLabel(e2.cga_string)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">New Screening</h1>
          <p className="page-subtitle">
            Laboratory requisition &amp; clinical intake for CKD risk stratification and KDIGO staging.
          </p>
        </div>
      </div>

      <div className="intake-split">
        {/* Left Clinical Lab Requisition Form */}
        <form className="panel" onSubmit={handleRunAssessment}>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Patient &amp; Laboratory Requisition</h2>
              <p className="panel-desc">
                Leave unmeasured tests blank; incomplete panels are flagged automatically without filling healthy defaults.
              </p>
            </div>
          </div>

          {error && <div className="notice notice-danger">{error}</div>}
          {saveNotice && <div className="notice">{saveNotice}</div>}

          <div className="section-label" style={{ marginTop: 0 }}>Patient Demographics</div>
          <div className="grid-4">
            <div className="field">
              <label>Patient ID / MRN</label>
              <input
                type="text"
                value={formState.patient_id}
                onChange={(e) => updateField('patient_id', e.target.value)}
                placeholder="e.g. MRN-20418"
                required
              />
            </div>
            <div className="field">
              <label>Age <span className="field-hint">yrs</span></label>
              <input
                type="number"
                min="1"
                max="120"
                placeholder="e.g. 54"
                value={formState.age}
                onChange={(e) => updateField('age', e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label>Sex</label>
              <select value={formState.sex} onChange={(e) => updateField('sex', e.target.value)}>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
            <div className="field">
              <label>Visit Date</label>
              <input
                type="date"
                value={formState.observation_date}
                onChange={(e) => updateField('observation_date', e.target.value)}
              />
            </div>
          </div>

          <div className="section-label">Kidney Function &amp; Urinalysis</div>
          <div className="grid-2">
            <div className="field">
              <label>Serum Creatinine</label>
              <div className="input-group">
                <input
                  type="number"
                  step="0.01"
                  placeholder="e.g. 1.20"
                  value={formState.serum_creatinine}
                  onChange={(e) => updateField('serum_creatinine', e.target.value)}
                />
                <select
                  className="input-unit"
                  value={formState.serum_creatinine_unit}
                  onChange={(e) => updateField('serum_creatinine_unit', e.target.value)}
                >
                  <option value="mg/dL">mg/dL</option>
                  <option value="umol/L">µmol/L</option>
                </select>
              </div>
            </div>

            <div className="field">
              <label>Urine Albumin-Creatinine Ratio (uACR)</label>
              <div className="input-group">
                <input
                  type="number"
                  step="0.1"
                  placeholder="e.g. 24.0"
                  value={formState.uacr}
                  onChange={(e) => updateField('uacr', e.target.value)}
                />
                <select
                  className="input-unit"
                  value={formState.uacr_unit}
                  onChange={(e) => updateField('uacr_unit', e.target.value)}
                >
                  <option value="mg/g">mg/g</option>
                  <option value="mg/mmol">mg/mmol</option>
                </select>
              </div>
            </div>
          </div>

          <div className="grid-2" style={{ marginTop: '0.75rem' }}>
            <div className="field">
              <label>Urine Dipstick Albumin <span className="field-hint">Grade 0–5</span></label>
              <input
                type="number"
                min="0"
                max="5"
                step="1"
                placeholder="0 – 5"
                value={formState.biomarkers.al}
                onChange={(e) => updateBiomarker('al', e.target.value)}
              />
            </div>
            <div className="field">
              <label>Urine Specific Gravity</label>
              <input
                type="number"
                step="0.005"
                min="1.000"
                max="1.035"
                placeholder="e.g. 1.020"
                value={formState.biomarkers.sg}
                onChange={(e) => updateBiomarker('sg', e.target.value)}
              />
            </div>
          </div>

          <div className="section-label">Metabolic &amp; Hematology (CBC)</div>
          <div className="grid-3">
            <div className="field">
              <label>Blood Urea <span className="field-hint">mg/dL</span></label>
              <input
                type="number"
                step="0.5"
                placeholder="e.g. 32"
                value={formState.biomarkers.bu}
                onChange={(e) => updateBiomarker('bu', e.target.value)}
              />
            </div>
            <div className="field">
              <label>Random Blood Glucose <span className="field-hint">mg/dL</span></label>
              <input
                type="number"
                step="1"
                placeholder="e.g. 110"
                value={formState.biomarkers.bgr}
                onChange={(e) => updateBiomarker('bgr', e.target.value)}
              />
            </div>
            <div className="field">
              <label>Hemoglobin <span className="field-hint">g/dL</span></label>
              <input
                type="number"
                step="0.1"
                placeholder="e.g. 13.5"
                value={formState.biomarkers.hemo}
                onChange={(e) => updateBiomarker('hemo', e.target.value)}
              />
            </div>
          </div>

          <div className="grid-2" style={{ marginTop: '0.75rem' }}>
            <div className="field">
              <label>Hematocrit / Packed Cell Volume <span className="field-hint">%</span></label>
              <input
                type="number"
                step="0.5"
                placeholder="e.g. 41"
                value={formState.biomarkers.pcv}
                onChange={(e) => updateBiomarker('pcv', e.target.value)}
              />
            </div>
            <div className="field">
              <label>Red Blood Cell Count <span className="field-hint">M/mcL</span></label>
              <input
                type="number"
                step="0.1"
                placeholder="e.g. 4.8"
                value={formState.biomarkers.rc}
                onChange={(e) => updateBiomarker('rc', e.target.value)}
              />
            </div>
          </div>

          <div className="section-label">Medical History</div>
          <div className="grid-2">
            <div className="field">
              <label>Hypertension</label>
              <select
                value={formState.biomarkers.htn}
                onChange={(e) => updateBiomarker('htn', e.target.value)}
              >
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </div>
            <div className="field">
              <label>Diabetes Mellitus</label>
              <select
                value={formState.biomarkers.dm}
                onChange={(e) => updateBiomarker('dm', e.target.value)}
              >
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </div>
          </div>

          {/* Collapsible Historical Lab Visits */}
          <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowVisits((s) => !s)}
              >
                {showVisits ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                Prior Lab Visits ({(formState.visits || []).length})
              </button>
              {showVisits && (
                <button type="button" className="btn btn-sm" onClick={addVisitRow}>
                  <Plus size={13} /> Add prior visit
                </button>
              )}
            </div>

            {showVisits && (
              <div style={{ marginTop: '0.65rem', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                {(formState.visits || []).length === 0 ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                    Add prior serum creatinine visits to calculate annualized eGFR slope and verify chronicity (&ge;90 days).
                  </div>
                ) : (
                  formState.visits.map((v, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1.2fr 0.9fr 0.8fr 0.8fr auto',
                        gap: '0.4rem',
                        alignItems: 'center',
                      }}
                    >
                      <input
                        className="input-inline"
                        type="date"
                        value={v.date}
                        onChange={(e) => updateVisitRow(idx, 'date', e.target.value)}
                      />
                      <input
                        className="input-inline"
                        type="number"
                        step="0.01"
                        placeholder="SCr mg/dL"
                        value={v.scr}
                        onChange={(e) => updateVisitRow(idx, 'scr', e.target.value)}
                      />
                      <input
                        className="input-inline"
                        type="number"
                        step="1"
                        placeholder="uACR mg/g"
                        value={v.uacr}
                        onChange={(e) => updateVisitRow(idx, 'uacr', e.target.value)}
                      />
                      <input
                        className="input-inline"
                        type="number"
                        step="1"
                        placeholder="SBP mmHg"
                        value={v.sbp}
                        onChange={(e) => updateVisitRow(idx, 'sbp', e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => removeVisitRow(idx)}
                        aria-label="Remove visit"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.55rem', marginTop: '1.15rem', paddingTop: '0.9rem', borderTop: '1px solid var(--border)' }}>
            <button type="submit" className="btn btn-primary" disabled={submitting} style={{ flex: 1 }}>
              <Play size={14} /> {submitting ? 'Evaluating Panel…' : 'Run Clinical Assessment'}
            </button>
            <button type="button" className="btn" onClick={clearForm}>
              <RotateCcw size={14} /> Reset form
            </button>
          </div>
        </form>

        {/* Right Sticky Clinical Summary Column */}
        <div className="sticky-col">
          {!assessment ? (
            <div className="panel">
              <h2 className="panel-title">Clinical Summary</h2>
              <p className="panel-desc" style={{ marginTop: '0.35rem' }}>
                Complete the requisition form to generate:
              </p>
              <ul style={{ margin: '0.75rem 0 0', paddingLeft: '1.15rem', fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                <li style={{ marginBottom: '0.35rem' }}>Triage recommendation and clinical safety alerts</li>
                <li style={{ marginBottom: '0.35rem' }}>Laboratory reference range bars with SI/US unit conversion</li>
                <li style={{ marginBottom: '0.35rem' }}>CKD-EPI 2021 eGFR and KDIGO staging heatmap</li>
                <li>2-year and 5-year kidney failure risk prognosis (KFRE)</li>
              </ul>
            </div>
          ) : (
            <div>
              {/* Triage Callout */}
              <div className={`notice ${noticeCls}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: '0.94rem' }}>{formatTriageTier(arb.tier)}</strong>
                  <span className="badge badge-neutral">{formatRuleName(arb.safety_rule_applied)}</span>
                </div>
                <div style={{ marginTop: '0.35rem', fontSize: '0.82rem' }}>
                  {arb.recommended_action || 'Clinical screening completed.'}
                </div>
              </div>

              {/* Key Metrics Card */}
              <div className="panel panel-tight">
                <div className="grid-3" style={{ gap: '0.65rem' }}>
                  <div>
                    <div className="metric-label">CKD Screening Risk</div>
                    <div className="metric-val tabular" style={{ fontSize: '1.25rem' }}>
                      {e1.risk_probability != null ? `${(e1.risk_probability * 100).toFixed(1)}%` : 'Held'}
                    </div>
                    <div className="metric-sub">{e1.risk_category || formatTriageTier(e1.conformal_gate_decision)}</div>
                  </div>
                  <div>
                    <div className="metric-label">eGFR · KDIGO</div>
                    <div className="metric-val tabular" style={{ fontSize: '1.25rem' }}>
                      {e2.egfr != null ? Number(e2.egfr).toFixed(1) : '—'}
                    </div>
                    <div className="metric-sub">{stageLabel}</div>
                  </div>
                  <div>
                    <div className="metric-label">5-Year KFRE</div>
                    <div className="metric-val tabular" style={{ fontSize: '1.25rem' }}>
                      {e3.kfre_5year_risk != null ? `${(e3.kfre_5year_risk * 100).toFixed(1)}%` : 'N/A'}
                    </div>
                    <div className="metric-sub">
                      {e3.kfre_2year_risk != null ? `2-yr ${(e3.kfre_2year_risk * 100).toFixed(1)}%` : 'Stages G3–G5'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.8rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)' }}>
                  <span className="badge badge-neutral tabular">
                    Panel Quality {e1.clinical_reliability_index != null ? `${Math.round(Number(e1.clinical_reliability_index) * 100)}%` : '—'}
                  </span>
                  <span className="badge badge-neutral">{chronicityText}</span>
                  <span
                    className={`badge ${
                      e1.coherence_audit?.coherence_status === 'COHERENT' ? 'badge-ok' : 'badge-warn'
                    }`}
                  >
                    {formatCoherenceStatus(e1.coherence_audit?.coherence_status)}
                  </span>
                  {e1.has_architecture_disagreement && (
                    <span className="badge badge-warn">Borderline Model Variance</span>
                  )}
                  {reconciledSc != null && (
                    <span className="badge badge-teal tabular">Converted SC: {reconciledSc} mg/dL</span>
                  )}
                </div>
              </div>

              {/* Biomarker Reference Bars */}
              <div className="panel panel-tight">
                <div className="panel-header" style={{ marginBottom: '0.4rem' }}>
                  <h3 className="panel-title" style={{ fontSize: '0.88rem' }}>Lab Reference Ranges</h3>
                </div>
                {LAB_BAR_KEYS.map((k) => (
                  <LabRangeBar
                    key={k}
                    biomarkerKey={k}
                    value={k === 'sc' ? formState.serum_creatinine : formState.biomarkers?.[k]}
                    reconciledValue={k === 'sc' ? reconciledSc : null}
                  />
                ))}
              </div>

              {/* Compact KDIGO Matrix */}
              <div className="panel panel-tight">
                <div className="panel-header" style={{ marginBottom: '0.55rem' }}>
                  <h3 className="panel-title" style={{ fontSize: '0.88rem' }}>KDIGO Staging Grid</h3>
                  <span className="badge badge-neutral">{stageLabel}</span>
                </div>
                <KdigoCompactGrid gCat={e2.gfr_category} aCat={e2.albuminuria_category} />
              </div>

              {/* Discrepancy & Coherence Alerts */}
              {(discrepancies.length > 0 || (e1.coherence_audit?.contradictions || []).length > 0) && (
                <div className="notice notice-warn">
                  <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
                    <AlertTriangle size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                    Clinical Verification Notes ({discrepancies.length + (e1.coherence_audit?.contradictions || []).length})
                  </div>
                  {discrepancies.map((d) => (
                    <div key={d.discrepancy_id} style={{ fontSize: '0.79rem', marginTop: '0.25rem' }}>
                      <strong>{d.title}:</strong> {d.clinical_action || d.description}
                    </div>
                  ))}
                  {(e1.coherence_audit?.contradictions || []).map((c, idx) => (
                    <div key={idx} style={{ fontSize: '0.79rem', marginTop: '0.25rem' }}>
                      <strong>Lab Coherence:</strong> {c.message}
                    </div>
                  ))}
                </div>
              )}

              {/* Chart & Export Actions */}
              <div className="panel panel-tight" style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => onOpenChart && onOpenChart(assessment)}
                >
                  Open patient chart &amp; follow-up plan <ArrowRight size={14} />
                </button>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.4rem' }}>
                  {['pdf', 'csv', 'json', 'txt'].map((fmt) => (
                    <button
                      key={fmt}
                      type="button"
                      className="btn btn-sm"
                      disabled={downloadingFmt === fmt}
                      onClick={() => handleDownloadReport(fmt)}
                    >
                      <Download size={12} /> {fmt.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
