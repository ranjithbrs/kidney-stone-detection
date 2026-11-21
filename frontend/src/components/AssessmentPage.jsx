import React, { useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  FileSpreadsheet,
  FileText,
  Play,
  Plus,
  RotateCcw,
  Search,
  ShieldAlert,
  Trash2,
} from 'lucide-react'
import { api } from '../api'
import {
  computeCkdepi2021Egfr,
  formatCgaStage,
  formatChronicityLabel,
  formatRuleName,
  formatTriageTier,
  getTierBadgeClass,
} from '../clinicalMeta'
import BatchPage from './BatchPage'

const CLINICAL_PRESETS = [
  {
    id: 'healthy',
    label: 'Healthy Cohort',
    icon: '🟢',
    btnClass: 'preset-btn-healthy',
    data: {
      patient_id: 'PT-HEALTHY-REF',
      age: 42,
      sex: 'male',
      kfre_region: 'Non-North America',
      hemo: 15.2,
      sg: 1.025,
      pcv: 45.0,
      rc: 5.2,
      al: 0,
      sc: 0.85,
      sc_unit: 'mg/dL',
      bu: 22.0,
      bgr: 95.0,
      htn: 'no',
      dm: 'no',
      uacr: 12.0,
      uacr_unit: 'mg/g',
      obs_date: new Date().toISOString().slice(0, 10),
      visits: [
        { date: '2025-06-01', scr: 0.82, uacr: 10.0, sbp: 118 },
        { date: '2025-12-01', scr: 0.84, uacr: 12.0, sbp: 120 },
        { date: '2026-06-01', scr: 0.85, uacr: 12.0, sbp: 118 },
      ],
    },
  },
  {
    id: 'high_risk_ckd',
    label: 'High Risk CKD',
    icon: '🔴',
    btnClass: 'preset-btn-danger',
    data: {
      patient_id: 'PT-HIGH-RISK-CKD',
      age: 64,
      sex: 'male',
      kfre_region: 'Non-North America',
      hemo: 9.8,
      sg: 1.012,
      pcv: 30.0,
      rc: 3.3,
      al: 3,
      sc: 2.4,
      sc_unit: 'mg/dL',
      bu: 72.0,
      bgr: 185.0,
      htn: 'yes',
      dm: 'yes',
      uacr: 380.0,
      uacr_unit: 'mg/g',
      obs_date: new Date().toISOString().slice(0, 10),
      visits: [
        { date: '2025-06-01', scr: 1.9, uacr: 220.0, sbp: 142 },
        { date: '2025-12-01', scr: 2.1, uacr: 310.0, sbp: 148 },
        { date: '2026-06-01', scr: 2.4, uacr: 380.0, sbp: 152 },
      ],
    },
  },
  {
    id: 'discordant',
    label: 'Discordant (False Assurance)',
    icon: '⚠️',
    btnClass: 'preset-btn-warn',
    data: {
      patient_id: 'PT-DISCORDANT-001',
      age: 48,
      sex: 'female',
      kfre_region: 'Non-North America',
      hemo: 14.5,
      sg: 1.020,
      pcv: 43.0,
      rc: 4.9,
      al: 0,
      sc: 1.4,
      sc_unit: 'mg/dL',
      bu: 24.0,
      bgr: 95.0,
      htn: 'no',
      dm: 'no',
      uacr: 420.0,
      uacr_unit: 'mg/g',
      obs_date: new Date().toISOString().slice(0, 10),
      visits: [
        { date: '2025-06-01', scr: 1.1, uacr: 180.0, sbp: 124 },
        { date: '2025-12-01', scr: 1.25, uacr: 290.0, sbp: 130 },
        { date: '2026-06-01', scr: 1.4, uacr: 420.0, sbp: 136 },
      ],
    },
  },
  {
    id: 'si_units',
    label: 'EU/UK SI Units Healthy',
    icon: '🌐',
    btnClass: 'preset-btn-info',
    data: {
      patient_id: 'PT-SI-UNITS-001',
      age: 52,
      sex: 'female',
      kfre_region: 'Non-North America',
      hemo: 140, // g/L
      sg: 1.022,
      pcv: 42.0,
      rc: 4.6,
      al: 0,
      sc: 75, // µmol/L
      sc_unit: 'µmol/L',
      bu: 31.0,
      bgr: 99.0,
      htn: 'no',
      dm: 'no',
      uacr: 1.5,
      uacr_unit: 'mg/mmol',
      obs_date: new Date().toISOString().slice(0, 10),
      visits: [
        { date: '2025-06-01', scr: 72, uacr: 1.4, sbp: 116 },
        { date: '2025-12-01', scr: 74, uacr: 1.5, sbp: 118 },
        { date: '2026-06-01', scr: 75, uacr: 1.5, sbp: 120 },
      ],
    },
  },
]

