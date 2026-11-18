import React, { useEffect, useState } from 'react'
import { api, getStoredToken, setStoredToken } from './api'
import SidebarNav from './components/SidebarNav'
import PatientsPage from './components/PatientsPage'
import AssessmentPage from './components/AssessmentPage'
import PatientChartPage from './components/PatientChartPage'
import BatchPage from './components/BatchPage'
import ModelAuditPage from './components/ModelAuditPage'
import AuthModal from './components/AuthModal'

function createEmptyFormState() {
  return {
    patient_id: '',
    age: '',
    sex: 'male',
    observation_date: new Date().toISOString().slice(0, 10),
    serum_creatinine: '',
    serum_creatinine_unit: 'mg/dL',
    uacr: '',
    uacr_unit: 'mg/g',
    biomarkers: {
      hemo: '',
      sg: '',
      pcv: '',
      rc: '',
      al: '',
      sc: '',
      bu: '',
      bgr: '',
      htn: 'no',
      dm: 'no',
    },
    visits: [],
  }
}

export default function App() {
  const [activePage, setActivePage] = useState('patients')
  const [health, setHealth] = useState(null)
  const [user, setUser] = useState(null)
  const [authModalMode, setAuthModalMode] = useState(null)
  const [formState, setFormState] = useState(createEmptyFormState)
  const [assessment, setAssessment] = useState(null)
  const [vaultRefreshKey, setVaultRefreshKey] = useState(0)
  const [globalError, setGlobalError] = useState('')

  useEffect(() => {
    let mounted = true
    async function init() {
      try {
        const h = await api.health()
        if (!mounted) return
        setHealth(h)
      } catch (err) {
        if (mounted) setGlobalError(err.message || 'Unable to connect to clinical backend.')
      }

      if (getStoredToken()) {
        try {
          const me = await api.me()
          if (mounted && me?.user) setUser(me.user)
        } catch {
          setStoredToken('')
        }
      }
    }
    init()
    return () => {
      mounted = false
    }
  }, [])

  function handleSignedIn(nextUser, storageBackend) {
    setUser(nextUser)
    if (storageBackend) {
      setHealth((prev) => (prev ? { ...prev, storage_backend: storageBackend } : prev))
    }
    setVaultRefreshKey((k) => k + 1)
  }

  async function handleOpenVaultPatient(patientId, assessmentId) {
    setGlobalError('')
    try {
      const [detail, visitRes] = await Promise.all([
        api.historyDetail(assessmentId),
        api.patientVisits(patientId).catch(() => ({ visits: [] })),
      ])
      const payload = detail?.payload
      if (!payload) {
        throw new Error('Saved assessment payload was empty.')
      }

      const rawBiomarkers = payload.biomarkers || payload.input_biomarkers || {}
      const e2 = payload.engine2_result || {}
      const restoredForm = {
        patient_id: payload.patient_id || patientId,
        age: payload.age ?? '',
        sex: payload.sex || 'male',
        observation_date: String(payload.observation_date || new Date().toISOString().slice(0, 10)).slice(0, 10),
        serum_creatinine: rawBiomarkers.sc ?? '',
        serum_creatinine_unit: 'mg/dL',
        uacr: e2.uacr ?? '',
        uacr_unit: 'mg/g',
        biomarkers: {
          hemo: rawBiomarkers.hemo ?? '',
          sg: rawBiomarkers.sg ?? '',
          pcv: rawBiomarkers.pcv ?? '',
          rc: rawBiomarkers.rc ?? '',
          al: rawBiomarkers.al ?? '',
          sc: rawBiomarkers.sc ?? '',
          bu: rawBiomarkers.bu ?? '',
          bgr: rawBiomarkers.bgr ?? '',
          htn: rawBiomarkers.htn || 'no',
          dm: rawBiomarkers.dm || 'no',
        },
        visits: Array.isArray(visitRes?.visits) ? visitRes.visits : [],
      }

      setFormState(restoredForm)
      setAssessment(payload)
      setActivePage('chart')
    } catch (err) {
      setGlobalError(err.message || 'Could not load saved patient record.')
    }
  }

  function handleSignOut() {
    setStoredToken('')
    setUser(null)
  }

  return (
    <div className="shell-layout">
      <SidebarNav
        activePage={activePage}
        hasActivePatient={Boolean(assessment)}
        onNavigate={setActivePage}
        user={user}
        onOpenAuth={(mode) => setAuthModalMode(mode)}
        onSignOut={handleSignOut}
      />

      <div className="main-col">
        <main className="page-main">
          {globalError && (
            <div className="notice notice-danger" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{globalError}</span>
              <button type="button" className="btn btn-sm" onClick={() => setGlobalError('')}>
                Dismiss
              </button>
            </div>
          )}

          {activePage === 'patients' && (
            <PatientsPage
              user={user}
              vaultRefreshKey={vaultRefreshKey}
              onNewScreening={() => setActivePage('screening')}
              onOpenBatchScreening={() => setActivePage('batch')}
              onOpenVaultPatient={handleOpenVaultPatient}
              onOpenAuth={(mode) => setAuthModalMode(mode)}
              onSignedIn={handleSignedIn}
            />
          )}

          {activePage === 'screening' && (
            <AssessmentPage
              formState={formState}
              setFormState={setFormState}
              assessment={assessment}
              setAssessment={setAssessment}
              user={user}
              onOpenChart={() => setActivePage('chart')}
              onVaultUpdated={() => setVaultRefreshKey((k) => k + 1)}
            />
          )}

          {activePage === 'chart' && (
            <PatientChartPage
              patientId={formState.patient_id}
              formState={formState}
              setFormState={setFormState}
              assessment={assessment}
              setAssessment={setAssessment}
              user={user}
              onNavigateToScreening={() => setActivePage('screening')}
              onVaultUpdated={() => setVaultRefreshKey((k) => k + 1)}
            />
          )}

          {activePage === 'batch' && <BatchPage />}

          {activePage === 'audit' && (
            <ModelAuditPage
              user={user}
              health={health}
              formState={formState}
              onOpenAuth={(mode) => setAuthModalMode(mode)}
            />
          )}
        </main>

        <footer className="app-footer">
          <div className="app-footer-inner">
            <span>
              NEFROAI-X Clinical Decision Support · Screening aid only; confirm all clinical decisions with a nephrologist.
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ padding: '0.1rem 0.4rem', fontSize: '0.76rem' }}
              onClick={() => setActivePage('audit')}
            >
              Validation &amp; Audit
            </button>
          </div>
        </footer>
      </div>

      {authModalMode && (
        <AuthModal
          initialMode={authModalMode}
          storageBackend={health?.storage_backend}
          onClose={() => setAuthModalMode(null)}
          onSuccess={(nextUser, storageBackend) => {
            handleSignedIn(nextUser, storageBackend)
            setAuthModalMode(null)
          }}
        />
      )}
    </div>
  )
}
