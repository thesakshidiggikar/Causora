import { StrictMode, useEffect, useState, type FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = 'http://localhost:8000/api/v1'
type Service = { id: string; name: string; description?: string }
type Snapshot = { id: string; service_id: string; format: string; created_at: string; content_hash: string; document: Record<string, unknown> }

async function api<T>(path: string, token?: string, payload?: unknown): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: payload === undefined ? 'GET' : 'POST',
    headers: {
      ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  })
  const body = await response.json()
  if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status}).`)
  return body as T
}

function App() {
  const [token, setToken] = useState<string>()
  const [authMode, setAuthMode] = useState<'register' | 'login'>('register')
  const [services, setServices] = useState<Service[]>([])
  const [serviceId, setServiceId] = useState('')
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [notice, setNotice] = useState('Create a workspace to save configuration snapshots and analysis history.')
  const [savedResult, setSavedResult] = useState('Saved snapshot comparison will appear here.')
  const [statelessResult, setStatelessResult] = useState('Your assessment will appear here.')
  const [impactResult, setImpactResult] = useState('Reachable downstream services and paths will appear here.')

  async function loadServices(accessToken: string) {
    try {
      const result = await api<Service[]>('/services', accessToken)
      setServices(result)
      if (result.length && !result.some(item => item.id === serviceId)) setServiceId(result[0].id)
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load services.') }
  }

  async function loadSnapshots(accessToken: string, id: string) {
    if (!id) { setSnapshots([]); return }
    try { setSnapshots(await api<Snapshot[]>(`/snapshots?service_id=${encodeURIComponent(id)}`, accessToken)) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load snapshots.') }
  }

  useEffect(() => { if (token) void loadServices(token) }, [token])
  useEffect(() => { if (token && serviceId) void loadSnapshots(token, serviceId) }, [token, serviceId])

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const payload = authMode === 'register'
      ? { organization_name: data.get('organization'), email: data.get('email'), password: data.get('password') }
      : { email: data.get('email'), password: data.get('password') }
    try {
      const result = await api<{ access_token: string }>(`/auth/${authMode}`, undefined, payload)
      setToken(result.access_token)
      setNotice(authMode === 'register' ? 'Workspace created. Add a service to continue.' : 'Signed in.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Authentication failed.') }
  }

  async function createService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token) return
    const form = event.currentTarget
    const data = new FormData(form)
    try {
      const service = await api<Service>('/services', token, { name: data.get('name'), description: data.get('description') || null })
      setServices(previous => [...previous, service].sort((a, b) => a.name.localeCompare(b.name)))
      setServiceId(service.id)
      setNotice(`Service �${service.name}� added.`)
      form.reset()
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not create service.') }
  }

  async function createDependency(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token) return
    const data = new FormData(event.currentTarget)
    try {
      await api('/dependencies', token, { source_id: data.get('source'), target_id: data.get('target') })
      setNotice('Dependency saved. Snapshot simulations now trace downstream services.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not save dependency.') }
  }

  async function saveSnapshots(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !serviceId) return
    const data = new FormData(event.currentTarget)
    try {
      await api<Snapshot>('/snapshots', token, { service_id: serviceId, format: data.get('format'), document: data.get('before') })
      await api<Snapshot>('/snapshots', token, { service_id: serviceId, format: data.get('format'), document: data.get('after') })
      await loadSnapshots(token, serviceId)
      setNotice('Both immutable snapshots were saved. Secret-like values are redacted at rest.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not save snapshots.') }
  }

  async function compareSaved(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token) return
    const data = new FormData(event.currentTarget)
    setSavedResult('Comparing stored snapshots�')
    try {
      const result = await api<unknown>('/analysis-runs/simulate', token, {
        before_snapshot_id: data.get('before-id'), after_snapshot_id: data.get('after-id'),
        context: { max_replicas: Number(data.get('max-replicas')), database_max_connections: Number(data.get('db-max-connections')), database_safety_margin: Number(data.get('safety-margin')) },
      })
      setSavedResult(JSON.stringify(result, null, 2))
    } catch (error) { setSavedResult(error instanceof Error ? error.message : 'Comparison failed.') }
  }

  async function fetchAudit() {
    if (!token) return
    try { setSavedResult(JSON.stringify(await api('/audit-events', token), null, 2)) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load the audit trail.') }
  }

  async function analyzeChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setStatelessResult('Analyzing�')
    try {
      setStatelessResult(JSON.stringify(await api('/analyses', undefined, {
        changes: [{ service: data.get('service'), key: data.get('key'), before: data.get('before'), after: data.get('after') }],
      }), null, 2))
    } catch (error) { setStatelessResult(error instanceof Error ? error.message : 'Analysis failed.') }
  }

  async function analyzeImpact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    try {
      setImpactResult(JSON.stringify(await api('/impact', undefined, {
        services: String(data.get('services')).split(',').map(value => value.trim()).filter(Boolean),
        changed_services: String(data.get('changed-services')).split(',').map(value => value.trim()).filter(Boolean),
        dependencies: JSON.parse(String(data.get('dependencies'))),
      }), null, 2))
    } catch (error) { setImpactResult(error instanceof Error ? error.message : 'Dependencies must be valid JSON.') }
  }

  return <main className="shell">
    <aside className="rail"><div className="mark">C</div><div className="rail-icon active">?</div><div className="rail-icon">?</div><div className="rail-icon">?</div><div className="rail-bottom">?</div></aside>
    <section className="page">
      <header><div className="brand"><span className="eyebrow">OPERATIONS INTELLIGENCE</span><h1>Causora<span className="dot">.</span></h1></div><div className="user"><span className="pulse"></span> LOCAL PREVIEW <b>SD</b></div></header>
      <div className="intro"><div><div className="eyebrow">CHANGE INTELLIGENCE / OVERVIEW</div><h2>Know what a change could break.</h2><p>Trace configuration changes into operational risk before they reach production.</p></div><button onClick={() => document.getElementById('workspace')?.scrollIntoView({ behavior: 'smooth' })}>+ &nbsp; New analysis</button></div>
      <div className="notice"><span>i</span><div><strong>Explainable analysis</strong><small>Rule-based evidence and structural reachability. No cloud account is connected.</small></div><span className="tag">LOCAL</span></div>
      <div className="stats"><article><label>SERVICES IN WORKSPACE</label><strong>{services.length || '�'}</strong><small>{token ? 'Tenant-scoped inventory' : 'Sign in to view inventory'}</small></article><article><label>SAVED SNAPSHOTS</label><strong>{snapshots.length || '�'}</strong><small>{token ? 'Redacted at rest' : 'Create a workspace'}</small></article><article><label>ANALYSIS HISTORY</label><strong>?</strong><small>{token ? 'Saved to tenant history' : 'Sign in to save analyses'}</small></article></div>
      <section className="panel" id="workspace"><div className="panel-head"><div><div className="eyebrow">TENANT WORKSPACE</div><h3>{token ? 'Your services and configuration history' : 'Create or access a workspace'}</h3></div>{token && <button className="secondary" onClick={() => { setToken(undefined); setServices([]); setSnapshots([]); setNotice('Signed out.') }}>Sign out</button>}</div>
        {!token ? <><div className="mode-switch"><button className={authMode === 'register' ? 'selected' : ''} onClick={() => setAuthMode('register')}>Create workspace</button><button className={authMode === 'login' ? 'selected' : ''} onClick={() => setAuthMode('login')}>Sign in</button></div><form onSubmit={authenticate}><div className="form-grid">{authMode === 'register' && <label>Organization<input name="organization" placeholder="e.g. Northstar Engineering" minLength={2} maxLength={120} required/></label>}<label>Email<input name="email" type="email" autoComplete="email" required/></label><label>Password (12+ characters)<input name="password" type="password" autoComplete={authMode === 'register' ? 'new-password' : 'current-password'} minLength={authMode === 'register' ? 12 : 1} maxLength={256} required/></label></div><div className="form-actions"><small>Workspace data is isolated by organization.</small><button type="submit">{authMode === 'register' ? 'Create workspace' : 'Sign in'} <span>?</span></button></div></form></> : <>
          <div className="workspace-message">{notice}</div><form className="service-form" onSubmit={createService}><div className="form-grid"><label>Service name<input name="name" placeholder="e.g. checkout-api" maxLength={100} required/></label><label>Description<input name="description" placeholder="Optional owner or purpose" maxLength={500}/></label></div><div className="form-actions"><small>Each service belongs to your organization.</small><button type="submit">Add service <span>+</span></button></div></form>
          {services.length > 0 && <><label className="service-select">Selected service<select value={serviceId} onChange={event => setServiceId(event.target.value)}>{services.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label><form className="service-form" onSubmit={createDependency}><div className="form-grid"><label>Upstream service<select name="source" required>{services.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label><label>Downstream dependent service<select name="target" required>{services.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label></div><div className="form-actions"><small>Edges mean a downstream service depends on the upstream service.</small><button type="submit">Save dependency <span>?</span></button></div></form><form onSubmit={saveSnapshots}><div className="eyebrow form-eyebrow">SAVE A BEFORE / AFTER PAIR</div><div className="form-grid"><label>Format<select name="format"><option value="yaml">YAML</option><option value="json">JSON</option></select></label><label>Before configuration<textarea name="before" placeholder={'database:\n  pool_size: 20\n  password: example'} required/></label><label>After configuration<textarea name="after" placeholder={'database:\n  pool_size: 40\n  password: changed'} required/></label></div><div className="form-actions"><small>Raw secret values are never stored. Comparisons use keyed fingerprints.</small><button type="submit">Save snapshots <span>?</span></button></div></form>
          {snapshots.length >= 2 && <form className="compare-form" onSubmit={compareSaved}><div className="form-grid"><label>Before snapshot<select name="before-id" defaultValue={snapshots[1]?.id} required>{snapshots.map((snapshot, index) => <option key={snapshot.id} value={snapshot.id}>{new Date(snapshot.created_at).toLocaleString()} � {snapshot.content_hash.slice(0, 8)}{index === snapshots.length - 1 ? ' (latest)' : ''}</option>)}</select></label><label>After snapshot<select name="after-id" defaultValue={snapshots[0]?.id} required>{snapshots.map((snapshot, index) => <option key={snapshot.id} value={snapshot.id}>{new Date(snapshot.created_at).toLocaleString()} � {snapshot.content_hash.slice(0, 8)}{index === 0 ? ' (latest)' : ''}</option>)}</select></label><label>Maximum replicas<input name="max-replicas" type="number" min="1" defaultValue="10" required/></label><label>Database max connections<input name="db-max-connections" type="number" min="1" defaultValue="1000" required/></label><label>Capacity safety margin<input name="safety-margin" type="number" min="0" max="0.89" step="0.01" defaultValue="0.1" required/></label></div><div className="form-actions"><small>Findings, assumptions, and downstream impact paths are saved in your workspace.</small><button type="submit">Compare saved versions <span>?</span></button></div></form>}
          <div className="form-actions audit-actions"><small>{snapshots.length} saved version(s) for this service.</small><button type="button" className="secondary" onClick={fetchAudit}>View audit trail</button></div></>}
        </>}
        <div className="workspace-message subtle">{notice}</div>
        {token && <pre className="result" id="saved-result">{savedResult}</pre>}
      </section>
      <details className="panel manual"><summary>Quick stateless assessment</summary><form onSubmit={analyzeChange}><div className="form-grid"><label>Service<input name="service" placeholder="checkout-api" required/></label><label>Key<input name="key" placeholder="DB_POOL_SIZE" required/></label><label>Current value<input name="before" placeholder="20"/></label><label>Proposed value<input name="after" placeholder="40"/></label></div><div className="form-actions"><small>Values are analyzed in memory and not saved.</small><button type="submit">Assess change <span>?</span></button></div></form><pre className="result">{statelessResult}</pre></details>
      <details className="panel manual"><summary>Explore downstream service impact</summary><form onSubmit={analyzeImpact}><div className="form-grid"><label>Service names, comma separated<input name="services" placeholder="api, auth, database" required/></label><label>Changed services<input name="changed-services" placeholder="api" required/></label><label className="wide">Dependencies: JSON edges from upstream source to downstream dependent<textarea name="dependencies" defaultValue={'[{"source":"api","target":"auth"},{"source":"auth","target":"database"}]'} required/></label></div><div className="form-actions"><small>Supply relationships known for this scenario.</small><button type="submit">Trace impact <span>?</span></button></div></form><pre className="result">{impactResult}</pre></details>
      <footer><span>CAUSORA � CONFIGURATION CAUSALITY</span><span>Deterministic rules � No production access</span></footer>
    </section>
  </main>
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
