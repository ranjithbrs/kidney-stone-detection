import React, { useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  BrainCircuit,
  Database,
  Home,
  LogIn,
  LogOut,
  ShieldCheck,
  Stethoscope,
  TrendingUp,
  UserPlus,
} from 'lucide-react'
import { api, getStoredToken, setStoredToken } from './api'
import AuthModal from './components/AuthModal'
import AssessmentPage from './components/AssessmentPage'
import ExplainabilityPage from './components/ExplainabilityPage'
import OverviewPage from './components/OverviewPage'
import PerformancePage from './components/PerformancePage'
import { GovernanceGuidePage, ProgressionGuidePage, VaultPage } from './components/VaultAndGuidesPage'

const DEFAULT_TODAY = new Date().toISOString().slice(0, 10)

const INITIAL_FORM = {
  patient_id: 'PT-HIGH-RISK-CKD',
  age: 64,
  sex: 'male',
  biomarkers: {
    hemo: 9.8,
    sg: 1.01,
    pcv: 30,
    sc: 2.4,
    rc: 3.3,
    al: 3,
    bu: 72,
    bgr: 185,
    htn: 'yes',
    dm: 'yes',
  },
  serum_creatinine: 2.4,
  serum_creatinine_unit: 'mg/dL',
  uacr: 380,
  uacr_unit: 'mg/g',
  observation_date_scr: DEFAULT_TODAY,
  observation_date_uacr: DEFAULT_TODAY,
  kfre_calibration: 'NON_NORTH_AMERICA',
  visits: [],
  auto_save: true,
}

const NAV_ITEMS = [
  { id: 'overview', label: 'System Overview', icon: Home },
  { id: 'assessment', label: 'CKD Screening & Labs', icon: Stethoscope },
  { id: 'explainability', label: 'Live XAI & What-If', icon: BrainCircuit },
  { id: 'performance', label: 'Benchmark & Calibration', icon: BarChart3 },
  { id: 'vault', label: 'Cloud Vault & Audit', icon: Database },
  { id: 'progression', label: 'Progression Methodology', icon: TrendingUp },
  { id: 'governance', label: 'Clinical Governance', icon: BookOpen },
]

