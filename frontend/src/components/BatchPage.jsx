import React, { useState } from 'react'
import { CheckCircle2, FileSpreadsheet, Upload } from 'lucide-react'
import { api } from '../api'
import {
  formatCoherenceStatus,
  formatGateDecision,
  formatTriageTier,
  getTierBadgeClass,
} from '../clinicalMeta'

export default function BatchPage() {
  const [batchFile, setBatchFile] = useState(null)
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchError, setBatchError] = useState('')
  const [batchResult, setBatchResult] = useState(null)

  async function handleBatchRun(e) {
    e.preventDefault()
    if (!batchFile) {
      setBatchError('Choose a CSV file containing renal laboratory panels first.')
      return
    }
    setBatchLoading(true)
    setBatchError('')
    try {
      const res = await api.batchScreen(batchFile)
      setBatchResult(res)
    } catch (err) {
      setBatchError(err.message || 'Batch screening failed.')
    } finally {
      setBatchLoading(false)
    }
  }

  async function handleDownloadTemplateCsv() {
    try {
      const raw = await api.sampleBatchCsv()
      const text = typeof raw?.text === 'function' ? await raw.text() : String(raw || '')
      const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'nefroai_cohort_template.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setBatchError(err.message || 'Could not download CSV template.')
    }
  }

  function handleDownloadSanitizedCsv() {
    if (!batchResult?.sanitized_csv) return
    const blob = new Blob([batchResult.sanitized_csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'nefroai_batch_results_sanitized.csv'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Batch Screening</h1>
          <p className="page-subtitle">
            Import laboratory CSV cohorts for bulk CKD triage, schema validation, and population shift monitoring.
          </p>
        </div>
        <button type="button" className="btn" onClick={handleDownloadTemplateCsv}>
          <FileSpreadsheet size={14} /> Download CSV template
        </button>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Upload Cohort Laboratory File</h2>
            <p className="panel-desc">
              Accepts UTF-8 CSV exports with renal panel columns (Serum Creatinine, Hemoglobin, Urine Albumin, Blood Urea).
            </p>
          </div>
        </div>

        {batchError && <div className="notice notice-danger">{batchError}</div>}

        <form onSubmit={handleBatchRun} style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setBatchFile(e.target.files?.[0] || null)}
            style={{ fontSize: '0.84rem' }}
          />
          <button type="submit" className="btn btn-primary" disabled={batchLoading || !batchFile}>
            <Upload size={14} /> {batchLoading ? 'Screening Cohort…' : 'Run Batch Screening'}
          </button>
        </form>
      </div>

      {batchResult && !batchResult.schema_valid && (
        <div className="notice notice-danger">
          <strong>Incompatible CSV Schema:</strong> {batchResult.schema_message}
        </div>
      )}

      {batchResult && batchResult.schema_valid && (
        <>
          <div className="metric-strip">
            <div className="metric-cell">
              <div className="metric-label">Patients Screened</div>
              <div className="metric-val tabular">{batchResult.total_rows}</div>
              <div className="metric-sub tabular">{batchResult.predictions_available} evaluated</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">High-Priority Cases</div>
              <div className="metric-val tabular">{batchResult.high_or_critical_risk}</div>
              <div className="metric-sub">Recommended for specialist review</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Held for Review</div>
              <div className="metric-val tabular">{batchResult.conformal_abstentions}</div>
              <div className="metric-sub">Incomplete or uncertain lab profiles</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Mean Panel Quality</div>
              <div className="metric-val tabular">{Number(batchResult.mean_cri || 0).toFixed(2)}</div>
              <div className="metric-sub">
                Cohort distribution: {formatTriageTier(batchResult.drift_report?.overall_drift_status || 'Checked')}
              </div>
            </div>
          </div>

          {batchResult.drift_report && (
            <div className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Cohort Distribution Check</h2>
                  <p className="panel-desc tabular">
                    Population Stability Index (max): {Number(batchResult.drift_report.max_psi || 0).toFixed(3)} · Outlier rows:{' '}
                    {batchResult.drift_report.ood_row_count ?? 0}
                  </p>
                </div>
                <span
                  className={`badge ${
                    batchResult.drift_report.overall_drift_status === 'STABLE' ? 'badge-ok' : 'badge-warn'
                  }`}
                >
                  {formatTriageTier(batchResult.drift_report.overall_drift_status)}
                </span>
              </div>
              <div className="table-wrap">
                <table className="clean-table">
                  <thead>
                    <tr>
                      <th>Biomarker</th>
                      <th>PSI Score</th>
                      <th>KS Statistic / p-value</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(batchResult.drift_report.feature_drift_details || []).map((f) => (
                      <tr key={f.feature}>
                        <td style={{ fontWeight: 500, color: 'var(--text)' }}>{f.feature}</td>
                        <td className="tabular">{f.psi != null ? Number(f.psi).toFixed(3) : '—'}</td>
                        <td className="tabular">
                          {f.ks_stat != null ? Number(f.ks_stat).toFixed(3) : '—'} (p=
                          {f.ks_p_value != null ? Number(f.ks_p_value).toFixed(3) : '—'})
                        </td>
                        <td>
                          <span className={`badge ${f.status === 'STABLE' ? 'badge-ok' : 'badge-warn'}`}>
                            {formatTriageTier(f.status)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Cohort Screening Results</h2>
                <p className="panel-desc">Showing screened records with sanitized CSV export.</p>
              </div>
              {batchResult.sanitized_csv && (
                <button type="button" className="btn btn-sm" onClick={handleDownloadSanitizedCsv}>
                  <CheckCircle2 size={14} /> Export Results CSV
                </button>
              )}
            </div>
            <div className="table-wrap">
              <table className="clean-table">
                <thead>
                  <tr>
                    <th>Patient / Row</th>
                    <th>Risk Score</th>
                    <th>Prediction Interval</th>
                    <th>Panel Quality</th>
                    <th>Lab Coherence</th>
                    <th>Clinical Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {(batchResult.rows || []).slice(0, 100).map((row, idx) => (
                    <tr key={idx}>
                      <td className="tabular" style={{ fontWeight: 500, color: 'var(--text)' }}>
                        {row.patient_id || `Row ${idx + 1}`}
                      </td>
                      <td className="tabular">
                        {row.risk_probability != null ? `${(row.risk_probability * 100).toFixed(1)}%` : 'Held'}
                      </td>
                      <td className="tabular">
                        {Array.isArray(row.conformal_set) ? `{${row.conformal_set.join(', ')}}` : '—'}
                      </td>
                      <td className="tabular">{row.cri != null ? Number(row.cri).toFixed(2) : '—'}</td>
                      <td>
                        <span className={`badge ${row.coherence_status === 'COHERENT' ? 'badge-ok' : 'badge-warn'}`}>
                          {formatCoherenceStatus(row.coherence_status)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${getTierBadgeClass(row.gate_decision || row.risk_category)}`}>
                          {formatGateDecision(row.gate_decision || row.risk_category)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
