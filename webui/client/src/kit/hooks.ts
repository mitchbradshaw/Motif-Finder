/* Kit hooks and helpers: query-bound state, paging, clipboard, the surface layer stack, anchored positioning. */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore, type RefObject } from 'react'
import { parseHash, setQuery } from '../state'

/* ---------------- useQueryState ---------------- */
function subscribeHash(l: () => void) { window.addEventListener('hashchange', l); return () => window.removeEventListener('hashchange', l) }
const readHash = () => window.location.hash

/** State bound to a hash query parameter (`#/models/launch?tab=results`), so the state is deep-linkable.
 *  The default value is not written to the URL. Updates replace the history entry unless `push` is set. */
export function useQueryState<T extends string = string>(key: string, defaultValue: NoInfer<T>, opts: { push?: boolean } = {}): [T, (next: T | null) => void] {
  const hash = useSyncExternalStore(subscribeHash, readHash, readHash)
  const value = (parseHash(hash).query[key] as T | undefined) ?? defaultValue
  const set = useCallback((next: T | null) => {
    setQuery({ [key]: next === null || next === defaultValue ? null : next }, !opts.push)
  }, [key, defaultValue, opts.push])
  return [value, set]
}

/** Boolean flavour of useQueryState: `?drawer=1`. */
export function useQueryFlag(key: string, opts: { push?: boolean } = {}): [boolean, (next: boolean) => void] {
  const [v, set] = useQueryState<string>(key, '', opts)
  return [v === '1', useCallback((next: boolean) => set(next ? '1' : null), [set])]
}

/* ---------------- usePagedList ---------------- */
export interface PagedList<T> {
  page: number; pageCount: number; pageSize: number; total: number
  items: T[]; from: number; to: number; label: string
  setPage: (p: number) => void; next: () => void; prev: () => void; hasNext: boolean; hasPrev: boolean
}

/** Client-side paging over an array. `page` is 1-based; `label` reads "1–10 of 112". */
export function usePagedList<T>(all: readonly T[], pageSize = 10, initialPage = 1): PagedList<T> {
  const [page, setPageRaw] = useState(initialPage)
  const total = all.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const p = Math.min(Math.max(1, page), pageCount)
  const setPage = useCallback((n: number) => setPageRaw(Math.max(1, n)), [])
  const from = total ? (p - 1) * pageSize + 1 : 0
  const to = Math.min(total, p * pageSize)
  const items = useMemo(() => all.slice((p - 1) * pageSize, p * pageSize), [all, p, pageSize])
  return {
    page: p, pageCount, pageSize, total, items, from, to, label: total ? `${fmtInt(from)}–${fmtInt(to)} of ${fmtInt(total)}` : '0 of 0',
    setPage, next: () => setPageRaw(Math.min(pageCount, p + 1)), prev: () => setPageRaw(Math.max(1, p - 1)), hasNext: p < pageCount, hasPrev: p > 1,
  }
}

/* ---------------- clipboard ---------------- */
/** Copy text to the clipboard; resolves true on success. Falls back to a hidden textarea when the async API is blocked. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return true }
  } catch { /* fall through */ }
  try {
    const ta = document.createElement('textarea')
    ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0'
    document.body.appendChild(ta); ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch { return false }
}

/* ---------------- formatting ---------------- */
export const fmtInt = (n: number) => Math.round(n).toLocaleString('en-US')
/** "+0.40 mV", "−0.34 mV" (typographic minus), "0 mV". */
export function fmtMv(v: number, digits = 2, unit = true) {
  const s = v === 0 ? '0' : `${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(digits)}`
  return unit ? `${s} mV` : s
}
export const fmtPct = (fraction: number, digits = 0) => `${(fraction * 100).toFixed(digits)} %`

/* ---------------- layer stack (Escape goes to the topmost surface only) ---------------- */
const layers: symbol[] = []
/** Register an open surface. Returns `isTop()`; a surface acts on Escape only when it is the top layer. */
export function useLayer(active: boolean) {
  const id = useRef(Symbol('layer'))
  useEffect(() => {
    if (!active) return
    const me = id.current
    layers.push(me)
    return () => { const i = layers.lastIndexOf(me); if (i >= 0) layers.splice(i, 1) }
  }, [active])
  return useCallback(() => layers[layers.length - 1] === id.current, [])
}

