import { StrictMode, type FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = 'http://localhost:8000/api/v1'

async function submit(url: string, payload: unknown, output: HTMLElement | null) {
  if (!output) return
  output.textContent = 'Analyzing…'
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const result = await response.json()
    output.textContent = JSON.stringify(result, null, 2)
  } catch {
    output.textContent = 'API unavailable. Start the local API at http://localhost:8000 and try again.'
  }
}

function App() {
  async function analyzeChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    await submit(`${API}/analyses`, {
      changes: [{
        service: data.get('service'),
        key: data.get('key'),
        before: data.get('before'),
        after: data.get('after'),
      }],
    }, document.getElementById('result'))
  }

  async function diffConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    await submit(`${API}/config-diffs`, {
      service: data.get('diff-service'),
      format: data.get('format'),
      before: data.get('config-before'),
      after: data.get('config-after'),
    }, document.getElementById('diff-result'))
  }

  async function analyzeImpact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const output = document.getElementById('impact-result')
    try {
      await submit(`${API}/impact`, {
        services: String(data.get('services')).split(',').map(value => value.trim()).filter(Boolean),
        changed_services: String(data.get('changed-services')).split(',').map(value => value.trim()).filter(Boolean),
        dependencies: JSON.parse(String(data.get('dependencies'))),
      }, output)
    } catch {
      if (output) output.textContent = 'Dependencies must be valid JSON, for example [{"source":"api","target":"database"}].'
    }
  }

  return <main className="shell">
    <aside className="rail"><div className="mark">C</div><div className="rail-icon active">?</div><div className="rail-icon">?</div><div className="rail-icon">?</div><div className="rail-bottom">?</div></aside>
    <section className="page">
      <header><div className="brand"><span className="eyebrow">OPERATIONS INTELLIGENCE</span><h1>Causora<span className="dot">.</span></h1></div><div className="user"><span className="pulse"></span> LOCAL PREVIEW <b>SD</b></div></header>
      <div className="intro"><div><div className="eyebrow">CHANGE INTELLIGENCE / OVERVIEW</div><h2>Know what a change could break.</h2><p>Trace configuration changes into operational risk before they reach production.</p></div><button onClick={() => document.getElementById('config-diff')?.scrollIntoView({ behavior: 'smooth' })}>+ &nbsp; New analysis</button></div>
      <div className="notice"><span>i</span><div><strong>Foundation preview</strong><small>Analysis is deterministic and uses only the values you submit. No cloud account is connected.</small></div><span className="tag">LOCAL</span></div>
      <div className="stats"><article><label>ANALYSES RUN</label><strong>—</strong><small>Ready when you are</small></article><article><label>SERVICES MAPPED</label><strong>0</strong><small>Connect a system to begin</small></article><article><label>OPEN FINDINGS</label><strong>0</strong><small>No active assessments</small></article></div>
      <section className="panel" id="config-diff"><div className="panel-head"><div><div className="eyebrow">CONFIG INGESTION</div><h3>Compare YAML or JSON configuration</h3></div><span className="tag muted">MAX 250 KB / FILE</span></div>
        <form onSubmit={diffConfig}><div className="form-grid"><label>Service name<input name="diff-service" placeholder="e.g. checkout-api" required/></label><label>Document format<select name="format"><option value="yaml">YAML</option><option value="json">JSON</option></select></label><label>Before<textarea name="config-before" placeholder={'database:\n  pool_size: 20'} required/></label><label>After<textarea name="config-after" placeholder={'database:\n  pool_size: 40'} required/></label></div><div className="form-actions"><small>Secret-like values are redacted from the result. Avoid pasting real production secrets.</small><button type="submit">Compare configs <span>?</span></button></div></form><pre id="diff-result" className="result">A key-by-key diff and evidence-backed findings will appear here.</pre>
      </section>
      <details className="panel manual"><summary>Or analyze a single setting</summary><form onSubmit={analyzeChange}><div className="form-grid"><label>Service<input name="service" placeholder="checkout-api" required/></label><label>Key<input name="key" placeholder="DB_POOL_SIZE" required/></label><label>Current value<input name="before" placeholder="20"/></label><label>Proposed value<input name="after" placeholder="40"/></label></div><div className="form-actions"><small>Sent to the local analysis API.</small><button type="submit">Assess change <span>?</span></button></div></form><pre id="result" className="result">Single-setting assessment result.</pre></details>
      <footer><span>CAUSORA · CONFIGURATION CAUSALITY</span><span>Deterministic rules · No production access</span></footer>
    </section>
  </main>
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
