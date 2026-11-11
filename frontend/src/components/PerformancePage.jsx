import React, { useEffect, useState } from 'react'
import { BarChart3, ShieldCheck } from 'lucide-react'
import { api } from '../api'

const MODEL_COLORS = ['#64748b', '#0f4c81', '#0e7490', '#7c3aed', '#d97706', '#059669']

function SvgMultiCurve({ title, xLabel, yLabel, series, diagonal = false }) {
  const W = 340
  const H = 220
  const pad = 34

  const toX = (x) => pad + x * (W - 2 * pad)
  const toY = (y) => H - pad - y * (H - 2 * pad)

  return (
    <div style={{ background: '#f8fafc', border: '1px solid var(--border)', borderRadius: '12px', padding: '0.8rem' }}>
      <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#0b1f3a', marginBottom: '0.35rem' }}>{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={title}>
        {/* Grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={toX(0)} y1={toY(t)} x2={toX(1)} y2={toY(t)} stroke="#e2e8f0" strokeWidth="1" />
            <line x1={toX(t)} y1={toY(0)} x2={toX(t)} y2={toY(1)} stroke="#e2e8f0" strokeWidth="1" />
            <text x={pad - 5} y={toY(t) + 3} fontSize="9" fill="#64748b" textAnchor="end">{t.toFixed(2)}</text>
            <text x={toX(t)} y={H - pad + 13} fontSize="9" fill="#64748b" textAnchor="middle">{t.toFixed(2)}</text>
          </g>
        ))}
        {/* Axes */}
        <line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke="#475569" strokeWidth="1.2" />
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="#475569" strokeWidth="1.2" />
        {diagonal && (
          <line x1={toX(0)} y1={toY(0)} x2={toX(1)} y2={toY(1)} stroke="#94a3b8" strokeDasharray="4 4" strokeWidth="1.2" />
        )}
        {/* Series Paths */}
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
              stroke={MODEL_COLORS[idx % MODEL_COLORS.length]}
              strokeWidth={s.name.includes('Stacking') || s.name.includes('Random Forest') ? '2.4' : '1.5'}
            />
          )
        })}
        <text x={W / 2} y={H - 4} fontSize="10" fill="#334155" textAnchor="middle" fontWeight="600">{xLabel}</text>
        <text x={11} y={H / 2} fontSize="10" fill="#334155" textAnchor="middle" fontWeight="600" transform={`rotate(-90 11 ${H / 2})`}>
          {yLabel}
        </text>
      </svg>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', marginTop: '0.3rem', fontSize: '0.71rem' }}>
        {series.map((s, idx) => (
          <span key={s.name} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '10px', height: '3px', background: MODEL_COLORS[idx % MODEL_COLORS.length], display: 'inline-block' }} />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function PerformancePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api.performance()
      .then((res) => { if (active) setData(res) })
      .catch((err) => { if (active) setError(err.message || 'Could not load performance benchmark.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (loading) return <div className="card">Computing held-out benchmark, calibration curves, and 5-fold CV stability...</div>
  if (error) return <div className="alert alert-danger">{error}</div>
  if (!data) return null

  const rep = data.stacking_report
  const models = Object.values(rep.models || {})
  const stab = data.feature_selection_stability
  const splitCal = data.conformal_split
  const mondCal = data.conformal_mondrian

  return (
    <div>
      {/* KPI Header */}
      <div className="grid-4" style={{ marginBottom: '1rem' }}>
        <div className="kpi-tile">
          <div className="kpi-label">Held-Out Test Cohort</div>
          <div className="kpi-value">N = {rep.test_samples}</div>
          <div className="kpi-note">Strictly isolated from Train (N={rep.train_samples})</div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-label">CV Feature Stability</div>
          <div className="kpi-value">{Number(stab.mean_pairwise_jaccard).toFixed(4)}</div>
          <div className="kpi-note">5-fold pairwise Jaccard index</div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-label">Split Conformal q</div>
          <div className="kpi-value">{Number(splitCal.conformal_quantile).toFixed(4)}</div>
          <div className="kpi-note">{splitCal.calibration_method} (95% target)</div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-label">Mondrian q (H / CKD)</div>
          <div className="kpi-value" style={{ fontSize: '1.25rem' }}>
            {Number(mondCal.q_healthy).toFixed(3)} / {Number(mondCal.q_ckd).toFixed(3)}
          </div>
          <div className="kpi-note">Class-conditional finite-sample calibration</div>
        </div>
      </div>

      {/* 6-Architecture Table */}
      <div className="card">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <BarChart3 size={18} color="#0f4c81" />
          Multi-Architecture Benchmark &amp; Calibration (Held-Out Test N={rep.test_samples})
        </h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model Architecture</th>
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
                  <td><strong>{m.model_name}</strong></td>
                  <td>{(m.accuracy * 100).toFixed(1)}%</td>
                  <td>{(m.sensitivity * 100).toFixed(1)}%</td>
                  <td>{(m.specificity * 100).toFixed(1)}%</td>
                  <td>{Number(m.macro_f1).toFixed(4)}</td>
                  <td>{Number(m.roc_auc).toFixed(4)}</td>
                  <td>{Number(m.pr_auc).toFixed(4)}</td>
                  <td>{Number(m.brier_score).toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* SVG Charts: ROC, PR, Calibration */}
      <div className="grid-3" style={{ marginBottom: '1rem' }}>
        <SvgMultiCurve
          title="ROC Curves (Held-Out N=80)"
          xLabel="False Positive Rate"
          yLabel="True Positive Rate"
          diagonal
          series={models.map((m) => ({
            name: m.model_name.split(' ')[0],
            xs: m.roc_curve?.fpr || [],
            ys: m.roc_curve?.tpr || [],
          }))}
        />
        <SvgMultiCurve
          title="Precision-Recall Curves"
          xLabel="Recall"
          yLabel="Precision"
          series={models.map((m) => ({
            name: m.model_name.split(' ')[0],
            xs: m.pr_curve?.recall || [],
            ys: m.pr_curve?.precision || [],
          }))}
        />
        <SvgMultiCurve
          title="Calibration Reliability Diagram"
          xLabel="Mean Predicted Probability"
          yLabel="Fraction Positive"
          diagonal
          series={models.map((m) => ({
            name: m.model_name.split(' ')[0],
            xs: m.calibration_curve?.prob_pred || [],
            ys: m.calibration_curve?.prob_true || [],
          }))}
        />
      </div>

      {/* Meta-Learner + Feature Stability + Subgroups */}
      <div className="grid-2">
        <div className="card">
          <h3>4-Family Meta-Learner &amp; 5-Fold Feature Consensus</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
            Out-of-fold Logistic Regression meta-weights blend tree-based, boosted, kernel, and neural hypotheses inside training partitions only.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', marginBottom: '0.85rem' }}>
            {Object.entries(rep.meta_learner_weights || {}).map(([name, w]) => (
              <span key={name} className="pill pill-blue">{name}: {Number(w).toFixed(3)}</span>
            ))}
          </div>

          <div style={{ fontWeight: 700, fontSize: '0.84rem', marginBottom: '0.4rem' }}>
            5-Fold Consensus Top-10 Selection Frequencies:
          </div>
          {Object.entries(stab.feature_frequencies || {}).map(([feat, cnt]) => (
            <div className="bar-row" key={feat}>
              <div><code>{feat}</code></div>
              <div className="bar-track">
                <div className="bar-fill-blue" style={{ width: `${(cnt / stab.n_splits) * 100}%` }} />
              </div>
              <div style={{ textAlign: 'right', fontWeight: 700 }}>{cnt} / {stab.n_splits} folds</div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <ShieldCheck size={18} color="#047857" /> Stratified Clinical Subgroup Audit
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Subgroup</th>
                  <th>N</th>
                  <th>CKD Prev</th>
                  <th>Accuracy</th>
                  <th>Sensitivity</th>
                  <th>Brier</th>
                </tr>
              </thead>
              <tbody>
                {(rep.subgroup_analysis || []).map((s) => (
                  <tr key={s.subgroup}>
                    <td><strong>{s.subgroup}</strong></td>
                    <td>{s.n}</td>
                    <td>{(s.ckd_prevalence * 100).toFixed(1)}%</td>
                    <td>{(s.accuracy * 100).toFixed(1)}%</td>
                    <td>{s.sensitivity != null ? `${(s.sensitivity * 100).toFixed(1)}%` : '—'}</td>
                    <td>{s.brier_score != null ? Number(s.brier_score).toFixed(4) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