/** Escape (window capture phase, so it runs before shell/useDismiss listeners) + pointer-down outside all `refs`. */
export function useSurfaceDismiss(refs: RefObject<HTMLElement | null>[], onClose: (reason: 'escape' | 'outside') => void, active: boolean, opts: { outside?: boolean } = {}) {
  const isTop = useLayer(active)
  const cb = useRef(onClose); cb.current = onClose
  const refsRef = useRef(refs); refsRef.current = refs
  useEffect(() => {
    if (!active) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || !isTop()) return
      e.stopPropagation(); e.preventDefault()
      cb.current('escape')
    }
    const onDown = (e: PointerEvent) => {
      if (!isTop()) return
      const t = e.target as Node
      if (refsRef.current.some(r => r.current?.contains(t))) return
      cb.current('outside')
    }
    window.addEventListener('keydown', onKey, true)
    let id = 0
    if (opts.outside !== false) id = window.setTimeout(() => document.addEventListener('pointerdown', onDown, true), 0)
    return () => { window.removeEventListener('keydown', onKey, true); window.clearTimeout(id); document.removeEventListener('pointerdown', onDown, true) }
  }, [active, isTop, opts.outside])
}

/* ---------------- anchored positioning ---------------- */
export type Placement = 'bottom-start' | 'bottom-end' | 'bottom' | 'top-start' | 'top-end' | 'top' | 'right-start' | 'left-start'

/** Position a fixed element next to an anchor; flips to the opposite side when it would leave the viewport,
 *  and clamps horizontally. Re-measures on scroll and resize. */
export function useAnchoredPosition(anchor: RefObject<HTMLElement | null>, floating: RefObject<HTMLElement | null>, open: boolean, placement: Placement = 'bottom-start', offset = 6) {
  const [pos, setPos] = useState<{ top: number; left: number; placement: Placement } | null>(null)
  const measure = useCallback(() => {
    const a = anchor.current, f = floating.current
    if (!a || !f) return
    const ar = a.getBoundingClientRect(), fr = f.getBoundingClientRect()
    const vw = window.innerWidth, vh = window.innerHeight, m = 8
    let [side, align] = placement.split('-') as [string, string | undefined]
    let top = 0, left = 0
    if (side === 'bottom' || side === 'top') {
      if (side === 'bottom' && ar.bottom + offset + fr.height > vh - m && ar.top - offset - fr.height > m) side = 'top'
      else if (side === 'top' && ar.top - offset - fr.height < m && ar.bottom + offset + fr.height < vh - m) side = 'bottom'
      top = side === 'bottom' ? ar.bottom + offset : ar.top - offset - fr.height
      left = align === 'start' ? ar.left : align === 'end' ? ar.right - fr.width : ar.left + ar.width / 2 - fr.width / 2
    } else {
      if (side === 'right' && ar.right + offset + fr.width > vw - m) side = 'left'
      else if (side === 'left' && ar.left - offset - fr.width < m) side = 'right'
      left = side === 'right' ? ar.right + offset : ar.left - offset - fr.width
      top = ar.top
    }
    left = Math.max(m, Math.min(left, vw - m - fr.width))
    top = Math.max(m, Math.min(top, vh - m - fr.height))
    setPos(p => (p && Math.abs(p.top - top) < 0.5 && Math.abs(p.left - left) < 0.5 && p.placement.startsWith(side)) ? p : { top, left, placement: `${side}${align ? '-' + align : ''}` as Placement })
  }, [anchor, floating, placement, offset])
  useLayoutEffect(() => {
    if (!open) { setPos(null); return }
    measure()
    const ro = new ResizeObserver(measure)
    if (floating.current) ro.observe(floating.current)
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)
    return () => { ro.disconnect(); window.removeEventListener('scroll', measure, true); window.removeEventListener('resize', measure) }
  }, [open, measure, floating])
  return pos
}

/** Controlled-or-uncontrolled value. */
export function useControllable<T>(value: T | undefined, defaultValue: T, onChange?: (v: T) => void): [T, (v: T) => void] {
  const [inner, setInner] = useState(defaultValue)
  const controlled = value !== undefined
  const v = controlled ? value as T : inner
  const set = useCallback((next: T) => { if (!controlled) setInner(next); onChange?.(next) }, [controlled, onChange])
  return [v, set]
}

/** Seeded sample of k indices out of n (stable for a given seed). */
export function sampleIndices(n: number, k: number, seed: number): number[] {
  if (k >= n) return Array.from({ length: n }, (_, i) => i)
  let s = (seed * 2654435761) >>> 0 || 1
  const rnd = () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return (s >>> 0) / 4294967296 }
  const idx = Array.from({ length: n }, (_, i) => i)
  for (let i = 0; i < k; i++) { const j = i + Math.floor(rnd() * (n - i)); [idx[i], idx[j]] = [idx[j], idx[i]] }
  return idx.slice(0, k).sort((a, b) => a - b)
}
