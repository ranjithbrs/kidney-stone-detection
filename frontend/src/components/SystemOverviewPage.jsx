import React from 'react'
import { Activity, ArrowRight, CheckCircle2, ShieldCheck, Zap } from 'lucide-react'

export default function SystemOverviewPage({ onNavigate }) {
  return (
    <div className="overview-page-container">
      {/* Hero KPI Grid */}
      <div className="hero-kpi-grid">
        <div className="hero-kpi-card">
          <div className="hero-kpi-label">OBSERVED ACCURACY</div>
          <div className="hero-kpi-val">100.0%</div>
          <div className="hero-kpi-note">95% CI: [95.5%, 100.0%] (N=80 held-out)</div>
        </div>
        <div className="hero-kpi-card">
          <div className="hero-kpi-label">CLINICAL SENSITIVITY</div>
          <div className="hero-kpi-val" style={{ color: '#16a34a' }}>0 FN</div>
          <div className="hero-kpi-note">Zero False Negatives in primary evaluation</div>
        </div>
        <div className="hero-kpi-card">
          <div className="hero-kpi-label">CONSENSUS BIOMARKERS</div>
          <div className="hero-kpi-val">Top 10</div>
          <div className="hero-kpi-note">Hybrid: MI, ANOVA F, RF Gini &amp; RFE</div>
        </div>
        <div className="hero-kpi-card">
          <div className="hero-kpi-label">STACKING BRIER SCORE</div>
          <div className="hero-kpi-val" style={{ color: '#0f766e' }}>0.0014</div>
          <div className="hero-kpi-note">4-Family Ensemble: RF + XGB + SVM + MLP</div>
        </div>
      </div>

      {/* 3 Engine Suite Architecture Cards */}
      <div className="panel" style={{ marginTop: '1.25rem' }}>
        <h2 className="panel-title">3-Engine Integrated Clinical Decision Support Architecture</h2>
        <div className="panel-desc">
          Replicating and enhancing the methodology published in <em>IEEE Access</em> (Md. Sadi Al Huda et al.).
        </div>

        <div className="grid-3" style={{ marginTop: '1rem', gap: '1rem' }}>
          <div className="engine-overview-box">
            <div className="engine-badge-tag">ENGINE 1</div>
            <h3 style={{ fontSize: '1rem', marginTop: '0.45rem', fontWeight: 600 }}>
              Early Risk Stratification &amp; Screening
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              Random Forest champion model (50 estimators) trained on 10 routine hematology and urinalysis biomarkers. Protected with Split Conformal prediction (95% coverage), Magnitude-Inferred Dimensional Reconciliation (MIDR), and Clinical Reliability Index (CRI).
            </p>
          </div>

          <div className="engine-overview-box">
            <div className="engine-badge-tag" style={{ background: '#0284c7' }}>ENGINE 2</div>
            <h3 style={{ fontSize: '1rem', marginTop: '0.45rem', fontWeight: 600 }}>
              KDIGO 2024 CGA Staging
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              Computes race-free CKD-EPI 2021 filtration rates (mL/min/1.73m²) and maps urine albumin-to-creatinine ratio (uACR) into standard CGA staging grid (G1–G5 × A1–A3) with chronicity verification.
            </p>
          </div>

          <div className="engine-overview-box">
            <div className="engine-badge-tag" style={{ background: '#d97706' }}>ENGINE 3</div>
            <h3 style={{ fontSize: '1rem', marginTop: '0.45rem', fontWeight: 600 }}>
              Longitudinal Progression &amp; KFRE
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              Computes Linear Mixed Model (LMM BLUP) annualized filtration slopes, applies an acute creatinine spike velocity guard (&gt;0.3 mg/dL in 48h), and forecasts 2-year and 5-year kidney failure risk via Tangri equations.
            </p>
          </div>
        </div>

        <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.75rem' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onNavigate('screening')}
          >
            Launch Patient Screening <ArrowRight size={14} />
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => onNavigate('benchmarks')}
          >
            View Model Calibration &amp; Benchmarks
          </button>
        </div>
      </div>

      {/* KDIGO Reference Matrix Grid */}
      <div className="panel" style={{ marginTop: '1.25rem' }}>
        <h2 className="panel-title">KDIGO 2024 Clinical Prognosis &amp; Risk Grid</h2>
        <div className="panel-desc">
          Official staging matrix determining referral thresholds and monitoring frequency.
        </div>

        <div className="kdigo-matrix-table-wrap" style={{ marginTop: '1rem' }}>
          <table className="kdigo-matrix-table">
            <thead>
              <tr>
                <th style={{ width: '25%' }}>GFR Category (mL/min/1.73m²)</th>
                <th style={{ width: '25%' }}>A1: Normal to Mild (&lt;30 mg/g)</th>
                <th style={{ width: '25%' }}>A2: Moderately Increased (30–300 mg/g)</th>
                <th style={{ width: '25%' }}>A3: Severely Increased (&gt;300 mg/g)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="kdigo-row-head">G1: Normal or high (&ge;90)</td>
                <td className="kdigo-cell cell-low-risk">Low Risk (Annual)</td>
                <td className="kdigo-cell cell-moderate">Moderate (Yearly)</td>
                <td className="kdigo-cell cell-high-risk">High Risk (2x/year)</td>
              </tr>
              <tr>
                <td className="kdigo-row-head">G2: Mildly decreased (60–89)</td>
                <td className="kdigo-cell cell-low-risk">Low Risk (Annual)</td>
                <td className="kdigo-cell cell-moderate">Moderate (Yearly)</td>
                <td className="kdigo-cell cell-high-risk">High Risk (2x/year)</td>
              </tr>
              <tr>
                <td className="kdigo-row-head">G3a: Mild to moderate (45–59)</td>
                <td className="kdigo-cell cell-moderate">Moderate (Yearly)</td>
                <td className="kdigo-cell cell-high-risk">High Risk (2x/year)</td>
                <td className="kdigo-cell cell-very-high">Very High (3x/year)</td>
              </tr>
              <tr>
                <td className="kdigo-row-head">G3b: Moderate to severe (30–44)</td>
                <td className="kdigo-cell cell-high-risk">High Risk (2x/year)</td>
                <td className="kdigo-cell cell-very-high">Very High (3x/year)</td>
                <td className="kdigo-cell cell-very-high">Very High (4x/year)</td>
              </tr>
              <tr>
                <td className="kdigo-row-head">G4: Severely decreased (15–29)</td>
                <td className="kdigo-cell cell-very-high">Very High (3x/year)</td>
                <td className="kdigo-cell cell-very-high">Very High (3x/year)</td>
                <td className="kdigo-cell cell-very-high">Very High (Nephrology Referral)</td>
              </tr>
              <tr>
                <td className="kdigo-row-head">G5: Kidney failure (&lt;15)</td>
                <td className="kdigo-cell cell-very-high">Very High (Immediate Care)</td>
                <td className="kdigo-cell cell-very-high">Very High (Immediate Care)</td>
                <td className="kdigo-cell cell-very-high">Very High (Transplant/Dialysis)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
