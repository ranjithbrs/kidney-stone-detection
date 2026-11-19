import React from 'react'
import { AlertTriangle, BookOpen, ShieldCheck } from 'lucide-react'

export default function GovernancePage() {
  return (
    <div className="overview-page-container">
      <div className="panel">
        <h2 className="panel-title">Clinical Governance &amp; Regulatory Framework</h2>
        <div className="panel-desc">
          Quality assurance standards, clinical decision support software (CDSS) scope, and research attestation.
        </div>

        <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="notice notice-warn">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}>
              <AlertTriangle size={16} /> Non-Diagnostic Investigational Software Declaration
            </div>
            <p style={{ marginTop: '0.35rem', fontSize: '0.82rem' }}>
              NEFROAI-X is an investigational Clinical Decision Support System (CDSS) designed for screening assistance and risk triaging. It does <strong>not</strong> provide a definitive medical diagnosis or replace board-certified physician judgment. All predictions and suggestions must be reviewed alongside clinical evaluation and confirmatory testing.
            </p>
          </div>

          <div className="panel panel-tight">
            <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>Reference Literature &amp; Citation</h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              This platform extends the machine learning and feature selection framework described in:
            </p>
            <div style={{ background: 'var(--surface-muted)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', marginTop: '0.5rem', fontFamily: 'monospace' }}>
              Md. Sadi Al Huda et al., "Explainable and Real-Time Framework for Predicting Chronic Kidney Disease Using Diverse Machine Learning Models and Different Feature Selection Techniques," <em>IEEE Access</em>, 2024.
            </div>
          </div>

          <div className="panel panel-tight">
            <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>Data Provenance &amp; Integrity Controls</h3>
            <ul style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.45rem', paddingLeft: '1.2rem' }}>
              <li><strong>Zero Imputation Leakage:</strong> Scalers, median imputers, and SMOTE resamplers are trained strictly on training partitions; test evaluations are never touched during parameter estimation.</li>
              <li><strong>SHA-256 Tamper-Evident Attestation:</strong> Every patient assessment creates a cryptographic SHA-256 seal anchoring input biomarkers, engine results, and model parameters.</li>
              <li><strong>Spreadsheet Formula Injection Defense:</strong> All CSV and tabular outputs are sanitized against CWE-1236 formula injection characters (<code>=</code>, <code>+</code>, <code>-</code>, <code>@</code>).</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
