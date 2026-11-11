import React, { useState } from 'react'
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Plus,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Trash2,
  Upload,
} from 'lucide-react'
import { api } from '../api'

const KDIGO_ROWS = [
  { g: 'G1', label: 'G1 (>=90)', cls: ['kdigo-low', 'kdigo-mod', 'kdigo-high'] },
  { g: 'G2', label: 'G2 (60-89)', cls: ['kdigo-low', 'kdigo-mod', 'kdigo-high'] },
  { g: 'G3a', label: 'G3a (45-59)', cls: ['kdigo-mod', 'kdigo-high', 'kdigo-vhigh'] },
  { g: 'G3b', label: 'G3b (30-44)', cls: ['kdigo-high', 'kdigo-vhigh', 'kdigo-vhigh'] },
  { g: 'G4', label: 'G4 (15-29)', cls: ['kdigo-vhigh', 'kdigo-vhigh', 'kdigo-vhigh'] },
  { g: 'G5', label: 'G5 (<15)', cls: ['kdigo-vhigh', 'kdigo-vhigh', 'kdigo-vhigh'] },
]

const KDIGO_RISK_TXT = {
  'kdigo-low': 'Low Risk',
  'kdigo-mod': 'Moderate',
  'kdigo-high': 'High Risk',
  'kdigo-vhigh': 'Very High',
}

function tierAlertClass(tier) {
  const t = String(tier || '').toLowerCase()
  if (
    t.includes('immediate') ||
    t.includes('critical') ||
    t.includes('escalation') ||
    t.includes('high') ||
    t.includes('referral') ||
    t.includes('priority')
  ) {
    return 'alert-danger'
  }
  if (t.includes('confirm') || t.includes('abstain') || t.includes('review') || t.includes('monitor') || t.includes('moderate')) {
    return 'alert-warn'
  }
  return 'alert-ok'
}

