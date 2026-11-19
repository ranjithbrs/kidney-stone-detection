import React from 'react'
import {
  Activity,
  BarChart2,
  BookOpen,
  ClipboardPlus,
  Database,
  Home,
  LogOut,
  Sliders,
  TrendingUp,
  User,
} from 'lucide-react'

const CLINICAL_WORKSPACE_NAV = [
  { id: 'overview', label: 'System Overview', icon: Home },
  { id: 'screening', label: 'CKD Screening & Labs', icon: ClipboardPlus },
  { id: 'xai', label: 'Live XAI & What-If', icon: Sliders },
  { id: 'benchmarks', label: 'Benchmark & Calibration', icon: BarChart2 },
  { id: 'vault', label: 'Cloud Vault & Audit', icon: Database },
  { id: 'methodology', label: 'Progression Methodology', icon: TrendingUp },
  { id: 'governance', label: 'Clinical Governance', icon: BookOpen },
]

export default function SidebarNav({
  activePage,
  onNavigate,
  user,
  onOpenAuth,
  onSignOut,
}) {
  const initials = user?.full_name
    ? user.full_name
        .split(/\s+/)
        .slice(0, 2)
        .map((w) => w[0]?.toUpperCase() || '')
        .join('')
    : 'DR'

  return (
    <aside className="sidebar-dark" aria-label="Primary clinical navigation">
      <div className="sidebar-top">
        {/* Brand Lockup */}
        <div className="sidebar-brand-box">
          <div className="sidebar-brand-title">NEFROAI-X</div>
          <div className="sidebar-brand-sub">Explainable Renal CDSS • Research SaaS</div>
        </div>

        {/* Clinician Session Box */}
        <div className="sidebar-session-card">
          <div className="sidebar-section-title">CLINICIAN SESSION</div>
          {user ? (
            <div style={{ marginTop: '0.45rem' }}>
              <div className="sidebar-user-row">
                <span className="user-avatar-dark">{initials}</span>
                <div style={{ minWidth: 0 }}>
                  <div className="user-name-dark">{user.full_name}</div>
                  <div className="user-role-dark">{user.role || 'Nephrologist'}</div>
                </div>
              </div>
              <button
                type="button"
                className="btn-sidebar-secondary"
                onClick={onSignOut}
                style={{ width: '100%', marginTop: '0.45rem' }}
              >
                <LogOut size={12} /> Sign out
              </button>
            </div>
          ) : (
            <div style={{ marginTop: '0.35rem' }}>
              <div className="sidebar-guest-notice">
                Guest Clinician Session Active
              </div>
              <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.45rem' }}>
                <button
                  type="button"
                  className="btn-sidebar-primary"
                  onClick={() => onOpenAuth('signin')}
                  style={{ flex: 1 }}
                >
                  <User size={12} /> Sign In
                </button>
                <button
                  type="button"
                  className="btn-sidebar-secondary"
                  onClick={() => onOpenAuth('signup')}
                  style={{ flex: 1 }}
                >
                  Register
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Clinical Workspace Navigation */}
        <div>
          <div className="sidebar-section-title">CLINICAL WORKSPACE</div>
          <nav className="sidebar-nav-list" style={{ marginTop: '0.4rem' }}>
            {CLINICAL_WORKSPACE_NAV.map((item) => {
              const Icon = item.icon
              const isActive = activePage === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`sidebar-nav-btn ${isActive ? 'active' : ''}`}
                  onClick={() => onNavigate(item.id)}
                >
                  <Icon size={15} />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Telemetry Block at Bottom */}
      <div className="sidebar-telemetry-box">
        <div className="sidebar-telemetry-title">SYSTEM TELEMETRY</div>
        <div className="telemetry-row">
          <span>● E1 Screening ML</span>
          <span className="telemetry-online">ONLINE</span>
        </div>
        <div className="telemetry-row">
          <span>● E2 KDIGO Staging</span>
          <span className="telemetry-online">ONLINE</span>
        </div>
        <div className="telemetry-row">
          <span>● E3 KFRE Risk</span>
          <span className="telemetry-online">ONLINE</span>
        </div>
      </div>
    </aside>
  )
}
