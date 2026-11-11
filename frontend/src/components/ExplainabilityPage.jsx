import React, { useEffect, useState } from 'react'
import { BrainCircuit, CheckCircle2, RefreshCw, Sliders } from 'lucide-react'
import { api } from '../api'

export default function ExplainabilityPage({ formState, onNavigate }) {
  const [targetRisk, setTargetRisk] = useState(0.2)
  const [maxChanges, setMaxChanges] = useState(2)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState(null)

  async function runExplain(tRisk = targetRisk, mChanges = maxChanges) {
    setError('')
    setLoading(true)
    try {
      const biomarkers = {
        ...formState.biomarkers,
        hemo: Number(formState.biomarkers.hemo),
        sg: Number(formState.biomarkers.sg),
        pcv: Number(formState.biomarkers.pcv),
        rc: Number(formState.biomarkers.rc),
        al: Number(formState.biomarkers.al),
        sc: Number(formState.biomarkers.sc),
        bu: Number(formState.biomarkers.bu),
        bgr: Number(formState.biomarkers.bgr),
      }
      const res = await api.explain({
        biomarkers,
        uacr_mg_g: formState.uacr !== '' && formState.uacr != null ? Number(formState.uacr) : null,
        target_max_risk: Number(tRisk),
        max_changes: Number(mChanges),
      })
      setData(res)
    } catch (err) {
      setError(err.message || 'Could not compute XAI attribution.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runExplain()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formState.patient_id])

  const shap = data?.treeshap
  const lime = data?.lime
  const conc = data?.concordance
  const cf = data?.counterfactual

  const maxAbsShap = shap?.top_drivers?.length
    ? Math.max(...shap.top_drivers.map((d) => Math.abs(d.shap_value)), 0.01)
    : 1

  const maxAbsLime = lime?.rules?.length
    ? Math.max(...lime.rules.map((r) => Math.abs(r.weight)), 0.01)
    : 1

  return (
    <div>
      {/* Controls & Concordance Banner */}
      <div className="card card-accent">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <BrainCircuit size={20} color="#0f4c81" />
              Live Game-Theoretic SHAP, Surrogate LIME &amp; What-If Simulator
            </h3>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
              Explaining patient <strong>{formState.patient_id}</strong> using exact <code>shap.TreeExplainer</code> (never Gini heuristics) paired with LIME.
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div className="field" style={{ width: '165px' }}>
              <label>Target Max Risk: {(targetRisk * 100).toFixed(0)}%</label>
              <input
                type="range"
                min="0.10"
                max="0.40"
                step="0.05"
                value={targetRisk}
                onChange={(e) => setTargetRisk(Number(e.target.value))}
              />
            </div>
            <div className="field" style={{ width: '140px' }}>
              <label>Max Bio Shifts</label>
              <select value={maxChanges} onChange={(e) => setMaxChanges(Number(e.target.value))}>
                <option value={1}>1 biomarker</option>
                <option value={2}>2 biomarkers</option>
                <option value={3}>3 biomarkers</option>
              </select>
            </div>
            <button type="button" className="btn btn-primary" disabled={loading} onClick={() => runExplain()}>
              <RefreshCw size={15} /> {loading ? 'Computing...' : 'Recompute Live XAI'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {data && (
        <div>
          {/* Concordance Summary */}
          {conc && (
            <div className="grid-4" style={{ marginBottom: '1rem' }}>
              <div className="kpi-tile">
                <div className="kpi-label">Concordance Status</div>
                <div className="kpi-value" style={{ fontSize: '1.05rem', color: '#047857' }}>
                  {conc.concordance_status}
                </div>
                <div className="kpi-note">Spearman rho: {conc.spearman_rank_corr ?? 'N/A'}</div>
              </div>
              <div className="kpi-tile">
                <div className="kpi-label">Top-3 Feature Overlap</div>
                <div className="kpi-value">{conc.top3_overlap_count} / 3</div>
                <div className="kpi-note">SHAP vs LIME agreement</div>
              </div>
              <div className="kpi-tile">
                <div className="kpi-label">Sign Agreement</div>
                <div className="kpi-value">{(conc.sign_agreement_ratio * 100).toFixed(0)}%</div>
                <div className="kpi-note">Direction polarity match</div>
              </div>
              <div className="kpi-tile">
                <div className="kpi-label">TreeSHAP Additivity</div>
                <div className="kpi-value" style={{ fontSize: '1.15rem' }}>
                  &epsilon; = {shap?.additivity_error?.toExponential(2)}
                </div>
                <div className="kpi-note">Exact E[f(X)] + &Sigma;&phi; = f(x)</div>
              </div>
            </div>
          )}

          {/* Dual Columns: TreeSHAP & LIME */}
          <div className="grid-2">
            <div className="card">
              <h3>Exact <code>shap.TreeExplainer</code> Attributions</h3>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '0.8rem' }}>
                Base rate: {(shap?.base_value * 100).toFixed(1)}% &rarr; Predicted risk:{' '}
                <strong>{(shap?.predicted_probability * 100).toFixed(1)}%</strong>
              </div>
              {(shap?.top_drivers || []).map((d) => {
                const widthPct = Math.min(100, Math.round((Math.abs(d.shap_value) / maxAbsShap) * 100))
                const pos = d.shap_value >= 0
                return (
                  <div className="bar-row" key={d.feature}>
                    <div title={`Value: ${d.clinical_value}`}>
                      <strong>{d.label}</strong>{' '}
                      <span style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>({String(d.clinical_value)})</span>
                    </div>
                    <div className="bar-track">
                      <div className={pos ? 'bar-fill-pos' : 'bar-fill-neg'} style={{ width: `${widthPct}%` }} />
                    </div>
                    <div style={{ textAlign: 'right', fontWeight: 700, color: pos ? '#b91c1c' : '#047857' }}>
                      {pos ? '+' : ''}{d.shap_value.toFixed(3)}
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="card">
              <h3>Live Surrogate LIME Decision Rules</h3>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '0.8rem' }}>
                Local linear surrogate on standardized training distribution (600 perturbations).
              </div>
              {(lime?.rules || []).map((r, idx) => {
                const widthPct = Math.min(100, Math.round((Math.abs(r.weight) / maxAbsLime) * 100))
                const pos = r.weight >= 0
                return (
                  <div className="bar-row" key={idx}>
                    <div style={{ fontFamily: 'monospace', fontSize: '0.76rem' }}>{r.rule}</div>
                    <div className="bar-track">
                      <div className={pos ? 'bar-fill-pos' : 'bar-fill-neg'} style={{ width: `${widthPct}%` }} />
                    </div>
                    <div style={{ textAlign: 'right', fontWeight: 700, color: pos ? '#b91c1c' : '#047857' }}>
                      {pos ? '+' : ''}{r.weight.toFixed(3)}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Constrained Counterfactual What-If Recourse */}
          {cf && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.6rem', marginBottom: '0.6rem' }}>
                <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <Sliders size={18} color="#0f4c81" />
                  Constrained Clinical Counterfactual What-If Simulator
                </h3>
                <span className={`pill ${cf.target_achieved ? 'pill-green' : 'pill-amber'}`}>
                  {cf.target_achieved ? 'TARGET CONFORMAL {0} ACHIEVED' : 'PARTIAL REDUCTION ONLY'}
                </span>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
                {cf.notes} Initial Risk: <strong>{(cf.initial_probability * 100).toFixed(1)}%</strong>{' '}
                (Set <code>{JSON.stringify(cf.initial_conformal_set)}</code>)
                {cf.target_probability != null && (
                  <> &rarr; Simulated Risk: <strong>{(cf.target_probability * 100).toFixed(1)}%</strong> (Set <code>{JSON.stringify(cf.target_conformal_set)}</code>)</>
                )}
              </p>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '0.7rem' }}>
                Locked immutable clinical factors: <code>{(cf.locked_immutable_features || []).join(', ')}</code>
              </div>

              {(cf.suggested_shifts || []).length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Modifiable Lab Biomarker</th>
                        <th>Current Measured Value</th>
                        <th>Simulated Target Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cf.suggested_shifts.map((s) => (
                        <tr key={s.feature}>
                          <td><strong>{s.label}</strong> (<code>{s.feature}</code>)</td>
                          <td>{s.current_value}</td>
                          <td style={{ color: '#047857', fontWeight: 700 }}>{s.target_value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="alert alert-ok" style={{ marginBottom: 0 }}>
                  <CheckCircle2 size={16} style={{ verticalAlign: 'text-bottom', marginRight: '6px' }} />
                  Patient profile already within target low-risk region or no safe shift required.
                </div>
              )}

              <div style={{ marginTop: '0.75rem' }}>
                <button type="button" className="btn btn-sm" onClick={() => onNavigate('assessment')}>
                  Return to Assessment Form
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
