const TOKEN_KEY = 'nefroai_bearer_token'

export function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setStoredToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Ignore storage quota errors cleanly
  }
}

async function apiFetch(path, options = {}) {
  const token = getStoredToken()
  const headers = new Headers(options.headers || {})
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const resp = await fetch(path, { ...options, headers })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const err = await resp.json()
      detail = err.detail || err.message || detail
    } catch {
      const txt = await resp.text()
      if (txt) detail = txt.slice(0, 240)
    }
    throw new Error(detail)
  }
  const contentType = resp.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return resp.json()
  }
  return resp
}

export const api = {
  health: () => apiFetch('/api/health'),
  presets: () => apiFetch('/api/presets'),
  signup: (payload) => apiFetch('/api/auth/signup', { method: 'POST', body: JSON.stringify(payload) }),
  signin: (payload) => apiFetch('/api/auth/signin', { method: 'POST', body: JSON.stringify(payload) }),
  me: () => apiFetch('/api/auth/me'),
  assess: (payload) => apiFetch('/api/assess', { method: 'POST', body: JSON.stringify(payload) }),
  explain: (payload) => apiFetch('/api/explain', { method: 'POST', body: JSON.stringify(payload) }),
  sampleBatchCsv: () => apiFetch('/api/sample-batch-csv'),
  batchScreen: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return apiFetch('/api/batch-screen', { method: 'POST', body: fd })
  },
  performance: () => apiFetch('/api/performance'),
  history: (patientId = '') => {
    const q = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : ''
    return apiFetch(`/api/history${q}`)
  },
  historyDetail: (assessmentId) => apiFetch(`/api/history/${encodeURIComponent(assessmentId)}`),
  patientVisits: (patientId) => apiFetch(`/api/history/visits/${encodeURIComponent(patientId)}`),
  verifyAttestation: (payload) => apiFetch('/api/verify-attestation', { method: 'POST', body: JSON.stringify(payload) }),
  async downloadReport(format, responsePayload, visits = []) {
    const resp = await apiFetch('/api/reports/export', {
      method: 'POST',
      body: JSON.stringify({ format, response: responsePayload, visits }),
    })
    const blob = await resp.blob()
    const extMap = { pdf: 'pdf', csv: 'csv', json: 'json', txt: 'txt' }
    const pid = (responsePayload?.patient_id || 'PATIENT').replace(/[^A-Za-z0-9._-]/g, '_')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `nefroai_${pid}_report.${extMap[format] || 'txt'}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}

