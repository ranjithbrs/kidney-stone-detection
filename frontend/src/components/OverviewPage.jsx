import React from 'react'
import { Activity, ArrowRight, BrainCircuit, Layers, ShieldAlert, ShieldCheck, Stethoscope, TrendingUp } from 'lucide-react'

export default function OverviewPage({ health, onNavigate, onOpenAuth, user }) {
  return (
    <div>
      {/* Executive KPI Strip */}
      <div className="grid-4" style={{ marginBottom: '1.1rem' }}>
        <div className="kpi-tile">
          <div className="kpi-label">Primary Motive</div>
          <div className="kpi-value" style={{ fontSize: '1.2rem' }}>Early CKD Detection</div>
          <div className="kpi-note">Detects kidney disease from routine blood &amp; urine labs</div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-label">Consensus Biomarkers</div>
          <div className="kpi-value">10 / 24 Labs</div>
          <div className="kpi-note">Jaccard 5-Fold Stability: 0.9273</div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-label">Conformal Guarantee</div>
          <div className="kpi-value">95% Coverage</div>
          <div className="kpi-note">Split &amp; Mondrian abstention gates</div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-label">Cloud Storage Engine</div>
          <div className="kpi-value" style={{ fontSize: '1.15rem' }}>
            {health?.cloud_postgres_connected ? 'Supabase Postgres' : 'SQLite + Cloud API'}
          </div>
          <div className="kpi-note">
            SHA-256 Attested &bull; {user ? `Signed in: ${user.username}` : 'Sign in to save records'}
          </div>
        </div>
      </div>

      {/* Plain-English Workflow Action Banner */}
      <div className="card card-accent" style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
        <div style={{ maxWidth: '680px' }}>
          <h2 style={{ fontSize: '1.22rem', marginBottom: '0.35rem' }}>
            Explainable Early Kidney Risk Screening — Built for Both Doctors &amp; Patients
          </h2>
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '0.45rem' }}>
            Enter 10 routine laboratory measurements (hemoglobin, urine albumin, serum creatinine, blood urea, blood pressure, etc.).
            NEFROAI-X simultaneously runs machine learning CKD screening, KDIGO stage mapping, 2-year/5-year kidney failure forecasting,
            and live Game-Theoretic SHAP explanations in one safety-arbitrated report.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" className="btn btn-primary" onClick={() => onNavigate('assessment')}>
              <Stethoscope size={16} />
              Start Patient CKD Screening
              <ArrowRight size={15} />
            </button>
            {!user && (
              <button type="button" className="btn" onClick={() => onOpenAuth('signup')}>
                Create Clinician Account
              </button>
            )}
            <button type="button" className="btn" onClick={() => onNavigate('performance')}>
              View Benchmark &amp; Calibration
            </button>
          </div>
        </div>
        <div style={{ background: '#f8fafc', border: '1px solid var(--border)', borderRadius: '12px', padding: '0.85rem 1rem', minWidth: '250px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#0f4c81', marginBottom: '0.35rem' }}>
            Active Safety Certification
          </div>
          <div style={{ fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.28rem' }}>
            <div><ShieldCheck size={14} color="#047857" style={{ verticalAlign: 'text-bottom' }} /> Champion RF SHA-256 Verified</div>
            <div><BrainCircuit size={14} color="#0f4c81" style={{ verticalAlign: 'text-bottom' }} /> 4-Family Stacking (RF/XGB/SVM/MLP)</div>
            <div><Activity size={14} color="#0e7490" style={{ verticalAlign: 'text-bottom' }} /> MIDR SI-Unit Converter &amp; COH-01..04</div>
            <div><ShieldAlert size={14} color="#b45309" style={{ verticalAlign: 'text-bottom' }} /> Survival ML Deferred Pending CRIC DUA</div>
          </div>
        </div>
      </div>

      {/* Three Clinical Engines */}
      <div className="grid-3" style={{ marginBottom: '1rem' }}>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Stethoscope size={18} color="#0f4c81" />
              Engine 1: CKD Screening
            </h3>
            <span className="pill pill-green">ONLINE</span>
          </div>
          <p style={{ fontSize: '0.86rem', color: 'var(--muted)' }}>
            Point-of-care CKD triage using 10 consensus blood &amp; urine labs. Combines the protected Champion Random Forest
            with a 4-Family Stacking Ensemble, MIDR international unit normalization, and Split + Mondrian Conformal abstention gates.
          </p>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Layers size={18} color="#0e7490" />
              Engine 2: KDIGO Staging
            </h3>
            <span className="pill pill-green">ONLINE</span>
          </div>
          <p style={{ fontSize: '0.86rem', color: 'var(--muted)' }}>
            Computes the 2021 race-free CKD-EPI eGFR alongside urine albumin-to-creatinine ratio (uACR) to place each patient
            inside the exact 28-cell KDIGO G1–G5 &times; A1–A3 clinical prognosis matrix.
          </p>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <TrendingUp size={18} color="#7c3aed" />
              Engine 3: Progression
            </h3>
            <span className="pill pill-amber">SURVIVAL ML DEFERRED</span>
          </div>
          <p style={{ fontSize: '0.86rem', color: 'var(--muted)' }}>
            Tracks longitudinal multi-visit kidney decline via OLS eGFR slope, Linear Mixed Models (LMM), walk-forward backtests,
            an Acute Kidney Injury (AKI) spike guard vs 90-day chronicity, and calibrated 2-year / 5-year KFRE failure risk.
          </p>
        </div>
      </div>

      {/* 5-Stage Safety Architecture Visual */}
      <div className="card">
        <h3 style={{ marginBottom: '0.65rem' }}>Safety-Max Multi-Engine Clinical Workflow</h3>
        <div className="grid-4" style={{ gap: '0.75rem' }}>
          <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#0f4c81' }}>1. Reliability &amp; Unit Check</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '0.2rem' }}>
              MIDR auto-converts SI units (&mu;mol/L, g/L, mmol/L) and computes CRI quality score + COH-01..04 hematology/renal coherence rules.
            </div>
          </div>
          <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#0f4c81' }}>2. Conformal + Ensemble</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '0.2rem' }}>
              Random Forest + XGBoost/SVM/MLP stacking agree on probability, while Mondrian Conformal sets flag uncertain borderline cases.
            </div>
          </div>
          <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#0f4c81' }}>3. KDIGO &amp; Trajectory</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '0.2rem' }}>
              Cross-checks AI risk against CKD-EPI 2021 eGFR, uACR, 90-day persistence vs AKI spike velocity, and KFRE risk.
            </div>
          </div>
          <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#0f4c81' }}>4. Arbitration &amp; Audit</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '0.2rem' }}>
              Non-compensatory Safety-Max arbitration (DISC-01..10) + SHA-256 tamper seal + PDF/CSV/JSON/TXT clinical exports.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

