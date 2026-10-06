/* fixup-ai — what *Create SLURM script* shows, for the B.2 CNN (Models › Launch) and for Ward over every training window
 * (Analyse › Shape clustering): the steps on the cluster, what must be copied there and how big it is, the script as
 * written (and its path), and how the results come back. Nothing here submits anything: the researcher does. */
import { useState } from 'react'
import { fmtBytes, type CopyRow } from '../api/cnn'

export function CopyList({ rows, total, testid }: { rows: CopyRow[]; total: number; testid: string }) {
  return (
    <table className="sh-table" data-testid={testid} style={{ marginTop: 4 }}>
      <thead><tr><th>copy to the cluster</th><th>path (repo-relative, the same under the cluster's repo)</th><th className="r">size</th></tr></thead>
      <tbody>
        {rows.map(r => <tr key={r.path} data-testid={`copy-row-${r.what.replace(/\s+/g, '-')}`}><td>{r.what}</td><td className="mono small" title={r.note}>{r.path}{r.note ? <div className="muted small">{r.note}</div> : null}</td><td className="r mono">{fmtBytes(r.bytes)}</td></tr>)}
        <tr><td><b>in all</b></td><td className="muted small">plus the repository's code at this commit (git pull on the cluster)</td><td className="r mono" data-testid={`${testid}-total`}><b>{fmtBytes(total)}</b></td></tr>
      </tbody>
    </table>
  )
}

export function ScriptBlock({ script, path, testid }: { script: string; path: string; testid: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(script).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500) },
      e => console.error('clipboard refused', e))
  }
  return (
    <div style={{ marginTop: 6 }}>
      <div className="row" style={{ gap: 8, alignItems: 'baseline' }}>
        <span className="mono small" data-testid={`${testid}-path`}>{path}</span>
        <button className="btn sm" onClick={copy} data-testid={`${testid}-copy`}>{copied ? 'copied' : 'copy the script'}</button>
      </div>
      <pre className="mono small" data-testid={testid} style={{ maxHeight: 320, overflow: 'auto', background: 'var(--bg-2, #f6f6f6)', padding: 8, borderRadius: 6, whiteSpace: 'pre' }}>{script}</pre>
    </div>
  )
}

export function Steps({ steps, testid }: { steps: string[]; testid: string }) {
  return <ol className="small" data-testid={testid} style={{ margin: '4px 0 0 18px', padding: 0 }}>{steps.map((s, i) => <li key={i} style={{ marginBottom: 3 }}>{s}</li>)}</ol>
}
