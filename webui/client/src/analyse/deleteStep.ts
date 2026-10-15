/* Delete one stage of the chain, with an undo (Ctrl Z restores it; frame chain-1e). Shared by the chain canvas and
   the block page (2026-10-15: "should be able to delete a block from analyse from within a block's settings view").
   The stage after the deleted one is marked stale so the next run recomputes from there. */
import type { ChainDraft } from '../state'
import type { useToast } from '../shell/Toast'
import { dropUndo, markStale, pushUndo, type UndoEntry } from './store'

type SetChain = (c: (prev: ChainDraft) => ChainDraft) => void
type Toast = ReturnType<typeof useToast>
const pad = (n: number) => String(n).padStart(2, '0')

export function restoreStep(setChain: SetChain, u: UndoEntry) {
  dropUndo(u); setChain(c => ({ ...c, saved: false, steps: u.steps })); markStale(u.staleIndex)
}

export function deleteStepAt({ steps, index, name, setChain, toast }: {
  steps: ChainDraft['steps']; index: number; name: string; setChain: SetChain; toast: Toast
}) {
  const entry: UndoEntry = { steps, staleIndex: index, label: `${pad(index + 1)} ${name}` }
  pushUndo(entry)
  setChain(c => ({ ...c, saved: false, steps: c.steps.filter((_, k) => k !== index) }))
  markStale(index)
  toast.push({ text: `${pad(index + 1)} ${name} deleted`, action: { label: 'Undo', hint: 'Ctrl Z', onClick: () => restoreStep(setChain, entry) } })
}
