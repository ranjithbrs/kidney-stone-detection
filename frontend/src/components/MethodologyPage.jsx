import React from 'react'

export default function MethodologyPage() {
  return (
    <div className="overview-page-container">
      <div className="panel">
        <h2 className="panel-title">Clinical Progression &amp; Risk Prediction Methodology</h2>
        <div className="panel-desc">
          Mathematical formulations underpinning CKD-EPI filtration, Tangri KFRE failure prognosis, and Linear Mixed Model trajectories.
        </div>

        <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="method-card">
            <h3 style={{ fontSize: '0.96rem', fontWeight: 600, color: '#0f766e' }}>
              1. Race-Free CKD-EPI 2021 eGFR Equation
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              Replaces legacy race-stratified coefficients with the validated ASNK/NKF 2021 race-free creatinine equation:
            </p>
            <div className="formula-box">
              <code>
                eGFR = 142 × min(S_cr / κ, 1)^α × max(S_cr / κ, 1)^(-1.200) × 0.9938^Age × (1.012 if female)
              </code>
            </div>
            <ul style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.45rem', paddingLeft: '1.2rem' }}>
              <li>Female: κ = 0.7, α = -0.241</li>
              <li>Male: κ = 0.9, α = -0.302</li>
            </ul>
          </div>

          <div className="method-card">
            <h3 style={{ fontSize: '0.96rem', fontWeight: 600, color: '#0284c7' }}>
              2. Tangri 4-Variable Kidney Failure Risk Equation (KFRE)
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              Calculates the 2-year and 5-year probability of progressing to end-stage kidney failure requiring dialysis or transplantation:
            </p>
            <div className="formula-box">
              <code>
                Risk = 1 - S_0(t)^exp( β_age·Age + β_sex·Sex + β_eGFR·eGFR + β_uACR·ln(uACR) )
              </code>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.45rem' }}>
              Calibrated separately for North American vs. Non-North American cohorts with baseline survival coefficients S_0(2yr) and S_0(5yr).
            </p>
          </div>

          <div className="method-card">
            <h3 style={{ fontSize: '0.96rem', fontWeight: 600, color: '#d97706' }}>
              3. Linear Mixed-Effects Model (LMM BLUP) &amp; AKI Velocity Guard
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              Separates true chronic kidney function decline from acute hemodynamic swings:
            </p>
            <ul style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.45rem', paddingLeft: '1.2rem' }}>
              <li><strong>Annualized Slope:</strong> Best Linear Unbiased Predictor (BLUP) shrinks individual slopes toward cohort mean when follow-up visits are sparse.</li>
              <li><strong>AKI Velocity Alert:</strong> Flags rapid creatinine rise (&gt;0.3 mg/dL in ≤48h or &ge;50% increase within 7 days) as KDIGO Acute Kidney Injury rather than chronic progression.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
