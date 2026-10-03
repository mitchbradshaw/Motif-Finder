/* "Save window set" (§6.9, P18; fixup-aa) — offered on the chain row and the block page of every block whose
   output type is WindowSet. Saving re-derives the set from the run's recipe up to this step, keeps no two
   overlapping windows when it is a training set (on by default, Q-W1), counts the human-verdict coverage at
   save, and writes the `window_sets` row Library › Window sets reads. The bridge answers with what it counted,
   and the toast says it — an absence (unlabelled, dropped) is the result, so it is on the face. */
import { useState } from 'react'
import { ApiError, saveWindowSetAs, type SavedWindowSet } from '../api'
import { Button, Checkbox, Modal, TextField } from '../kit'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'

const NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/

export function savedSummary(r: SavedWindowSet): string {
  const c = r.coverage
  const classes = Object.entries(c.class_counts_at_save).map(([k, v]) => `${k} ${v.toLocaleString()}`).join(' · ')
  return `${r.name} · ${r.n_windows.toLocaleString()} windows saved of ${r.n_windows_offered.toLocaleString()} · ${c.labelled_windows.toLocaleString()} labelled (${classes})`
    + ` · unlabelled ${c.unlabelled.toLocaleString()} · conflicting ${c.conflicting.toLocaleString()} · artifact ${c.artifact.toLocaleString()}`
    + ` · dropped for overlap ${c.dropped_for_overlap.toLocaleString()}${c.non_overlap_rule ? ` (${c.non_overlap_rule})` : ''}`
}

/** The button and its dialog. `jobId` null (or a `disabledReason`) disables it with the reason as its title. */
export function SaveWindowSetButton({ jobId, step, defaultName, disabledReason, testid, small }: {
  jobId: number | null; step: number; defaultName: string; disabledReason?: string | null; testid: string; small?: boolean
}) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(defaultName)
  const [nonOverlap, setNonOverlap] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reason = jobId === null ? 'run the chain first — a window set is saved from a run\'s result' : disabledReason ?? null
  const save = async () => {
    if (jobId === null || busy) return
    setBusy(true); setError(null)
    try {
      const r = await saveWindowSetAs(jobId, step, name, { non_overlapping: nonOverlap })
      setOpen(false)
      toast.push({ text: savedSummary(r), ttlMs: 12000, action: { label: 'Open in Library', onClick: () => navigate(`library/window-sets?set=${encodeURIComponent(r.name)}`) } })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally { setBusy(false) }
  }
  const valid = NAME.test(name)
  return (
    <>
      <button className={`btn${small ? ' sm' : ''}`} disabled={!!reason} title={reason ?? 'save this step\'s windows as a reusable set (Library › Window sets)'}
        onClick={() => { setName(defaultName); setError(null); setOpen(true) }} data-testid={testid}>⤓ Save window set</button>
      <Modal open={open} onClose={() => setOpen(false)} size="sm" title="Save window set" subtitle={`step ${String(step + 1).padStart(2, '0')} of job ${jobId ?? '—'}`} testid="save-window-set-modal"
        footer={<><Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="primary" disabled={!valid || busy} disabledReason={!valid ? 'letters, digits, _ . - (no spaces), up to 64' : 'saving…'} onClick={save} testid="save-window-set-confirm">{busy ? 'Saving…' : 'Save'}</Button></>}>
        <div className="stack" style={{ gap: 10 }}>
          <TextField value={name} onChange={setName} placeholder="ws_name" invalid={!valid} block testid="save-window-set-name" autoFocus onEnter={save} />
          <Checkbox checked={nonOverlap} onChange={setNonOverlap} testid="save-window-set-non-overlap"
            label={<span>Training set — keep no two overlapping windows</span>} />
          <span className="muted small">
            {nonOverlap
              ? 'Labelled windows are kept first — each unless it overlaps one already kept — then unlabelled windows fill the gaps; the rest are counted as dropped. Overlapping training windows share samples, so a model would be tested on what it trained on.'
              : 'Every window is kept, overlapping neighbours included. The set will fail its spacing check and be badged not train-safe.'}
          </span>
          <span className="muted small">Coverage is counted at save by the manual-label rule: a window is labelled only if it wholly contains a human-labelled span and every span it contains agrees. Library › Window sets shows it now and at save.</span>
          {error && <div className="error-card" style={{ padding: '6px 10px' }} data-testid="save-window-set-error"><div className="mono small">{error}</div></div>}
        </div>
      </Modal>
    </>
  )
}
