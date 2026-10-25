/* The Analyse pages' number format (moved out of EventFeatures.tsx by night-b so it runs under Node in
 * tests/test_webui_night_b_fmtnum.py; EventFeatures re-exports it). An exact zero is "0" and a count column
 * (`n_…`) is an integer: the one-event intervals table read "events 1.000 · intervals 0.00e+0".
 * tq-analyse (2026-10-25): `fmtN`, the type views' format (views/common.tsx re-exports it), moved here, and
 * `fmtNum` is its column rules in front of it: the two were the same numeric branch written twice. */
export function fmtN(v: number): string {
  if (!Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  return a === 0 ? '0' : a >= 1000 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 0.01 ? v.toFixed(3) : v.toExponential(2)
}

export function fmtNum(v: number | null | undefined, col = ''): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  if (col === 'polarity') return v < 0 ? 'drop' : 'spike'
  if (col.endsWith('_idx') || col.startsWith('n_')) return String(Math.round(v))
  return fmtN(v)
}
