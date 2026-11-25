/* The NeurIPS demo's entry (demo.html; `npm run build:neurips` → dist-neurips/). Separate from the site's main.tsx:
   the normal build neither imports nor ships any of src/demo. */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../theme.css'
import './demo.css'
import { api } from './api'
import { App } from './App'
import { DemoProvider } from './store'

const root = createRoot(document.getElementById('root')!)
api.manifest().then(
  m => root.render(<StrictMode><DemoProvider m={m}><App /></DemoProvider></StrictMode>),
  e => root.render(<div className="boot-error" data-testid="boot-error"><h2>MycoWave could not start</h2><p>{String(e?.message || e)}</p>
    <button onClick={() => window.location.reload()}>Try again</button></div>),
)