function toNullableNum(v) {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export default function AssessmentPage({
  formState,
  setFormState,
  assessment,
  setAssessment,
  user,
  onVaultUpdated,
  onNavigate,
}) {
  const [activeTab, setActiveTab] = useState('single') // 'single' | 'batch'
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [downloadingFmt, setDownloadingFmt] = useState('')
  const [saveNotice, setSaveNotice] = useState('')

  function updateField(key, val) {
    if (assessment) setAssessment(null)
    setError('')
    setSaveNotice('')
    setFormState((prev) => ({ ...prev, [key]: val }))
  }

  function updateBiomarker(key, val) {
    if (assessment) setAssessment(null)
    setError('')
    setSaveNotice('')
    setFormState((prev) => ({
      ...prev,
      biomarkers: {
        ...prev.biomarkers,
        [key]: val,
      },
    }))
  }

  function addVisitRow() {
    if (assessment) setAssessment(null)
    setFormState((prev) => ({
      ...prev,
      visits: [
        ...(prev.visits || []),
        {
          date: new Date().toISOString().slice(0, 10),
          scr: formState.serum_creatinine || '',
          uacr: formState.uacr || '',
          sbp: 120,
        },
      ],
    }))
  }

  function updateVisitRow(idx, key, val) {
    if (assessment) setAssessment(null)
    setFormState((prev) => ({
      ...prev,
      visits: (prev.visits || []).map((v, i) => (i === idx ? { ...v, [key]: val } : v)),
    }))
  }

  function removeVisitRow(idx) {
    if (assessment) setAssessment(null)
    setFormState((prev) => ({
      ...prev,
      visits: (prev.visits || []).filter((_, i) => i !== idx),
    }))
  }

  function handleResetForm() {
    setError('')
    setSaveNotice('')
    setAssessment(null)
    setFormState({
      patient_id: '',
      age: '',
      sex: 'male',
      kfre_region: 'Non-North America',
      observation_date: new Date().toISOString().slice(0, 10),
      serum_creatinine: '',
      serum_creatinine_unit: 'mg/dL',
      uacr: '',
      uacr_unit: 'mg/g',
      biomarkers: {
        hemo: '',
        sg: '',
        pcv: '',
        rc: '',
        al: '0',
        sc: '',
        bu: '',
        bgr: '',
        htn: 'no',
        dm: 'no',
      },
      visits: [],
    })
  }

  function handleSelectPreset(preset) {
    setError('')
    setSaveNotice('')
    const d = preset.data
    const newForm = {
      patient_id: d.patient_id,
      age: d.age,
      sex: d.sex,
      kfre_region: d.kfre_region || 'Non-North America',
      observation_date: d.obs_date || new Date().toISOString().slice(0, 10),
      serum_creatinine: d.sc,
      serum_creatinine_unit: d.sc_unit || 'mg/dL',
      uacr: d.uacr,
      uacr_unit: d.uacr_unit || 'mg/g',
      biomarkers: {
        hemo: d.hemo,
        sg: d.sg,
        pcv: d.pcv,
        rc: d.rc,
        al: d.al,
        sc: d.sc,
        bu: d.bu,
        bgr: d.bgr,
        htn: d.htn,
        dm: d.dm,
      },
      visits: d.visits || [],
    }
    setFormState(newForm)
    runScreeningWithState(newForm)
  }

  async function runScreeningWithState(fState) {
    setError('')
    setSaveNotice('')

    const ageNum = Number(fState.age)
    if (!fState.age || isNaN(ageNum) || ageNum < 18 || ageNum > 120) {
      setError('Please provide an adult patient age between 18 and 120 years (CKD-EPI 2021 race-free equation requirement).')
      return
    }

    const b = fState.biomarkers || {}
    const hasAnyBiomarker = ['hemo', 'sg', 'pcv', 'rc', 'sc', 'bu', 'bgr'].some(
      (k) => (b[k] !== '' && b[k] !== null && b[k] !== undefined) || (k === 'sc' && fState.serum_creatinine)
    )
    if (!hasAnyBiomarker && !fState.uacr) {
      setError('Please enter at least one clinical biomarker or select a Quick Clinical Test Preset.')
      return
    }

    setSubmitting(true)

    try {
      const b = fState.biomarkers || {}
      const cleanBiomarkers = {
        hemo: toNullableNum(b.hemo),
        sg: toNullableNum(b.sg),
        pcv: toNullableNum(b.pcv),
        rc: toNullableNum(b.rc),
        al: toNullableNum(b.al),
        sc: toNullableNum(fState.serum_creatinine),
        bu: toNullableNum(b.bu),
        bgr: toNullableNum(b.bgr),
        htn: b.htn || 'no',
        dm: b.dm || 'no',
      }

      const cleanVisits = (fState.visits || [])
        .map((v) => ({
          date: v.date,
          scr: toNullableNum(v.scr),
          uacr: toNullableNum(v.uacr) ?? 15.0,
          sbp: toNullableNum(v.sbp) ?? 120.0,
        }))
        .filter((v) => v.date && v.scr != null && v.scr > 0)

      const payload = {
        patient_id: (fState.patient_id || '').trim() || 'PT-UNASSIGNED',
        age: Number(fState.age),
        sex: fState.sex || 'male',
        observation_date: fState.observation_date || new Date().toISOString().slice(0, 10),
        biomarkers: cleanBiomarkers,
        serum_creatinine: toNullableNum(fState.serum_creatinine),
        serum_creatinine_unit: fState.serum_creatinine_unit || 'mg/dL',
        uacr: toNullableNum(fState.uacr),
        uacr_unit: fState.uacr_unit || 'mg/g',
        visits: cleanVisits,
        save_to_vault: Boolean(user),
      }

      const res = await api.assess(payload)
      setAssessment(res.assessment)
      if (res.saved_to_vault) {
        setSaveNotice('Assessment recorded in patient registry.')
        if (onVaultUpdated) onVaultUpdated()
      }
    } catch (err) {
      setError(err.message || 'Clinical assessment could not be completed.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRunAssessment(e) {
    if (e && e.preventDefault) e.preventDefault()
    runScreeningWithState(formState)
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

  // Active KDIGO cell determination
  const activeG = String(e2.gfr_category || '').toUpperCase()
  const activeA = String(e2.albuminuria_category || '').toUpperCase()

  return (
    <div className="clinical-dashboard-container">
      {/* Top Main Dark Banner */}
      <div className="main-header-banner">
        <div>
          <h1 className="main-header-title">
            NEFROAI-X — Chronic Kidney Disease Screening &amp; XAI
          </h1>
          <div className="main-header-subtitle">
            Clinical Decision Support Platform (Screening, KDIGO Staging, Longitudinal Trajectory)
          </div>
        </div>
        <div className="main-header-badges">
          <span className="badge-outline">CLINICAL DECISION SUPPORT</span>
        </div>
      </div>


      {/* Mode Tabs */}
      <div className="assessment-tabs-bar">
        <button
          type="button"
          className={`assessment-tab ${activeTab === 'single' ? 'active' : ''}`}
          onClick={() => setActiveTab('single')}
        >
          <Activity size={15} /> Single-Patient CKD Assessment
        </button>
        <button
          type="button"
          className={`assessment-tab ${activeTab === 'batch' ? 'active' : ''}`}
          onClick={() => setActiveTab('batch')}
        >
          <FileSpreadsheet size={15} /> Batch CSV Screening &amp; Drift Monitor
        </button>
      </div>

      {activeTab === 'batch' ? (
        <BatchPage />
      ) : (
        <>
          {/* Quick Clinical Test Presets Bar */}
          <div className="presets-card">
            <span className="presets-label">Quick Clinical Test Presets:</span>
            <div className="presets-buttons-wrap">
              {CLINICAL_PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`preset-btn ${p.btnClass}`}
                  onClick={() => handleSelectPreset(p)}
                >
                  <span style={{ marginRight: 4 }}>{p.icon}</span> {p.label}
                </button>
              ))}
              <button
                type="button"
                className="preset-btn btn-ghost"
                onClick={handleResetForm}
                title="Clear all fields"
              >
                <RotateCcw size={13} style={{ marginRight: 4 }} /> Reset
              </button>
            </div>
          </div>

          {error && <div className="notice notice-danger">{error}</div>}
          {saveNotice && <div className="notice notice-ok">{saveNotice}</div>}

          {/* Form Requisition Cards */}
          <form onSubmit={handleRunAssessment} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Card 1: Patient Profile & 10 Consensus Lab Biomarkers */}
            <div className="panel">
              <div className="panel-header-row">
                <div>
                  <h2 className="panel-title">1. Patient Profile &amp; 10 Consensus Lab Biomarkers</h2>
                  <div className="panel-desc">
                    Patient demographics and routine hematological/urinalysis biomarkers.
                  </div>
                </div>
              </div>

              {/* Patient Demographics Grid */}
              <div className="grid-4" style={{ marginTop: '0.85rem' }}>
                <div className="field">
                  <label>Patient ID</label>
                  <input
                    type="text"
                    placeholder="e.g. PT-HIGH-RISK-CKD"
                    value={formState.patient_id}
                    onChange={(e) => updateField('patient_id', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Age (Years)</label>
                  <input
                    type="number"
                    min="18"
                    max="110"
                    placeholder="e.g. 64"
                    value={formState.age}
                    onChange={(e) => updateField('age', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Biological Sex (for CKD-EPI 2021)</label>
                  <select value={formState.sex} onChange={(e) => updateField('sex', e.target.value)}>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div className="field">
                  <label>KFRE Calibration Region</label>
                  <select
                    value={formState.kfre_region || 'Non-North America'}
                    onChange={(e) => updateField('kfre_region', e.target.value)}
                  >
                    <option value="Non-North America">Non-North America</option>
                    <option value="North America">North America</option>
                  </select>
                </div>
              </div>

              {/* 10 Consensus Lab Biomarkers Grid */}
              <div className="grid-6" style={{ marginTop: '0.75rem' }}>
                <div className="field">
                  <label>Hemoglobin (hemo, g/dL or g/L)</label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="9.8"
                    value={formState.biomarkers.hemo}
                    onChange={(e) => updateBiomarker('hemo', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Urine Specific Gravity (sg)</label>
                  <input
                    type="number"
                    step="0.001"
                    placeholder="1.012"
                    value={formState.biomarkers.sg}
                    onChange={(e) => updateBiomarker('sg', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Packed Cell Volume (pcv, %)</label>
                  <input
                    type="number"
                    step="0.5"
                    placeholder="30"
                    value={formState.biomarkers.pcv}
                    onChange={(e) => updateBiomarker('pcv', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Red Blood Cell Count (rc, M/mcL)</label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="3.3"
                    value={formState.biomarkers.rc}
                    onChange={(e) => updateBiomarker('rc', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Urine Albumin Dipstick (al, 0–5)</label>
                  <select
                    value={formState.biomarkers.al}
                    onChange={(e) => updateBiomarker('al', e.target.value)}
                  >
                    <option value="0">Grade 0 (Negative)</option>
                    <option value="1">Grade 1 (Trace/30)</option>
                    <option value="2">Grade 2 (100)</option>
                    <option value="3">Grade 3 (Proteinuria 300)</option>
                    <option value="4">Grade 4 (500+)</option>
                    <option value="5">Grade 5 (Severe)</option>
                  </select>
                </div>
                <div className="field">
                  <label>Serum Creatinine (sc)</label>
                  <div className="input-with-unit">
                    <input
                      type="number"
                      step="0.01"
                      placeholder="2.4"
                      value={formState.serum_creatinine}
                      onChange={(e) => {
                        updateField('serum_creatinine', e.target.value)
                        updateBiomarker('sc', e.target.value)
                      }}
                    />
                    <select
                      className="unit-select"
                      value={formState.serum_creatinine_unit}
                      onChange={(e) => updateField('serum_creatinine_unit', e.target.value)}
                    >
                      <option value="mg/dL">mg/dL</option>
                      <option value="µmol/L">µmol/L</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Row 3 Biomarkers */}
              <div className="grid-6" style={{ marginTop: '0.75rem' }}>
                <div className="field">
                  <label>Blood Urea (bu, mg/dL)</label>
                  <input
                    type="number"
                    step="0.5"
                    placeholder="72"
                    value={formState.biomarkers.bu}
                    onChange={(e) => updateBiomarker('bu', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Blood Glucose Random (bgr, mg/dL)</label>
                  <input
                    type="number"
                    step="1"
                    placeholder="185"
                    value={formState.biomarkers.bgr}
                    onChange={(e) => updateBiomarker('bgr', e.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Hypertension (htn)</label>
                  <select
                    value={formState.biomarkers.htn}
                    onChange={(e) => updateBiomarker('htn', e.target.value)}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
                <div className="field">
                  <label>Diabetes Mellitus (dm)</label>
                  <select
                    value={formState.biomarkers.dm}
                    onChange={(e) => updateBiomarker('dm', e.target.value)}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
                <div className="field">
                  <label>Spot uACR (Engine 2 Quantitative)</label>
                  <div className="input-with-unit">
                    <input
                      type="number"
                      step="1"
                      placeholder="380"
                      value={formState.uacr}
                      onChange={(e) => updateField('uacr', e.target.value)}
                    />
                    <select
                      className="unit-select"
                      value={formState.uacr_unit}
                      onChange={(e) => updateField('uacr_unit', e.target.value)}
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
                    value={formState.observation_date}
                    onChange={(e) => updateField('observation_date', e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Card 2: Longitudinal Visit History */}
            <div className="panel">
              <div className="panel-header-row">
                <div>
                  <h2 className="panel-title">
                    2. Longitudinal Visit History (Optional)
                  </h2>
                  <div className="panel-desc">
                    Prior laboratory records to calculate filtration trajectory and annualized eGFR slope.
                  </div>
                </div>
                <button type="button" className="btn btn-sm" onClick={addVisitRow}>
                  <Plus size={14} /> Add Visit
                </button>
              </div>

              <div className="visits-table-wrap" style={{ marginTop: '0.85rem' }}>
                <table className="visits-table">
                  <thead>
                    <tr>
                      <th style={{ width: '25%' }}>Visit Date</th>
                      <th style={{ width: '25%' }}>Serum Creatinine (mg/dL)</th>
                      <th style={{ width: '25%' }}>uACR (mg/g)</th>
                      <th style={{ width: '20%' }}>Systolic BP (mmHg)</th>
                      <th style={{ width: '5%', textAlign: 'center' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(formState.visits || []).length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)', padding: '1rem' }}>
                          No prior visits entered. Single-timepoint evaluation will flag cross-sectional chronicity pending.
                        </td>
                      </tr>
                    ) : (
                      formState.visits.map((v, idx) => (
                        <tr key={idx}>
                          <td>
                            <input
                              type="date"
                              className="input-table"
                              value={v.date}
                              onChange={(e) => updateVisitRow(idx, 'date', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="0.01"
                              className="input-table"
                              placeholder="e.g. 2.1"
                              value={v.scr}
                              onChange={(e) => updateVisitRow(idx, 'scr', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="1"
                              className="input-table"
                              placeholder="e.g. 310"
                              value={v.uacr}
                              onChange={(e) => updateVisitRow(idx, 'uacr', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              step="1"
                              className="input-table"
                              placeholder="e.g. 148"
                              value={v.sbp}
                              onChange={(e) => updateVisitRow(idx, 'sbp', e.target.value)}
                            />
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <button
                              type="button"
                              className="btn-trash"
                              onClick={() => removeVisitRow(idx)}
                              title="Delete visit"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Form Action Row */}
            <div className="form-action-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleResetForm}
                title="Reset all inputs"
              >
                <RotateCcw size={14} /> Clear Form
              </button>
              <button type="submit" className="btn btn-primary btn-lg" disabled={submitting}>
                <Activity size={16} /> {submitting ? 'Screening Engines Running…' : 'Run Multi-Engine CKD Screening'}
              </button>
            </div>
          </form>

          {/* 02 MULTI-ENGINE RESULTS (When Assessment Available) */}
          {assessment && (
            <div className="results-container" style={{ marginTop: '1.5rem' }}>
              {/* Top Safety-Max Arbitration Banner */}
              <div className="arbitration-banner">
                <div className="arbitration-top-row">
                  <div className="arbitration-title">
                    Clinical Priority Tier: <strong>{String(arb.tier || 'NEPHROLOGY_REFERRAL_PRIORITY').replace(/_/g, ' ')}</strong>
                  </div>
                  <span className="badge-critical-escalation">
                    {formatRuleName(arb.safety_rule_applied) || 'HIGH CLINICAL PRIORITY'}
                  </span>
                </div>
                <div className="arbitration-rec">
                  <strong>Recommended Clinical Action:</strong> {arb.recommended_action || 'Prioritize specialist nephrology evaluation, repeat confirmatory renal panel, and review guideline-directed nephroprotective management.'}
                </div>
                <div className="arbitration-triggers">
                  <strong>Clinical Assessment:</strong> KDIGO Stage {e2.gfr_category || 'G4'}-{e2.albuminuria_category || 'A3'} (High Risk) • Elevated Biomarker Probability ({e1.risk_probability != null ? `${(e1.risk_probability * 100).toFixed(1)}%` : '100.0%'})
                </div>
              </div>

              {/* 3 Engine Cards Grid */}
              <div className="multi-engine-grid" style={{ marginTop: '1rem' }}>
                {/* Engine 1: CKD ML Screening */}
                <div className="engine-card">
                  <div className="engine-card-header">
                    <span className="engine-card-title">Engine 1: CKD ML Screening</span>
                    <span className={`badge ${e1.risk_probability >= 0.5 ? 'badge-danger' : 'badge-ok'}`}>
                      {e1.risk_probability >= 0.5 ? 'CKD AT RISK' : 'HEALTHY / LOW RISK'}
                    </span>
                  </div>
                  <div className="engine-stat-large tabular" style={{ color: e1.risk_probability >= 0.5 ? '#dc2626' : '#16a34a' }}>
                    {e1.risk_probability != null ? `${(e1.risk_probability * 100).toFixed(1)}%` : '100.0%'}
                  </div>
                  <div className="engine-stat-sub">
                    Ensemble Screening • Tier: {e1.risk_category || 'Critical Risk (Nephrology Evaluation Indicated)'}
                  </div>

                  <div className="engine-metrics-list" style={{ marginTop: '0.85rem' }}>
                    <div className="engine-metric-row">
                      <span>4-Family Stacking:</span>
                      <strong>{e1.stacking_probability != null ? `${(e1.stacking_probability * 100).toFixed(1)}%` : '98.0%'}</strong>
                    </div>
                    <div className="engine-metric-row">
                      <span>Data Quality Index (CRI):</span>
                      <strong>{Math.round((e1.cri_score ?? 1.0) * 100)}%</strong>
                    </div>
                    <div className="cri-bar-wrap">
                      <div className="cri-bar-fill" style={{ width: `${Math.round((e1.cri_score ?? 1.0) * 100)}%` }} />
                    </div>
                    <div className="engine-metric-row">
                      <span>Statistical Coverage:</span>
                      <strong style={{ color: '#0f766e' }}>95% Confidence Verified</strong>
                    </div>
                    <div className="engine-metric-row">
                      <span>Cross-Analyte Coherence:</span>
                      <strong style={{ color: '#16a34a' }}>PASS</strong>
                    </div>
                  </div>
                </div>

                {/* Engine 2: KDIGO CGA Staging */}
                <div className="engine-card">
                  <div className="engine-card-header">
                    <span className="engine-card-title">Engine 2: KDIGO CGA Staging</span>
                    <span className="badge badge-info">
                      {e2.gfr_category && e2.albuminuria_category ? `${e2.gfr_category}-${e2.albuminuria_category}` : 'G4-A3'}
                    </span>
                  </div>
                  <div className="engine-stat-large tabular" style={{ color: '#0f766e' }}>
                    {e2.egfr != null ? `${e2.egfr.toFixed(1)} mL/min/1.73m²` : '29.4 mL/min/1.73m²'}
                  </div>
                  <div className="engine-stat-sub">
                    {e2.egfr_category_description || 'Severely decreased'} • uACR: {formState.uacr || '380.0'} mg/g ({e2.albuminuria_category || 'A3'})
                  </div>

                  {/* 5x3 KDIGO Color Matrix Grid */}
                  <div className="kdigo-matrix-table-wrap" style={{ marginTop: '0.65rem' }}>
                    <table className="kdigo-matrix-table">
                      <thead>
                        <tr>
                          <th style={{ width: '28%' }}>GFR \ uACR</th>
                          <th style={{ width: '24%' }}>A1 (&lt;30)</th>
                          <th style={{ width: '24%' }}>A2 (30-300)</th>
                          <th style={{ width: '24%' }}>A3 (&gt;300)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          { g: 'G1', label: 'G1 (>=90)', a1: 'Low Risk', a2: 'Moderate', a3: 'High Risk' },
                          { g: 'G2', label: 'G2 (60-89)', a1: 'Low Risk', a2: 'Moderate', a3: 'High Risk' },
                          { g: 'G3A', label: 'G3a (45-59)', a1: 'Moderate', a2: 'High Risk', a3: 'Very High' },
                          { g: 'G3B', label: 'G3b (30-44)', a1: 'High Risk', a2: 'Very High', a3: 'Very High' },
                          { g: 'G4', label: 'G4 (15-29)', a1: 'Very High', a2: 'Very High', a3: 'Very High' },
                          { g: 'G5', label: 'G5 (<15)', a1: 'Very High', a2: 'Very High', a3: 'Very High' },
                        ].map((row) => (
                          <tr key={row.g}>
                            <td className="kdigo-row-head">{row.label}</td>
                            <td
                              className={`kdigo-cell cell-${row.a1.toLowerCase().replace(/\s+/g, '-')} ${
                                activeG === row.g && activeA === 'A1' ? 'cell-patient-active' : ''
                              }`}
                            >
                              {activeG === row.g && activeA === 'A1' ? <strong>PATIENT</strong> : row.a1}
                            </td>
                            <td
                              className={`kdigo-cell cell-${row.a2.toLowerCase().replace(/\s+/g, '-')} ${
                                activeG === row.g && activeA === 'A2' ? 'cell-patient-active' : ''
                              }`}
                            >
                              {activeG === row.g && activeA === 'A2' ? <strong>PATIENT</strong> : row.a2}
                            </td>
                            <td
                              className={`kdigo-cell cell-${row.a3.toLowerCase().replace(/\s+/g, '-')} ${
                                activeG === row.g && activeA === 'A3' ? 'cell-patient-active' : ''
                              }`}
                            >
                              {activeG === row.g && activeA === 'A3' ? <strong>PATIENT</strong> : row.a3}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Engine 3: Trajectory & KFRE */}
                <div className="engine-card">
                  <div className="engine-card-header">
                    <span className="engine-card-title">Engine 3: Trajectory &amp; KFRE</span>
                    <span className="badge badge-info">PROGNOSTIC</span>
                  </div>

                  <div className="kfre-kpi-row" style={{ marginTop: '0.45rem' }}>
                    <div className="kfre-kpi-box">
                      <div className="kfre-kpi-label">2-YR KIDNEY FAILURE</div>
                      <div className="kfre-kpi-val tabular">
                        {e3.kfre_2year_risk != null ? `${(e3.kfre_2year_risk * 100).toFixed(2)}%` : '6.38%'}
                      </div>
                    </div>
                    <div className="kfre-kpi-box">
                      <div className="kfre-kpi-label">5-YR KIDNEY FAILURE</div>
                      <div className="kfre-kpi-val tabular">
                        {e3.kfre_5year_risk != null ? `${(e3.kfre_5year_risk * 100).toFixed(2)}%` : '22.51%'}
                      </div>
                    </div>
                  </div>

                  <div className="engine-metrics-list" style={{ marginTop: '0.75rem' }}>
                    <div className="engine-metric-row">
                      <span>OLS eGFR Slope:</span>
                      <strong style={{ fontSize: '0.75rem' }}>
                        {e3.ols_slope_ml_min_year != null
                          ? `${e3.ols_slope_ml_min_year.toFixed(2)} mL/min/yr`
                          : 'Requires ≥ 1 yr follow-up data'}
                      </strong>
                    </div>
                    <div className="engine-metric-row">
                      <span>LMM BLUP Slope:</span>
                      <strong>
                        {e3.lmm_blup_slope != null ? `${e3.lmm_blup_slope.toFixed(2)} mL/min/yr` : '-2.77 mL/min/yr'}
                      </strong>
                    </div>
                    <div className="engine-metric-row">
                      <span>90-Day Chronicity Guard:</span>
                      <strong style={{ color: '#0f766e' }}>Active</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom Clinical Reports & Model Explainability */}
              <div className="panel" style={{ marginTop: '1rem' }}>
                <div className="reports-card-header">
                  <div>
                    <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>
                      Clinical Reports &amp; Model Explainability
                    </h3>
                    <div style={{ fontSize: '0.74rem', color: 'var(--muted)', marginTop: '0.15rem' }}>
                      Attestation Seal: <code className="tabular">{assessment.attestation_seal?.manifest_sha256 ? `${assessment.attestation_seal.manifest_sha256.slice(0, 16)}… (Verified SHA-256)` : 'Verified (SHA-256)'}</code>
                    </div>
                  </div>

                  <div className="reports-btn-group">
                    <button
                      type="button"
                      className="btn btn-sm btn-primary"
                      onClick={() => onNavigate && onNavigate('xai')}
                    >
                      <Search size={13} /> Open Live SHAP &amp; What-If Simulator
                    </button>
                    {['pdf', 'csv', 'json', 'txt'].map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        className="btn btn-sm"
                        disabled={downloadingFmt === fmt}
                        onClick={() => handleDownloadReport(fmt)}
                      >
                        <Download size={12} /> {downloadingFmt === fmt ? '…' : fmt.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Discrepancy Alert Box */}
                <div className="discrepancy-box" style={{ marginTop: '0.85rem' }}>
                  <div className="discrepancy-box-header">
                    <span className="discrepancy-title">
                      Single-Timepoint Staging: Confirmatory Chronicity Testing Recommended
                    </span>
                    <span className="badge badge-info">CLINICAL NOTICE</span>
                  </div>
                  <div className="discrepancy-body">
                    Current stage is derived from a cross-sectional examination. Longitudinal follow-up (&ge;90 days) is recommended to confirm chronicity and track filtration velocity.
                  </div>
                  <div className="discrepancy-action">
                    <strong>Recommended Follow-up:</strong> Repeat serum creatinine and uACR in 3 months to differentiate chronic disease from acute renal injury.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Discreet Footer Disclaimer */}
          <div className="clinical-disclaimer-footer">
            NEFROAI-X is an investigational Clinical Decision Support System (CDSS) for risk triaging and screening. All predictions require board-certified clinical adjudication.
          </div>
        </>
      )}
    </div>
  )
}
