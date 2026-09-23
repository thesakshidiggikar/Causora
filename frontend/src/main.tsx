import React from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

function App() {
  return <main className="shell">
    <aside className="rail"><div className="mark">C</div><div className="rail-icon active">?</div><div className="rail-icon">?</div><div className="rail-icon">?</div><div className="rail-bottom">?</div></aside>
    <section className="page">
      <header><div className="brand"><span className="eyebrow">OPERATIONS INTELLIGENCE</span><h1>Causora<span className="dot">.</span></h1></div><div className="user"><span className="pulse"></span> LOCAL PREVIEW <b>SD</b></div></header>
      <div className="intro"><div><div className="eyebrow">CHANGE INTELLIGENCE / OVERVIEW</div><h2>Know what a change could break.</h2><p>Trace configuration changes into operational risk before they reach production.</p></div><button onClick={() => document.getElementById('analysis')?.scrollIntoView({behavior:'smooth'})}>+ &nbsp; New analysis</button></div>
      <div className="notice"><span>i</span><div><strong>Foundation preview</strong><small>Analysis is deterministic and uses only the values you submit. No cloud account is connected.</small></div><span className="tag">LOCAL</span></div>
      <div className="stats"><article><label>ANALYSES RUN</label><strong>—</strong><small>Ready when you are</small></article><article><label>SERVICES MAPPED</label><strong>0</strong><small>Connect a system to begin</small></article><article><label>OPEN FINDINGS</label><strong>0</strong><small>No active assessments</small></article></div>
      <section className="panel" id="analysis"><div className="panel-head"><div><div className="eyebrow">QUICK ASSESSMENT</div><h3>Analyze a configuration change</h3></div><span className="tag muted">RULE ENGINE</span></div><form onSubmit={async e => { e.preventDefault(); const f=e.currentTarget; const data=new FormData(f); const result=document.getElementById('result'); if(!result)return; result.textContent='Sending analysis…'; try { const r=await fetch('http://localhost:8000/api/v1/analyses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changes:[{service:data.get('service'),key:data.get('key'),before:data.get('before'),after:data.get('after')}]})}); const json=await r.json(); result.textContent=JSON.stringify(json,null,2) } catch { result.textContent='API unavailable. Start the backend at http://localhost:8000 and try again.' } }}>
        <div className="form-grid"><label>Service name<input name="service" placeholder="e.g. checkout-api" required/></label><label>Configuration key<input name="key" placeholder="e.g. DB_POOL_SIZE" required/></label><label>Current value<input name="before" placeholder="20"/></label><label>Proposed value<input name="after" placeholder="60"/></label></div><div className="form-actions"><small>Values are sent to the local API. Avoid entering real secrets.</small><button type="submit">Assess change <span>?</span></button></div></form><pre id="result" className="result">Your explainable assessment will appear here.</pre></section>
      <footer><span>CAUSORA · CONFIGURATION CAUSALITY</span><span>Deterministic rules · No production access</span></footer>
    </section>
  </main>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