export default function AssessmentPage({
  presets,
  formState,
  setFormState,
  assessment,
  setAssessment,
  user,
  onNavigate,
  onVaultUpdated,
}) {
  const [activeTab, setActiveTab] = useState('single')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [saveFeedback, setSaveFeedback] = useState('')
  const [exportingFmt, setExportingFmt] = useState('')

  // Batch CSV state
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchError, setBatchError] = useState('')
  const [batchResult, setBatchResult] = useState(null)

  function updateBio(key, val) {
    setFormState((prev) => ({
      ...prev,
      biomarkers: { ...prev.biomarkers, [key]: val },
      ...(key === 'sc' ? { serum_creatinine: val } : {}),
    }))
  }

  function applyPreset(presetKey) {
    const p = presets[presetKey]
    if (!p) return
    const todayIso = new Date().toISOString().slice(0, 10)
    setFormState({
      patient_id: p.patient_id,
      age: p.age,
      sex: p.sex,
      biomarkers: { ...p.biomarkers },
      serum_creatinine: p.serum_creatinine,
      serum_creatinine_unit: p.serum_creatinine_unit || 'mg/dL',
      uacr: p.uacr,
      uacr_unit: p.uacr_unit || 'mg/g',
      observation_date_scr: todayIso,
      observation_date_uacr: todayIso,
      kfre_calibration: 'NON_NORTH_AMERICA',
      visits: (p.visits || []).map((v) => ({ ...v })),
      auto_save: true,
    })
    setError('')
    setSaveFeedback('')
  }

  function addVisit() {
    const todayIso = new Date().toISOString().slice(0, 10)
    setFormState((prev) => ({
      ...prev,
      visits: [
        ...(prev.visits || []),
        {
          date: todayIso,
          scr: Number(prev.serum_creatinine || prev.biomarkers.sc || 1.0),
          uacr: Number(prev.uacr || 20.0),
          sbp: 125.0,
        },
      ],
    }))
  }

  function updateVisit(idx, key, val) {
    setFormState((prev) => ({
      ...prev,
      visits: prev.visits.map((v, i) => (i === idx ? { ...v, [key]: val } : v)),
    }))
  }

  function removeVisit(idx) {
    setFormState((prev) => ({
      ...prev,
      visits: prev.visits.filter((_, i) => i !== idx),
    }))
  }

  async function handleRunAssessment(e) {
    e.preventDefault()
    setError('')
    setSaveFeedback('')
    setLoading(true)
    try {
      const payload = {
        ...formState,
        age: Number(formState.age),
        serum_creatinine: formState.serum_creatinine !== '' && formState.serum_creatinine !== null
          ? Number(formState.serum_creatinine)
          : null,
        uacr: formState.uacr !== '' && formState.uacr !== null ? Number(formState.uacr) : null,
        biomarkers: {
          ...formState.biomarkers,
          hemo: formState.biomarkers.hemo === '' ? null : Number(formState.biomarkers.hemo),
          sg: formState.biomarkers.sg === '' ? null : Number(formState.biomarkers.sg),
          pcv: formState.biomarkers.pcv === '' ? null : Number(formState.biomarkers.pcv),
          rc: formState.biomarkers.rc === '' ? null : Number(formState.biomarkers.rc),
          al: formState.biomarkers.al === '' ? null : Number(formState.biomarkers.al),
          sc: formState.biomarkers.sc === '' ? null : Number(formState.biomarkers.sc),
          bu: formState.biomarkers.bu === '' ? null : Number(formState.biomarkers.bu),
          bgr: formState.biomarkers.bgr === '' ? null : Number(formState.biomarkers.bgr),
        },
        visits: (formState.visits || []).map((v) => ({
          date: v.date,
          scr: Number(v.scr),
          uacr: v.uacr !== '' && v.uacr !== null ? Number(v.uacr) : null,
          sbp: v.sbp !== '' && v.sbp !== null ? Number(v.sbp) : null,
        })),
      }
      const res = await api.assess(payload)
      setAssessment(res.assessment)
      if (res.saved_to_vault) {
        setSaveFeedback(
          `Saved to ${res.storage_backend === 'postgresql' ? 'Cloud PostgreSQL' : 'SQLite Vault'} (Row #${res.saved_row_id})`,
        )
        if (onVaultUpdated) onVaultUpdated()
      } else if (user && !formState.auto_save) {
        setSaveFeedback('Completed without saving (Auto-Save disabled).')
      }
    } catch (err) {
      setError(err.message || 'Assessment failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleExport(fmt) {
    if (!assessment) return
    setExportingFmt(fmt)
    try {
      await api.downloadReport(fmt, assessment, formState.visits || [])
    } catch (err) {
      setError(err.message || `Export (${fmt.toUpperCase()}) failed.`)
    } finally {
      setExportingFmt('')
    }
  }

  async function handleBatchFileChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setBatchError('')
    setBatchLoading(true)
    try {
      const res = await api.batchScreen(file)
      setBatchResult(res)
    } catch (err) {
      setBatchError(err.message || 'Batch screening failed.')
    } finally {
      setBatchLoading(false)
      e.target.value = ''
    }
  }

  async function handleDownloadSampleCsv() {
    try {
      const data = await api.sampleBatchCsv()
      const blob = new Blob([data.csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'nefroai_sample_batch_patients.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setBatchError(err.message || 'Could not download sample CSV.')
    }
  }

  function handleDownloadSanitizedBatch() {
    if (!batchResult?.sanitized_csv) return
    const blob = new Blob([batchResult.sanitized_csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'nefroai_batch_screened_results.csv'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const e1 = assessment?.engine1_result
  const e2 = assessment?.engine2_result
  const e3 = assessment?.engine3_result
  const arb = assessment?.overall_completeness?.arbitration_detail
  const coh = e1?.coherence_audit

  return (
    <div>
      <div className="tabs">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'single' ? 'active' : ''}`}
          onClick={() => setActiveTab('single')}
        >
          <Stethoscope size={15} style={{ verticalAlign: 'text-bottom', marginRight: '6px' }} />
          Single-Patient CKD Assessment
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'batch' ? 'active' : ''}`}
          onClick={() => setActiveTab('batch')}
        >
          <FileSpreadsheet size={15} style={{ verticalAlign: 'text-bottom', marginRight: '6px' }} />
          Batch CSV Screening &amp; Drift Monitor
        </button>
      </div>

      {activeTab === 'single' ? (
        <div>
          {/* Clinical Preset Strip */}
          <div className="card" style={{ padding: '0.9rem 1.15rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.6rem' }}>
              <div style={{ fontSize: '0.84rem', fontWeight: 700, color: '#0b1f3a' }}>
                Quick Clinical Test Presets:
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {Object.entries(presets || {}).map(([key, p]) => (
                  <button
                    key={key}
                    type="button"
                    className="btn btn-sm"
                    onClick={() => applyPreset(key)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <form onSubmit={handleRunAssessment}>
            {/* Demographics & Consensus 10 Lab Panel */}
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <div>
                  <h3 style={{ margin: 0 }}>1. Patient Profile &amp; 10 Consensus Lab Biomarkers</h3>
                  <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                    Works cleanly with standard US/India units or EU/UK SI units (MIDR auto-reconciles &mu;mol/L, g/L, mmol/L).
                  </div>
                </div>
                {user && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem', fontWeight: 600 }}>
                    <input
                      type="checkbox"
                      checked={Boolean(formState.auto_save)}
                      onChange={(e) => setFormState((prev) => ({ ...prev, auto_save: e.target.checked }))}
                    />
                    Auto-save to Cloud Vault
                  </label>
                )}
              </div>

              <div className="field-grid" style={{ marginBottom: '0.9rem' }}>
                <div className="field">
                  <label>Patient ID</label>
                  <input
                    type="text"
                    value={formState.patient_id}
                    onChange={(e) => setFormState((p) => ({ ...p, patient_id: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label>Age (Years)</label>
                  <input
                    type="number"
                    min="1"
                    max="120"
                    step="1"
                    value={formState.age}
                    onChange={(e) => setFormState((p) => ({ ...p, age: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label>Biological Sex (for CKD-EPI 2021)</label>
                  <select
                    value={formState.sex}
                    onChange={(e) => setFormState((p) => ({ ...p, sex: e.target.value }))}
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div className="field">
                  <label>KFRE Calibration Region</label>
                  <select
                    value={formState.kfre_calibration}
                    onChange={(e) => setFormState((p) => ({ ...p, kfre_calibration: e.target.value }))}
                  >
                    <option value="NON_NORTH_AMERICA">Non-North America</option>
                    <option value="NORTH_AMERICA">North America</option>
                  </select>
                </div>
              </div>

              <div className="field-grid">
                <div className="field">
                  <label>Hemoglobin (hemo, g/dL or g/L)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formState.biomarkers.hemo ?? ''}
                    onChange={(e) => updateBio('hemo', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Urine Specific Gravity (sg)</label>
                  <input
                    type="number"
                    step="0.005"
                    value={formState.biomarkers.sg ?? ''}
                    onChange={(e) => updateBio('sg', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Packed Cell Volume (pcv, %)</label>
                  <input
                    type="number"
                    step="1"
                    value={formState.biomarkers.pcv ?? ''}
                    onChange={(e) => updateBio('pcv', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Red Blood Cell Count (rc, M/mcL)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formState.biomarkers.rc ?? ''}
                    onChange={(e) => updateBio('rc', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Urine Albumin Dipstick (al, 0–5)</label>
                  <select
                    value={formState.biomarkers.al ?? 0}
                    onChange={(e) => updateBio('al', Number(e.target.value))}
                  >
                    {[0, 1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>Grade {n} {n === 0 ? '(Normal)' : '(Proteinuria)'}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Serum Creatinine (sc)</label>
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <input
                      type="number"
                      step="0.01"
                      value={formState.biomarkers.sc ?? ''}
                      onChange={(e) => updateBio('sc', e.target.value)}
                    />
                    <select
                      style={{ width: '95px', flexShrink: 0 }}
                      value={formState.serum_creatinine_unit}
                      onChange={(e) => setFormState((p) => ({ ...p, serum_creatinine_unit: e.target.value }))}
                    >
                      <option value="mg/dL">mg/dL</option>
                      <option value="µmol/L">&mu;mol/L</option>
                    </select>
                  </div>
                </div>
                <div className="field">
                  <label>Blood Urea (bu, mg/dL)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={formState.biomarkers.bu ?? ''}
                    onChange={(e) => updateBio('bu', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Blood Glucose Random (bgr, mg/dL)</label>
                  <input
                    type="number"
                    step="1"
                    value={formState.biomarkers.bgr ?? ''}
                    onChange={(e) => updateBio('bgr', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Hypertension (htn)</label>
                  <select
                    value={formState.biomarkers.htn ?? 'no'}
                    onChange={(e) => updateBio('htn', e.target.value)}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
                <div className="field">
                  <label>Diabetes Mellitus (dm)</label>
                  <select
                    value={formState.biomarkers.dm ?? 'no'}
                    onChange={(e) => updateBio('dm', e.target.value)}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
                <div className="field">
                  <label>Spot uACR (Engine 2 Quantitative)</label>
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <input
                      type="number"
                      step="0.1"
                      value={formState.uacr ?? ''}
                      onChange={(e) => setFormState((p) => ({ ...p, uacr: e.target.value }))}
                    />
                    <select
                      style={{ width: '98px', flexShrink: 0 }}
                      value={formState.uacr_unit}
                      onChange={(e) => setFormState((p) => ({ ...p, uacr_unit: e.target.value }))}
                    >
                      <option value="mg/g">mg/g</option>
                      <option value="mg/mmol">mg/mmol</option>
                    </select>
                  </div>
                </div>
                <div className="field">
                  <label>Lab Observation Date</label>
                  <input
                    type="date"
                    value={formState.observation_date_scr}
                    onChange={(e) =>
                      setFormState((p) => ({
                        ...p,
                        observation_date_scr: e.target.value,
                        observation_date_uacr: e.target.value,
                      }))
                    }
                  />
                </div>
              </div>
            </div>

            {/* Engine 3 Longitudinal Visits Editor */}
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.55rem' }}>
                <div>
                  <h3 style={{ margin: 0 }}>2. Longitudinal Visit History (Engine 3 KDIGO &gt;=90-Day Chronicity &amp; Slope)</h3>
                  <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                    Add 2+ prior lab visits spanning &gt;=90 days to calculate eGFR slope, AKI vs Chronic guard, and trajectory backtest.
                  </div>
                </div>
                <button type="button" className="btn btn-sm" onClick={addVisit}>
                  <Plus size={14} /> Add Visit
                </button>
              </div>

              {(formState.visits || []).length === 0 ? (
                <div style={{ fontSize: '0.83rem', color: 'var(--muted)', padding: '0.4rem 0' }}>
                  No longitudinal visits added yet. Engine 3 will still compute KFRE if uACR and eGFR are available, or click &ldquo;Add Visit&rdquo;.
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Visit Date</th>
                        <th>Serum Creatinine (mg/dL)</th>
                        <th>uACR (mg/g)</th>
                        <th>Systolic BP (mmHg)</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {formState.visits.map((v, idx) => (
                        <tr key={idx}>
                          <td>
                            <input
                              type="date"
                              value={v.date}
                              onChange={(e) => updateVisit(idx, 'date', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              value={v.scr}
                              onChange={(e) => updateVisit(idx, 'scr', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.1"
                              value={v.uacr ?? ''}
                              onChange={(e) => updateVisit(idx, 'uacr', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="1"
                              value={v.sbp ?? ''}
                              onChange={(e) => updateVisit(idx, 'sbp', e.target.value)}
                            />
                          </td>
                          <td>
                            <button
                              type="button"
                              className="btn btn-sm"
                              onClick={() => removeVisit(idx)}
                              aria-label="Remove visit row"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginTop: '1rem' }}>
                <div style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
                  {user
                    ? `Signed in as ${user.full_name} — evaluation saves automatically to Vault.`
                    : 'Not signed in — results still compute immediately; sign in to persist history online.'}
                </div>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  <Sparkles size={16} />
                  {loading ? 'Running 3-Engine Analysis...' : 'Run Multi-Engine CKD Screening'}
                </button>
              </div>
            </div>
          </form>

          {error && <div className="alert alert-danger">{error}</div>}
          {saveFeedback && (
            <div className="alert alert-ok" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle2 size={16} /> {saveFeedback}
            </div>
          )}

          {/* Live Results Panel */}
          {assessment && (
            <div>
              {/* Safety-Max Arbitration Banner */}
              {arb && (
                <div className={`alert ${tierAlertClass(arb.tier)}`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.35rem' }}>
                    <strong style={{ fontSize: '0.98rem' }}>
                      Safety-Max Arbitration Tier: {arb.tier}
                    </strong>
                    <span className="pill pill-blue">{arb.safety_rule_applied}</span>
                  </div>
                  <div style={{ marginBottom: '0.35rem' }}>
                    <strong>Recommended Clinical Action:</strong> {arb.recommended_action}
                  </div>
                  {(arb.trigger_reasons || []).length > 0 && (
                    <div style={{ fontSize: '0.82rem' }}>
                      Triggers: {arb.trigger_reasons.join(' • ')}
                    </div>
                  )}
                </div>
              )}

              {/* Engine 1 / 2 / 3 Output Grid */}
              <div className="grid-3">
                {/* Engine 1 */}
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <h3 style={{ margin: 0 }}>Engine 1: CKD ML Screening</h3>
                    <span className={`pill ${e1?.diagnostic_class === 1 ? 'pill-red' : 'pill-green'}`}>
                      {e1?.diagnostic_class === 1 ? 'CKD AT RISK' : e1?.diagnostic_class === 0 ? 'NO CKD DETECTED' : 'ABSTAIN'}
                    </span>
                  </div>
                  <div style={{ fontSize: '1.65rem', fontWeight: 800, color: e1?.diagnostic_class === 1 ? '#b91c1c' : '#047857' }}>
                    {e1?.risk_probability != null ? `${(e1.risk_probability * 100).toFixed(1)}%` : 'Abstained'}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: '0.7rem' }}>
                    Champion RF Probability &bull; Tier: <strong>{e1?.risk_category}</strong>
                  </div>

                  <div style={{ fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <div>
                      <strong>4-Family Stacking:</strong>{' '}
                      {e1?.stacking_probability != null ? `${(e1.stacking_probability * 100).toFixed(1)}%` : 'N/A'}
                      {e1?.has_architecture_disagreement && ' (Disagreement Flag)'}
                    </div>
                    <div>
                      <strong>CRI Quality Score:</strong>{' '}
                      {e1?.clinical_reliability_index != null ? `${(e1.clinical_reliability_index * 100).toFixed(0)}%` : 'N/A'}
                    </div>
                    <div className="bar-track" style={{ height: '10px' }}>
                      <div
                        className="bar-fill-blue"
                        style={{ width: `${Math.round((e1?.clinical_reliability_index || 0) * 100)}%` }}
                      />
                    </div>
                    <div>
                      <strong>Split Conformal Set (95%):</strong>{' '}
                      <code>{JSON.stringify(e1?.conformal_set)}</code> ({e1?.conformal_gate_decision})
                    </div>
                    <div>
                      <strong>Mondrian Set:</strong>{' '}
                      <code>{JSON.stringify(e1?.mondrian_conformal_set)}</code>
                    </div>
                    <div>
                      <strong>MIDR Unit Audits:</strong>{' '}
                      {Object.keys(e1?.unit_reconciliation_audit || {}).length > 0
                        ? Object.entries(e1.unit_reconciliation_audit)
                            .map(([k, v]) => `${k} (${v.original_value} -> ${v.reconciled_value})`)
                            .join('; ')
                        : 'Standard units'}
                    </div>
                    {coh && (
                      <div style={{ marginTop: '0.25rem', padding: '0.5rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border)' }}>
                        <strong>Cross-Analyte Coherence:</strong> {coh.coherence_status || 'PASS'}
                        {(coh.contradictions || []).length > 0 && (
                          <div style={{ color: '#b45309', fontSize: '0.78rem', marginTop: '0.2rem' }}>
                            {coh.contradictions.map((c) => `${c.rule_id}: ${c.message}`).join(' | ')}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Engine 2 + KDIGO Heatmap */}
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem' }}>
                    <h3 style={{ margin: 0 }}>Engine 2: KDIGO CGA Staging</h3>
                    <span className="pill pill-blue">
                      {e2?.gfr_category && e2?.albuminuria_category
                        ? `${e2.gfr_category}-${e2.albuminuria_category}`
                        : 'CGA'}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.4rem', wordBreak: 'break-word' }}>
                    {e2?.cga_string || 'N/A'}
                  </div>
                  <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#0f4c81' }}>
                    {e2?.egfr != null ? `${Number(e2.egfr).toFixed(1)}` : '—'}{' '}
                    <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>mL/min/1.73m&sup2;</span>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: '0.55rem' }}>
                    {e2?.gfr_description} &bull; uACR: {e2?.uacr != null ? `${Number(e2.uacr).toFixed(1)} mg/g (${e2.albuminuria_category})` : 'Not supplied'}
                  </div>

                  {/* Interactive 28-cell KDIGO Matrix */}
                  <div className="kdigo-grid" aria-label="KDIGO G1-G5 by A1-A3 Heatmap">
                    <div className="kdigo-hdr">GFR \ uACR</div>
                    <div className="kdigo-hdr">A1 (&lt;30)</div>
                    <div className="kdigo-hdr">A2 (30-300)</div>
                    <div className="kdigo-hdr">A3 (&gt;300)</div>
                    {KDIGO_ROWS.map((row) => (
                      <React.Fragment key={row.g}>
                        <div className="kdigo-hdr" style={{ background: '#1e3a5f' }}>{row.label}</div>
                        {['A1', 'A2', 'A3'].map((aCol, idx) => {
                          const isCurrent = e2?.gfr_category === row.g && e2?.albuminuria_category === aCol
                          const cls = row.cls[idx]
                          return (
                            <div
                              key={`${row.g}-${aCol}`}
                              className={`kdigo-cell ${cls} ${isCurrent ? 'active-cell' : ''}`}
                              title={`${row.g}-${aCol}: ${KDIGO_RISK_TXT[cls]}`}
                            >
                              {isCurrent ? 'PATIENT' : KDIGO_RISK_TXT[cls]}
                            </div>
                          )
                        })}
                      </React.Fragment>
                    ))}
                  </div>
                </div>

                {/* Engine 3 */}
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <h3 style={{ margin: 0 }}>Engine 3: Trajectory &amp; KFRE</h3>
                    <span className="pill pill-amber">SURVIVAL ML DEFERRED</span>
                  </div>

                  <div className="grid-2" style={{ gap: '0.5rem', marginBottom: '0.65rem' }}>
                    <div style={{ background: '#f8fafc', padding: '0.6rem', borderRadius: '9px', border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--muted)', fontWeight: 700 }}>2-YR KIDNEY FAILURE</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0b1f3a' }}>
                        {e3?.kfre_2year_risk != null ? `${(e3.kfre_2year_risk * 100).toFixed(2)}%` : 'Requires G3a+ & uACR'}
                      </div>
                    </div>
                    <div style={{ background: '#f8fafc', padding: '0.6rem', borderRadius: '9px', border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--muted)', fontWeight: 700 }}>5-YR KIDNEY FAILURE</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0b1f3a' }}>
                        {e3?.kfre_5year_risk != null ? `${(e3.kfre_5year_risk * 100).toFixed(2)}%` : 'Requires G3a+ & uACR'}
                      </div>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.32rem' }}>
                    <div>
                      <strong>OLS eGFR Slope:</strong>{' '}
                      {e3?.historical_egfr_slope != null
                        ? `${Number(e3.historical_egfr_slope).toFixed(2)} mL/min/yr (${e3.slope_status})`
                        : e3?.slope_status || 'Single-visit only'}
                    </div>
                    <div>
                      <strong>LMM BLUP Slope:</strong>{' '}
                      {e3?.lmm_annual_slope != null ? `${Number(e3.lmm_annual_slope).toFixed(2)} mL/min/yr` : 'N/A'}
                    </div>
                    {e3?.chronicity_aki_assessment && (
                      <div style={{ padding: '0.5rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border)' }}>
                        <strong>90-Day Chronicity / AKI Guard:</strong>{' '}
                        {e3.chronicity_aki_assessment.classification}
                        {e3.chronicity_aki_assessment.aki_velocity_alert && ' — ACUTE CREATININE VELOCITY SPIKE'}
                      </div>
                    )}
                    {e3?.trajectory_backtest?.evaluated && (
                      <div>
                        <strong>Walk-Forward Backtest:</strong> MAE {Number(e3.trajectory_backtest.mae).toFixed(2)}, RMSE{' '}
                        {Number(e3.trajectory_backtest.rmse).toFixed(2)}
                      </div>
                    )}
                    <div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
                      {e3?.kfre_applicability_explanation}
                    </div>
                  </div>
                </div>
              </div>

              {/* Clinical Discrepancies + Exports + Attestation */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.6rem', marginBottom: '0.7rem' }}>
                  <div>
                    <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <ShieldCheck size={18} color="#0f4c81" />
                      Cross-Engine Discrepancies, XAI &amp; Medical Reports
                    </h3>
                    <div style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                      SHA-256 Attestation Seal: <code>{assessment.provenance?.attestation_sha256 || 'N/A'}</code>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap' }}>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => onNavigate('explainability')}>
                      <BrainCircuit size={14} /> Open Live SHAP &amp; What-If Simulator
                    </button>
                    {['pdf', 'csv', 'json', 'txt'].map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        className="btn btn-sm"
                        disabled={exportingFmt === fmt}
                        onClick={() => handleExport(fmt)}
                      >
                        <Download size={14} /> {exportingFmt === fmt ? '...' : fmt.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                {(assessment.clinical_discrepancies || []).length === 0 ? (
                  <div className="alert alert-ok" style={{ marginBottom: 0 }}>
                    No cross-engine clinical discrepancies triggered (DISC-01 through DISC-10 clear).
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {assessment.clinical_discrepancies.map((d) => (
                      <div key={d.discrepancy_id} className="alert alert-warn" style={{ marginBottom: 0 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                          <strong>{d.discrepancy_id}: {d.title}</strong>
                          <span className="pill pill-red">{d.severity}</span>
                        </div>
                        <div style={{ fontSize: '0.84rem', marginTop: '0.25rem' }}>{d.description}</div>
                        <div style={{ fontSize: '0.82rem', marginTop: '0.25rem' }}>
                          <strong>Required Action:</strong> {d.clinical_action}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Tab 2: Batch CSV Upload & Drift Monitor */
        <div>
          <div className="card">
            <h3>Batch Cohort CKD Screening &amp; Schema Protection Guard</h3>
            <p style={{ fontSize: '0.86rem', color: 'var(--muted)' }}>
              Upload a CSV file containing patient rows with routine kidney lab biomarkers (<code>hemo</code>, <code>sc</code>, <code>sg</code>, <code>pcv</code>, <code>bu</code>, <code>al</code>, etc.).
              Non-renal datasets (e.g., kidney stone calcium oxalate tables) are rejected automatically by the clinical schema guard, and
              training-anchored PSI / KS / Mahalanobis OOD drift metrics are computed for every batch.
            </p>
            <div style={{ display: 'flex', gap: '0.7rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
                <Upload size={16} />
                {batchLoading ? 'Screening Cohort...' : 'Upload Patient Cohort CSV'}
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleBatchFileChange}
                  disabled={batchLoading}
                  style={{ display: 'none' }}
                />
              </label>
              <button type="button" className="btn" onClick={handleDownloadSampleCsv}>
                <Download size={15} /> Download Sample Valid CSV
              </button>
              {batchResult?.sanitized_csv && (
                <button type="button" className="btn" onClick={handleDownloadSanitizedBatch}>
                  <Download size={15} /> Export Sanitized Results CSV
                </button>
              )}
            </div>
          </div>

          {batchError && <div className="alert alert-danger">{batchError}</div>}

          {batchResult && !batchResult.schema_valid && (
            <div className="alert alert-danger">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
                <AlertTriangle size={18} /> Clinical Schema Guard Rejected Uploaded CSV
              </div>
              <div style={{ marginTop: '0.35rem' }}>{batchResult.schema_message}</div>
            </div>
          )}

          {batchResult && batchResult.schema_valid && (
            <div>
              <div className="alert alert-ok">{batchResult.schema_message}</div>
              <div className="grid-4" style={{ marginBottom: '1rem' }}>
                <div className="kpi-tile">
                  <div className="kpi-label">Total Patients</div>
                  <div className="kpi-value">{batchResult.total_rows}</div>
                  <div className="kpi-note">Valid predictions: {batchResult.predictions_available}</div>
                </div>
                <div className="kpi-tile">
                  <div className="kpi-label">High / Critical Risk</div>
                  <div className="kpi-value" style={{ color: '#b91c1c' }}>{batchResult.high_or_critical_risk}</div>
                  <div className="kpi-note">Conformal abstentions: {batchResult.conformal_abstentions}</div>
                </div>
                <div className="kpi-tile">
                  <div className="kpi-label">Mean CRI Score</div>
                  <div className="kpi-value">{(batchResult.mean_cri * 100).toFixed(1)}%</div>
                  <div className="kpi-note">Quantile q: {Number(batchResult.conformal_quantile).toFixed(3)}</div>
                </div>
                <div className="kpi-tile">
                  <div className="kpi-label">Covariate Drift Status</div>
                  <div className="kpi-value" style={{ fontSize: '1.05rem' }}>
                    {batchResult.drift_report?.overall_drift_status || 'N/A'}
                  </div>
                  <div className="kpi-note">
                    Max PSI: {Number(batchResult.drift_report?.max_psi || 0).toFixed(3)} &bull; OOD rows:{' '}
                    {batchResult.drift_report?.ood_row_count ?? 0}
                  </div>
                </div>
              </div>

              {batchResult.drift_report?.feature_drift_details && (
                <div className="card">
                  <h3>Training-Anchored Covariate Shift (X_train N=320 Reference)</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Biomarker</th>
                          <th>Train Mean</th>
                          <th>Batch Mean</th>
                          <th>PSI</th>
                          <th>KS Stat</th>
                          <th>KS p-value</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {batchResult.drift_report.feature_drift_details.map((f) => (
                          <tr key={f.feature}>
                            <td><code>{f.feature}</code></td>
                            <td>{f.train_mean != null ? Number(f.train_mean).toFixed(2) : '—'}</td>
                            <td>{f.batch_mean != null ? Number(f.batch_mean).toFixed(2) : '—'}</td>
                            <td>{f.psi != null ? Number(f.psi).toFixed(4) : '—'}</td>
                            <td>{f.ks_stat != null ? Number(f.ks_stat).toFixed(4) : '—'}</td>
                            <td>{f.ks_pvalue != null ? Number(f.ks_pvalue).toFixed(4) : '—'}</td>
                            <td>{f.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="card">
                <h3>Patient-Level Screened Batch Output ({batchResult.rows?.length || 0} rows)</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>Diagnosis</th>
                        <th>Risk Prob</th>
                        <th>Category</th>
                        <th>CRI</th>
                        <th>Conformal Set</th>
                        <th>Gate</th>
                        <th>Mahalanobis</th>
                        <th>OOD</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(batchResult.rows || []).slice(0, 100).map((r, i) => (
                        <tr key={i}>
                          <td>#{i + 1}</td>
                          <td>{r.diagnosis || r.prediction_status}</td>
                          <td>{r.risk_probability != null ? `${(Number(r.risk_probability) * 100).toFixed(1)}%` : 'Abstain'}</td>
                          <td>{r.risk_category}</td>
                          <td>{r.clinical_reliability_index}</td>
                          <td><code>{r.conformal_set}</code></td>
                          <td>{r.conformal_gate_decision}</td>
                          <td>{r.mahalanobis_distance}</td>
                          <td>{r.mahalanobis_ood_flag ? 'OOD' : 'In-Dist'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
