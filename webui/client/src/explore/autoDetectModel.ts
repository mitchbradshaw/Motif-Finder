/* Explore › Auto-detect, the pure part (no DOM, no React): the stretch's samples decoded once into a min/max pyramid
   so every zoom is local, what the filters show, and the formatting. The drawing is AutoDetectViewer.tsx; the page
   is AutoDetectPage.tsx. Ported from the reference viewer the researcher reviewed (scripts/autodetect/
   viewer_template.html, 2026-11-23). */
import type { AdCands, AdSignal } from '../api/autodetect'

export interface Level { b: number; mn: Float32Array; mx: Float32Array }
/** The stretch as the page holds it: millivolts (NaN = a gap), its pyramid, and where it sits on the channel. */
export interface Sig { y: Float32Array; levels: Level[]; n: number; fs: number; start_idx: number; unit: string; unit_note: string | null }

export function decodeSignal(s: AdSignal): Sig {
  const bin = atob(s.b64)
  const u8 = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i)
  const q = new Int16Array(u8.buffer)
  const y = new Float32Array(q.length)
  for (let i = 0; i < q.length; i++) y[i] = q[i] === s.missing ? NaN : q[i] * s.scale + s.offset
  return { y, levels: pyramid(y), n: q.length, fs: s.fs, start_idx: s.start_idx, unit: s.unit, unit_note: s.unit_note }
}

/** min/max levels, each 8x coarser, until a level has under 64 bins. */
export function pyramid(y: Float32Array): Level[] {
  const out: Level[] = []
  let mn = y, mx = y, b = 1
  for (let step = 0; step < 6; step++) {
    const f = 8
    const nb = Math.ceil(mn.length / f)
    const lo = new Float32Array(nb), hi = new Float32Array(nb)
    for (let i = 0; i < nb; i++) {
      let a = Infinity, z = -Infinity
      const e = Math.min(mn.length, (i + 1) * f)
      for (let j = i * f; j < e; j++) { const u = mn[j], w = mx[j]; if (u < a) a = u; if (w > z) z = w }
      lo[i] = a === Infinity ? NaN : a; hi[i] = z === -Infinity ? NaN : z
    }
    b *= f
    out.push({ b, mn: lo, mx: hi })
    mn = lo; mx = hi
    if (nb < 64) break
  }
  return out
}

/** Per pixel column: the lowest and highest sample between v0 and v1 (sample indices), from the coarsest level fine
 *  enough. `spp` is samples per column. */
export function envelope(sig: Sig, v0: number, v1: number, cols: number) {
  const spp = (v1 - v0) / cols
  const mins = new Float32Array(cols), maxs = new Float32Array(cols)
  let L: Level | null = null
  for (const l of sig.levels) if (l.b <= spp / 2) L = l
  const mnA = L ? L.mn : sig.y, mxA = L ? L.mx : sig.y, b = L ? L.b : 1
  for (let c = 0; c < cols; c++) {
    const s0 = v0 + c * spp, s1 = s0 + spp
    const i0 = Math.max(0, Math.floor(s0 / b)), i1 = Math.min(mnA.length, Math.max(i0 + 1, Math.ceil(s1 / b)))
    let a = Infinity, z = -Infinity
    for (let i = i0; i < i1; i++) { const u = mnA[i], w = mxA[i]; if (u < a) a = u; if (w > z) z = w }
    mins[c] = a === Infinity ? NaN : a; maxs[c] = z === -Infinity ? NaN : z
  }
  return { mins, maxs, spp }
}

// ── what is shown ────────────────────────────────────────────────────────

export const SCAN = 'r4_scan'
export const NONE = 'none'
export interface Filter { minc: number; drop: boolean; rise: boolean; src: Set<string> }

/** Candidate i passes the filters: confidence, type, and one of its sources (a candidate R4's scan found alone is
 *  `r4_scan`; one inside another box that no source vouched for is `none`). */
export function isShown(c: AdCands, sources: string[], f: Filter, i: number): boolean {
  if (c.c[i] < f.minc - 1e-9) return false
  if (c.pol[i] ? !f.rise : !f.drop) return false
  if (c.k[i] === 1) return f.src.has(SCAN)
  const m = c.src[i]
  if (!m) return f.src.has(NONE)
  for (let k = 0; k < sources.length; k++) if ((m & (1 << k)) && f.src.has(sources[k])) return true
  return false
}