export default function App() {
  const [page, setPage] = useState('overview')
  const [health, setHealth] = useState(null)
  const [presets, setPresets] = useState({})
  const [user, setUser] = useState(null)
  const [authModalMode, setAuthModalMode] = useState(null)
  const [formState, setFormState] = useState(INITIAL_FORM)
  const [assessment, setAssessment] = useState(null)
  const [vaultRefreshKey, setVaultRefreshKey] = useState(0)

  useEffect(() => {
    api.health().then(setHealth).catch(() => {})
    api
      .presets()
      .then((d) => {
        if (d?.presets) {
          setPresets(d.presets)
          const p = d.presets.high_risk_ckd
          if (p) {
            setFormState((prev) => ({
              ...prev,
              patient_id: p.patient_id,
              age: p.age,
              sex: p.sex,
              biomarkers: { ...p.biomarkers },
              serum_creatinine: p.serum_creatinine,
              serum_creatinine_unit: p.serum_creatinine_unit || 'mg/dL',
              uacr: p.uacr,
              uacr_unit: p.uacr_unit || 'mg/g',
              visits: (p.visits || []).map((v) => ({ ...v })),
            }))
          }
        }
      })
      .catch(() => {})

    if (getStoredToken()) {
      api
        .me()
        .then((res) => {
          if (res?.user) setUser(res.user)
        })
        .catch(() => setStoredToken(''))
    }
  }, [])

  function handleSignOut() {
    setStoredToken('')
    setUser(null)
  }

  function handleLoadPatientVisits(patientId, visits) {
    setFormState((prev) => ({
      ...prev,
      patient_id: patientId,
      visits: visits || [],
    }))
    setPage('assessment')
  }

  const storageLabel = health?.cloud_postgres_connected ? 'CLOUD POSTGRES (SUPABASE)' : 'SQLITE VAULT (CLOUD READY)'

  return (
    <div className="app-shell">
      {/* Executive Dark-Navy Sidebar */}
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-title">
            <Activity size={22} color="#38bdf8" />
            <span>NEFROAI-X</span>
          </div>
          <div className="brand-sub">Explainable Renal CDSS &bull; Research SaaS</div>
        </div>

        {/* Account Auth Widget */}
        <div className="sidebar-section-label">Clinician Session</div>
        <div className="auth-sidebar-box">
          {user ? (
            <div>
              <div style={{ fontWeight: 700, color: '#ffffff', fontSize: '0.9rem' }}>{user.full_name}</div>
              <div style={{ fontSize: '0.75rem', color: '#93c5fd', marginBottom: '0.55rem' }}>
                @{user.username} &bull; {user.role}
              </div>
              <button type="button" className="btn btn-sidebar" onClick={handleSignOut}>
                <LogOut size={14} /> Sign Out
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <div style={{ fontSize: '0.77rem', color: '#cbd5e1', marginBottom: '0.15rem' }}>
                Guest Mode — screening active; sign in to save records permanently.
              </div>
              <button type="button" className="btn btn-sidebar" onClick={() => setAuthModalMode('signin')}>
                <LogIn size={14} /> Sign In
              </button>
              <button type="button" className="btn btn-sidebar" onClick={() => setAuthModalMode('signup')}>
                <UserPlus size={14} /> Create Account
              </button>
            </div>
          )}
        </div>

        {/* Navigation Links */}
        <div className="sidebar-section-label">Clinical Workspace</div>
        <nav className="nav-list" aria-label="Primary clinical navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const active = page === item.id
            return (
              <button
                key={item.id}
                type="button"
                className={`nav-btn ${active ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        {/* Live Engine Status */}
        <div className="engine-status-card">
          <div style={{ fontWeight: 700, color: '#93c5fd', marginBottom: '0.35rem', fontSize: '0.72rem' }}>
            SYSTEM TELEMETRY
          </div>
          <div className="status-row">
            <span><span className="dot dot-green" /> E1 Screening RF+Stack</span>
            <span>ONLINE</span>
          </div>
          <div className="status-row">
            <span><span className="dot dot-green" /> E2 KDIGO 2024 Staging</span>
            <span>ONLINE</span>
          </div>
          <div className="status-row">
            <span><span className="dot dot-green" /> E3 KFRE &amp; Trajectory</span>
            <span>ONLINE</span>
          </div>
          <div className="status-row">
            <span><span className="dot dot-amber" /> Survival ML</span>
            <span>DEFERRED</span>
          </div>
        </div>
      </aside>

      {/* Main Pane */}
      <main className="main-pane">
        <header className="topbar">
          <div>
            <h1>NEFROAI-X &mdash; Chronic Kidney Disease Screening &amp; XAI</h1>
            <div className="topbar-sub">
              Full-Stack FastAPI + React Clinical Decision Support Platform (Screening, KDIGO Staging, Longitudinal Trajectory)
            </div>
          </div>
          <div className="pill-bar">
            <span className="pill pill-navy">RESEARCH PROTOTYPE</span>
            <span className={`pill ${health?.cloud_postgres_connected ? 'pill-green' : 'pill-blue'}`}>
              <ShieldCheck size={13} /> {storageLabel}
            </span>
            <span className="pill pill-amber">SURVIVAL ML: DEFERRED</span>
          </div>
        </header>

        <div className="disclaimer-banner" role="note">
          <AlertTriangle size={17} style={{ flexShrink: 0 }} />
          <span>
            MANDATORY CLINICAL NOTICE: Research Decision Support Prototype — Not clinically validated for standalone medical diagnosis.
            All automated CKD estimates require board-certified physician adjudication.
          </span>
        </div>

        {page === 'overview' && (
          <OverviewPage
            health={health}
            user={user}
            onNavigate={setPage}
            onOpenAuth={setAuthModalMode}
          />
        )}

        {page === 'assessment' && (
          <AssessmentPage
            presets={presets}
            formState={formState}
            setFormState={setFormState}
            assessment={assessment}
            setAssessment={setAssessment}
            user={user}
            onNavigate={setPage}
            onVaultUpdated={() => setVaultRefreshKey((k) => k + 1)}
          />
        )}

        {page === 'explainability' && (
          <ExplainabilityPage formState={formState} onNavigate={setPage} />
        )}

        {page === 'performance' && <PerformancePage />}

        {page === 'vault' && (
          <VaultPage
            user={user}
            storageBackend={health?.storage_backend}
            activeAssessment={assessment}
            onOpenAuth={setAuthModalMode}
            onLoadPatientVisits={handleLoadPatientVisits}
            vaultRefreshKey={vaultRefreshKey}
          />
        )}

        {page === 'progression' && <ProgressionGuidePage onNavigate={setPage} />}

        {page === 'governance' && <GovernanceGuidePage health={health} />}
      </main>

      {authModalMode && (
        <AuthModal
          initialMode={authModalMode}
          storageBackend={health?.storage_backend}
          onClose={() => setAuthModalMode(null)}
          onSuccess={(loggedUser, backendName) => {
            setUser(loggedUser)
            if (backendName) {
              setHealth((h) => (h ? { ...h, storage_backend: backendName, cloud_postgres_connected: backendName === 'postgresql' } : h))
            }
            setVaultRefreshKey((k) => k + 1)
            setAuthModalMode(null)
          }}
        />
      )}
    </div>
  )
}

