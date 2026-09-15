/* The Review keymap (§10.3–10.5, Settings › Keyboard & behaviour): real key handlers, suppressed while typing. */
import { useEffect, useRef } from 'react'
import type { Verdict } from '../api/review'

export interface KeyHandlers {
  verdict: (v: Verdict) => void
  skip: () => void
  klass: (key: string) => void
  undo: () => void
  redo: () => void
  enter: () => boolean
  next: () => void
  prev: () => void
  edit?: () => void
  rails: () => void
}

export const SHORTCUTS: { keys: string[]; action: string }[] = [
  { keys: ['S'], action: 'seed · promotes to Library' },
  { keys: ['I'], action: 'interesting' },
  { keys: ['N'], action: 'not interesting' },
  { keys: ['A'], action: 'artifact · kept out of training' },
  { keys: ['U'], action: 'unsure' },
  { keys: ['Space'], action: 'skip · no write' },
  { keys: ['1', '2', '3', '4'], action: 'class spike-train · burst · slow-drift · plateau' },
  { keys: ['9'], action: 'class electrode artifact (non-informative)' },
  { keys: ['Ctrl', 'Z'], action: 'undo last write (a whole batch)' },
  { keys: ['Ctrl', 'Shift', 'Z'], action: 'redo' },
  { keys: ['Enter'], action: 'confirm promotion and next' },
  { keys: ['→', '←'], action: 'next · previous candidate' },
  { keys: ['E'], action: 'edit span in Explore' },
  { keys: ['\\'], action: 'open / close both rails' },
  { keys: ['Esc'], action: 'close a popover' },
]

const VERDICT_KEYS: Record<string, Verdict> = { s: 'seed', i: 'interesting', n: 'not_interesting', a: 'artifact', u: 'unsure' }

function typing(t: EventTarget | null) {
  const el = t as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
}
const activatable = (t: EventTarget | null) => {
  const el = t as HTMLElement | null
  return !!el && (el.tagName === 'BUTTON' || el.tagName === 'A' || ['radio', 'switch', 'checkbox', 'menuitem', 'option'].includes(el.getAttribute('role') ?? ''))
}

export function useReviewKeys(handlers: KeyHandlers, active = true) {
  const ref = useRef(handlers)
  ref.current = handlers
  useEffect(() => {
    if (!active) return
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || typing(e.target) || e.altKey || e.metaKey) return
      if (document.querySelector('.k-modal-backdrop')) return   // a modal owns the keyboard
      const h = ref.current
      const k = e.key.toLowerCase()
      if (e.ctrlKey) {
        if (k === 'z' && e.shiftKey) { e.preventDefault(); h.redo() }
        else if (k === 'z') { e.preventDefault(); h.undo() }
        else if (k === 'y') { e.preventDefault(); h.redo() }
        return
      }
      if (e.key === ' ') { if (activatable(e.target)) return; e.preventDefault(); h.skip(); return }
      if (e.key === 'Enter') { if (activatable(e.target)) return; if (h.enter()) e.preventDefault(); return }
      if (e.key === 'ArrowRight') { e.preventDefault(); h.next(); return }
      if (e.key === 'ArrowLeft') { e.preventDefault(); h.prev(); return }
      if (e.key === '\\') { e.preventDefault(); h.rails(); return }
      if (e.shiftKey) return
      if (VERDICT_KEYS[k]) { e.preventDefault(); h.verdict(VERDICT_KEYS[k]); return }
      if (['1', '2', '3', '4', '9'].includes(k)) { e.preventDefault(); h.klass(k); return }
      if (k === 'e' && h.edit) { e.preventDefault(); h.edit() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active])
}
