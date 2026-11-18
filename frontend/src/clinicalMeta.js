export const BIOMARKER_META = {
  sc: {
    label: 'Serum Creatinine',
    unit: 'mg/dL',
    normalLow: 0.7,
    normalHigh: 1.3,
    scaleMin: 0.3,
    scaleMax: 5.0,
  },
  hemo: {
    label: 'Hemoglobin',
    unit: 'g/dL',
    normalLow: 12.0,
    normalHigh: 17.5,
    scaleMin: 6.0,
    scaleMax: 18.5,
  },
  pcv: {
    label: 'Hematocrit (PCV)',
    unit: '%',
    normalLow: 36,
    normalHigh: 50,
    scaleMin: 18,
    scaleMax: 55,
  },
  rc: {
    label: 'Red Blood Cell Count',
    unit: 'M/mcL',
    normalLow: 4.2,
    normalHigh: 5.9,
    scaleMin: 2.2,
    scaleMax: 6.5,
  },
  sg: {
    label: 'Urine Specific Gravity',
    unit: '',
    normalLow: 1.01,
    normalHigh: 1.025,
    scaleMin: 1.005,
    scaleMax: 1.03,
  },
  bu: {
    label: 'Blood Urea',
    unit: 'mg/dL',
    normalLow: 15,
    normalHigh: 40,
    scaleMin: 5,
    scaleMax: 140,
  },
  bgr: {
    label: 'Random Blood Glucose',
    unit: 'mg/dL',
    normalLow: 70,
    normalHigh: 140,
    scaleMin: 50,
    scaleMax: 320,
  },
  al: {
    label: 'Urine Albumin Dipstick',
    unit: 'grade',
    normalLow: 0,
    normalHigh: 0,
    scaleMin: 0,
    scaleMax: 5,
  },
  htn: { label: 'Hypertension History' },
  dm: { label: 'Diabetes Mellitus History' },
}

export function formatBiomarkerName(key) {
  return BIOMARKER_META[key]?.label || key
}