export function sourcesOf(c: AdCands, sources: string[], i: number): string[] {
  if (c.k[i] === 1) return [SCAN]
  const out: string[] = []
  for (let k = 0; k < sources.length; k++) if (c.src[i] & (1 << k)) out.push(sources[k])
  return out
}

/** Every candidate's index, by start then end. */
export function byStart(c: AdCands): number[] {
  return Array.from({ length: c.s.length }, (_, i) => i).sort((a, b) => c.s[a] - c.s[b] || c.e[a] - c.e[b])
}

export function longest(c: AdCands): number {
  let m = 0
  for (let i = 0; i < c.s.length; i++) m = Math.max(m, c.e[i] - c.s[i])
  return m
}

/** Calls fn for each candidate (in start order) whose box overlaps [v0, v1). */
export function eachVisible(c: AdCands, order: number[], maxDur: number, v0: number, v1: number, fn: (i: number) => void) {
  let lo = 0, hi = order.length
  const key = v0 - maxDur
  while (lo < hi) { const m = (lo + hi) >> 1; if (c.s[order[m]] < key) lo = m + 1; else hi = m }
  for (let j = lo; j < order.length; j++) { const i = order[j]; if (c.s[i] >= v1) break; if (c.e[i] > v0) fn(i) }
}

/** Counts per source key (and `r4_scan`, `none`, `drop`, `spike`) for the filter labels. */
export function sourceCounts(c: AdCands, sources: string[]): Record<string, number> {
  const out: Record<string, number> = { [SCAN]: 0, [NONE]: 0, drop: 0, spike: 0 }
  for (const s of sources) out[s] = 0
  for (let i = 0; i < c.s.length; i++) {
    out[c.pol[i] ? 'spike' : 'drop']++
    if (c.k[i] === 1) { out[SCAN]++; continue }
    if (!c.src[i]) { out[NONE]++; continue }
    for (let k = 0; k < sources.length; k++) if (c.src[i] & (1 << k)) out[sources[k]]++
  }
  return out
}

// ── formatting ───────────────────────────────────────────────────────────

/** Hours on the recording's clock of stretch index `idx`. */
export const hoursOf = (sig: { fs: number; start_idx: number }, idx: number) => (idx + sig.start_idx) / sig.fs / 3600

export function clock(seconds: number, withSeconds = true): string {
  const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = Math.floor(seconds % 60)
  return withSeconds ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${h}:${String(m).padStart(2, '0')}`
}

export function duration(samples: number, fs: number): string {
  const s = samples / fs
  if (s < 120) return `${s.toFixed(s < 10 ? 1 : 0)} s`
  if (s < 7200) return `${(s / 60).toFixed(1)} min`
  return `${(s / 3600).toFixed(1)} h`
}

export function minutes(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return '—'
  if (seconds < 90) return `${Math.round(seconds)} s`
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`
  return `${(seconds / 3600).toFixed(1)} h`
}

/** "220:08", "220:08:30" or "220.13" → hours; null when it is not a time. */
export function parseHour(text: string): number | null {
  const s = text.trim()
  if (!s) return null
  const m = /^(\d+):(\d{1,2})(?::(\d{1,2}(?:\.\d+)?))?$/.exec(s)
  const h = m ? Number(m[1]) + Number(m[2]) / 60 + (m[3] ? Number(m[3]) / 3600 : 0) : Number(s)
  return Number.isFinite(h) ? h : null
}

/** A tick step (in samples) giving about `target` ticks across `range` samples. */
export function tickStep(range: number, target: number, fs: number): number {
  const raw = range / target
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400, 172800]
  for (const s of steps) if (s * fs >= raw) return s * fs
  return steps[steps.length - 1] * fs
}

export function valueStep(lo: number, hi: number, target: number): number {
  const r = (hi - lo) / target, p = Math.pow(10, Math.floor(Math.log10(r))), m = r / p
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p
}

/** Confidence → fill opacity of a box (the reference viewer's ramp). */
export const alphaOf = (c: number) => 0.07 + 0.55 * Math.max(0, Math.min(1, (c - 0.3) / 0.7))

export const COLOUR = { drop: '#4f46e5', rise: '#db2777', scan: '#d97706', seqDrop: '#0d9488', seqRise: '#db2777' }

export function rgba(hex: string, a: number): string {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map(x => x + x).join('') : h, 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}
