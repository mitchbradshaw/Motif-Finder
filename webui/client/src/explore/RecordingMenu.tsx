/* Recording selector + its menu (frame explore-1b, left popover). Rows come from live /api/recordings:
   name, channels, length, fs, and a status column derived from what the bridge says — `⇄ linked fs2` for
   an `_fs1`/`_fs2` pair of the same recording (B30), `held out · locked` for the held-out file (D6, a
   disabled row with its reason). The filter narrows by name; the footer links to Settings › Datasets. */
import { useMemo, useRef, useState } from 'react'
import type { RecordingFile } from '../api'
import { DisabledReason, Icon, Popover, TextField, Tooltip } from '../kit'
import { navigate } from '../state'

function linkedTo(f: RecordingFile, all: RecordingFile[]): string | null {
  const m = f.source_file.match(/^(.*)_fs(\d+)(\.[a-z0-9]+)$/i)
  if (!m) return null
  const other = all.find(o => o !== f && o.source_file.startsWith(`${m[1]}_fs`) && o.source_file.endsWith(m[3]))
  const om = other?.source_file.match(/_fs(\d+)\./i)
  return om ? `fs${om[1]}` : null
}
const fmtLen = (h: number) => (h >= 10 ? `${Math.round(h)} h` : `${h.toFixed(1)} h`)
const fmtFs = (fs: number) => `${Number.isInteger(fs) ? fs : fs.toFixed(1)} Hz`

export function RecordingMenu({ files, current, open, setOpen, onPick }: {
  files: RecordingFile[] | null; current: RecordingFile | null; open: boolean; setOpen: (o: boolean) => void; onPick: (f: RecordingFile) => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const [q, setQ] = useState('')
  const rows = useMemo(() => (files ?? []).filter(f => f.source_file.toLowerCase().includes(q.trim().toLowerCase())), [files, q])
  return (
    <>
      <button ref={ref} type="button" className="ex-rec-trigger" onClick={() => setOpen(!open)} aria-haspopup="dialog" aria-expanded={open} data-testid="recording-select" disabled={!files}
        title={files ? 'choose a recording' : 'loading recordings…'}>
        <Icon name={current?.held_out ? 'lock' : 'database'} size={14} className="db" />
        {current ? <><b>{current.source_file}</b><span className="meta">{current.n_channels} ch · {fmtLen(current.duration_h)} · {fmtFs(current.fs)}</span></> : <span className="meta">loading recordings…</span>}
        <Icon name="chevron-down" size={13} className="chev" />
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} width={560} flush testid="recordings-menu" ariaLabel="recordings">
        <div className="ex-rec-menu">
          <TextField value={q} onChange={setQ} placeholder="filter recordings" icon="search" block testid="recordings-filter" />
          <div className="ex-rec-table" role="listbox" aria-label="recordings">
            <div className="hd"><span>recording</span><span>ch</span><span>length</span><span>fs</span><span>status</span></div>
            {rows.map(f => {
              const sel = f.source_file === current?.source_file
              const link = linkedTo(f, files ?? [])
              const row = (
                <button key={f.source_file} type="button" role="option" aria-selected={sel} aria-disabled={f.held_out || undefined} className={`r${sel ? ' sel' : ''}${f.held_out ? ' locked' : ''}`}
                  onClick={() => { if (!f.held_out) { onPick(f); setOpen(false) } }} data-testid={`recording-row-${f.source_file}`}>
                  <span className="nm">{sel ? <Icon name="check" size={13} className="ck" /> : <Icon name={f.held_out ? 'lock' : 'database'} size={13} />}<span>{f.source_file}</span></span>
                  <span>{f.n_channels}</span><span>{fmtLen(f.duration_h)}</span><span>{fmtFs(f.fs)}</span>
                  <span className="st">{f.held_out ? 'held out · locked' : link ? <Tooltip content={`same recording resampled at ${link.slice(2)} Hz — counts are not independent (B30)`}><span>⇄ linked {link}</span></Tooltip> : ''}</span>
                </button>
              )
              return f.held_out ? <DisabledReason key={f.source_file} reason={f.held_out_reason ?? 'held out · locked (D6) — Settings › Datasets'} block>{row}</DisabledReason> : row
            })}
            {!rows.length && <div className="empty" data-testid="recordings-empty">no recording matches "{q}"</div>}
          </div>
          <div className="ft">
            <button type="button" className="ex-link" onClick={() => { setOpen(false); navigate('settings/datasets?modal=import') }} data-testid="import-recording"><Icon name="plus" size={13} /> Import a recording in Settings › Datasets</button>
            <span className="hint">‹ › page through recordings</span>
          </div>
        </div>
      </Popover>
    </>
  )
}