function prettifyEnum(val, fallback = 'Evaluated') {
  const s = String(val || '').trim()
  if (!s) return fallback
  return s
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

const TRIAGE_LABELS = {
  NEPHROLOGY_REFERRAL_PRIORITY: 'Urgent Nephrology Referral',
  CRITICAL_CKD_ALERT: 'Critical Risk Escalation',
  HIGH_RISK_CKD: 'High-Risk Follow-up',
  SPECIMEN_VERIFICATION_REDRAW: 'Repeat Lab / Redraw Required',
  PRE_INFERENCE_COHERENCE_PRIORITY: 'Lab Verification Required',
  CONFIRMATORY_WORKUP_RECOMMENDED: 'Confirmatory Repeat Lab',
  CONFORMAL_REVIEW_REQUIRED: 'Clinician Review Required',
  ABSTAIN_CLINICAL_REVIEW: 'Incomplete Panel — Review',
  MODERATE_RISK_MONITORING: 'Moderate Risk — Monitor',
  ROUTINE_MONITORING: 'Routine Follow-up',
  LOW_RISK_ROUTINE: 'Routine Follow-up',
}

export function formatTriageTier(tier) {
  const key = String(tier || '').trim().toUpperCase()
  if (!key) return 'Evaluated'
  return TRIAGE_LABELS[key] || prettifyEnum(tier)
}

const RULE_LABELS = {
  SAFETY_MAX_CRITICAL_ESCALATION: 'Safety Escalation Rule',
  PRE_INFERENCE_COHERENCE_PRIORITY: 'Lab Consistency Guard',
  DISCREPANCY_ESCALATION: 'Clinical Discordance Check',
  CONFORMAL_ABSTENTION: 'Uncertainty Abstention',
  STANDARD: 'Standard Triage',
}

export function formatRuleName(rule) {
  const key = String(rule || '').trim().toUpperCase()
  if (!key) return 'Standard Triage'
  return RULE_LABELS[key] || prettifyEnum(rule)
}

export function formatCoherenceStatus(status) {
  const key = String(status || '').trim().toUpperCase()
  if (key === 'COHERENT') return 'Labs Consistent'
  if (key.includes('CONTRADICTION') || key.includes('INCOHERENT') || key.includes('DISCORD')) {
    return 'Lab Discordance Flagged'
  }
  return key ? prettifyEnum(key) : 'Verified'
}

export function formatChronicityLabel(cgaOrText) {
  const raw = String(cgaOrText || '').toUpperCase()
  if (!raw) return 'Pending'
  if (raw.includes('UNAVAILABLE_CROSS_SECTIONAL')) return 'Single visit (chronicity pending)'
  if (raw.includes('CONFIRMED_CHRONIC') || raw.includes('CHRONIC_CONFIRMED')) return 'Confirmed Chronic (≥90 days)'
  if (raw.includes('AKI') || raw.includes('ACUTE')) return 'Acute Elevation Flagged'
  if (raw.includes('SINGLE_VISIT')) return 'Single visit'
  return prettifyEnum(cgaOrText)
}

export function formatCgaStage(gCat, aCat, cgaFallback) {
  if (gCat && aCat) return `Stage ${gCat} · ${aCat}`
  if (gCat) return `Stage ${gCat}`
  if (cgaFallback && !String(cgaFallback).includes('UNAVAILABLE')) return String(cgaFallback)
  return 'Unstaged'
}

export function formatConcordanceStatus(status) {
  const key = String(status || '').trim().toUpperCase()
  if (key === 'HIGH_CONCORDANCE') return 'Strong Agreement'
  if (key === 'MODERATE_CONCORDANCE') return 'Moderate Agreement'
  if (key === 'LOW_CONCORDANCE') return 'Low Agreement'
  return prettifyEnum(status, 'Checked')
}

export function formatGateDecision(decision) {
  const key = String(decision || '').trim().toUpperCase()
  if (!key) return 'Evaluated'
  if (key === 'PASS' || key === 'DECISIVE') return 'Confident Prediction'
  if (key.includes('ABSTAIN')) return 'Held for Clinician Review'
  return prettifyEnum(decision)
}

/**
 * Race-free CKD-EPI 2021 serum creatinine eGFR equation for longitudinal chart plotting.
 */
export function computeCkdepi2021Egfr(scrMgDl, age, sex) {
  const scr = Number(scrMgDl)
  const a = Number(age)
  if (!Number.isFinite(scr) || scr <= 0 || !Number.isFinite(a) || a <= 0) return null
  const isFemale = String(sex || '').toLowerCase().startsWith('f')
  const kappa = isFemale ? 0.7 : 0.9
  const alpha = isFemale ? -0.241 : -0.302
  const sexFactor = isFemale ? 1.012 : 1.0
  const ratio = scr / kappa
  return (
    142 *
    Math.pow(Math.min(ratio, 1), alpha) *
    Math.pow(Math.max(ratio, 1), -1.2) *
    Math.pow(0.9938, a) *
    sexFactor
  )
}

export function getTierBadgeClass(tier) {
  const t = String(tier || '').toLowerCase()
  if (
    t.includes('immediate') ||
    t.includes('critical') ||
    t.includes('high') ||
    t.includes('referral') ||
    t.includes('escalation') ||
    t.includes('priority')
  ) {
    return 'badge-danger'
  }
  if (
    t.includes('confirm') ||
    t.includes('abstain') ||
    t.includes('review') ||
    t.includes('moderate') ||
    t.includes('monitor') ||
    t.includes('redraw')
  ) {
    return 'badge-warn'
  }
  if (t.includes('low') || t.includes('routine') || t.includes('stable') || t.includes('normal')) {
    return 'badge-ok'
  }
  return 'badge-neutral'
}

export function formatStageCareGuidance(egfrCategory, albCategory) {
  const g = String(egfrCategory || '').toUpperCase()
  const a = String(albCategory || '').toUpperCase()
  const notes = []

  if (g === 'G4' || g === 'G5') {
    notes.push('Prioritize nephrology consultation for renal replacement planning and medication dose adjustments.')
    notes.push('Monitor serum potassium, bicarbonate, calcium/phosphorus, and fluid balance closely.')
  } else if (g === 'G3A' || g === 'G3B') {
    notes.push('Schedule nephrology co-management review; monitor eGFR and urine ACR every 3–6 months.')
    notes.push('Screen for renal anemia (hemoglobin/iron) and avoid nephrotoxic NSAIDs when alternatives exist.')
  } else if (g === 'G1' || g === 'G2') {
    if (a === 'A2' || a === 'A3') {
      notes.push('Preserved filtration with elevated albuminuria — verify repeat uACR and optimize blood pressure and glycemic control.')
    } else {
      notes.push('Kidney filtration markers are within preserved range; continue routine preventive follow-up.')
    }
  } else {
    notes.push('Complete serum creatinine and spot urine ACR measurements to establish formal KDIGO staging.')
  }

  if (a === 'A3') {
    notes.push('Severe albuminuria (>300 mg/g): evaluate antiproteinuric therapy eligibility and strict blood pressure targets.')
  } else if (a === 'A2') {
    notes.push('Moderate albuminuria (30–300 mg/g): confirm persistence over 90 days and review cardiovascular risk factors.')
  }

  return notes
}
