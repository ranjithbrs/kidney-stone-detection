import React from 'react'
import {
  Activity,
  ClipboardPlus,
  FileSpreadsheet,
  LogOut,
  ShieldCheck,
  User,
  Users,
} from 'lucide-react'

const CLINICAL_NAV = [
  { id: 'patients', label: 'Patients', icon: Users },
  { id: 'screening', label: 'New Screening', icon: ClipboardPlus },
  { id: 'chart', label: 'Patient Chart', icon: Activity },
  { id: 'batch', label: 'Batch Screening', icon: FileSpreadsheet },
]

export default function SidebarNav({
  activePage,
  hasActivePatient,
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
    <aside className="sidebar" aria-label="Primary clinical navigation">
      <div className="sidebar-top">
        <button type="button" className="brand-lockup" onClick={() => onNavigate('patients')}>
          <span className="brand-mark">N</span>
          <span>
            <span className="brand-name">NEFROAI-X</span>
            <span className="brand-env">Renal Diagnostics</span>
          </span>
        </button>

        <div>
          <div className="sidebar-section-label">Clinical Workflow</div>
          <nav className="sidebar-nav">
            {CLINICAL_NAV.map((item) => {
              const Icon = item.icon
              const isActive = activePage === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`sidebar-item ${isActive ? 'active' : ''}`}
                  onClick={() => onNavigate(item.id)}
                >
                  <span className="sidebar-item-left">
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </span>
                  {item.id === 'chart' && hasActivePatient && (
                    <span
                      style={{
                        width: 7,
                        height: 7,
                        borderRadius: 999,
                        background: 'var(--accent)',
                        flexShrink: 0,
                      }}
                      title="Active patient loaded"
                    />
                  )}
                </button>
              )
            })}
          </nav>
        </div>

        <div>
          <div className="sidebar-section-label">Quality &amp; Audit</div>
          <nav className="sidebar-nav">
            <button
              type="button"
              className={`sidebar-item ${activePage === 'audit' ? 'active' : ''}`}
              onClick={() => onNavigate('audit')}
            >
              <span className="sidebar-item-left">
                <ShieldCheck size={16} />
                <span>Validation &amp; Audit</span>
              </span>
            </button>
          </nav>
        </div>
      </div>

      <div className="sidebar-footer">
        {user ? (
          <>
            <div className="user-chip" title={`${user.full_name} (${user.role || 'Clinician'})`}>
              <span className="user-avatar">{initials}</span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {user.full_name}
                </div>
                <div style={{ fontSize: '0.71rem', color: 'var(--muted)' }}>
                  {user.role || 'Nephrology'}
                </div>
              </div>
            </div>
            <button type="button" className="btn btn-sm" onClick={onSignOut} style={{ width: '100%' }}>
              <LogOut size={13} /> Sign out
            </button>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <button type="button" className="btn btn-sm btn-primary" onClick={() => onOpenAuth('signin')} style={{ width: '100%' }}>
              <User size={13} /> Clinician sign in
            </button>
            <button type="button" className="btn btn-sm" onClick={() => onOpenAuth('signup')} style={{ width: '100%' }}>
              Create account
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
