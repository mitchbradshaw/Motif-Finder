/* W3-F: a SpanSet that carries a STACK OF CYCLES (`payload.cycle_stack`, a payload convention — cycle shapes ships
 * one). Wired the way DetectorFunnel is: `cycleStackOf(payload)` reads the payload, never the block's name.
 *
 *  - two heat-maps, BEFORE and AFTER alignment: one row per cycle in time order (each cycle stretched to one
 *    length and z-normalised by the block), a group-colour strip beside them, the block's change points marked
 *    as amber lines between rows;
 *  - under them, each group's medoid cycle as a MEMBER (the block named it: `cycle_exemplars`), drawn from the
 *    recording in small multiples, each on its own y with a scale bar (drawing rule 4);
 *  - each sequence's and group's verdict exactly as the block gave it (`whole_verdict`, a group's `verdict` and its
 *    `~noise_like` / `~untested` key): nothing here compares a score with a null. σ² leads, eq. 17 beside it. */
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import type { CycleExemplar, CycleSequence, CycleStack as CycleStackT, CycleVerdict, SpansetPayload } from '../api'
import { measuredDomain } from '../charts/domain'
import { EventTrace, InfoTip, ScaleBar, type SlideTrace } from '../kit'
import { fmtDuration, fmtHours } from '../state'
import { familyColour } from './views/GroupingView'
import { loadWindow } from './views/common'

export function cycleStackOf(p: unknown): CycleStackT | null {
  const s = (p as SpansetPayload | null)?.cycle_stack
  return s && Array.isArray(s.rows) ? s : null
}

const f2 = (v: number | null | undefined) => (v === null || v === undefined || !Number.isFinite(v) ? '—' : v.toFixed(2))
const ROW_H_MAX = 4

/** z-normalised values on a diverging ramp clipped at ±2.5: blue below, white at 0, amber above. */
function rgb(v: number): [number, number, number] {
  const u = Math.max(-1, Math.min(1, v / 2.5))
  return u < 0 ? [Math.round(255 + u * (255 - 10)), Math.round(255 + u * (255 - 132)), 255] : [255, Math.round(255 - u * (255 - 144)), Math.round(255 - u * (255 - 12))]
}

function StackCanvas({ rows, which, testid }: { rows: CycleStackT['rows']; which: 'before' | 'after'; testid: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const n = rows.length, m = rows[0]?.[which]?.length ?? 0
  useEffect(() => {
    const c = ref.current
    if (!c || !n || !m) return
    c.width = m; c.height = n
    const ctx = c.getContext('2d')
    if (!ctx) return
    const img = ctx.createImageData(m, n)
    rows.forEach((r, i) => r[which].forEach((v, j) => {
      const [R, G, B] = Number.isFinite(v) ? rgb(v) : [153, 153, 153]
      const k = (i * m + j) * 4
      img.data[k] = R; img.data[k + 1] = G; img.data[k + 2] = B; img.data[k + 3] = 255
    }))
    ctx.putImageData(img, 0, 0)
  }, [rows, which, n, m])
  return <canvas ref={ref} data-testid={testid} style={{ width: '100%', height: '100%', imageRendering: 'pixelated', display: 'block' }} />
}

/** A verdict as the block gave it: tested or not (and why), beyond noise or not, the colour check. */
export function CycleVerdictBadge({ v, testid }: { v: CycleVerdict | null; testid?: string }) {
  if (!v) return <span className="k-badge t-grey" data-testid={testid} data-verdict="none">no verdict</span>
  if (!v.tested) return <span className="k-badge t-grey" data-testid={testid} data-verdict="untested" title={v.reason ?? ''}>untested</span>
  if (v.background_colour_mismatch) return <span className="k-badge t-grey" data-testid={testid} data-verdict="colour-mismatch" title="the chain's background differs in colour from the quiet margins: beyond the margins, not beyond its own noise">background of another colour</span>
  if (v.beyond_noise) return <span className="k-badge t-green" data-testid={testid} data-verdict="beyond" title={`eq. 17 below every background draw and more than the block's spread margin below their median${v.z != null ? ` (z ${v.z.toFixed(1)})` : ''}`}>beyond noise</span>
  return <span className="k-badge t-amber" data-testid={testid} data-verdict="noise-like" title={v.z != null ? `z ${v.z.toFixed(1)}` : ''}>no better than noise</span>
}

function groupKeyOf(seqs: CycleSequence[], seq: string | number, g: number): string {
  const s = seqs.find(q => String(q.key) === String(seq))
  return s?.groups.find(x => x.group === g)?.key ?? String(g)
}

function Exemplar({ ex, recordingId, unit }: { ex: CycleExemplar; recordingId: number; unit: string }) {
  const [tr, setTr] = useState<SlideTrace | null>(null)
  useEffect(() => {
    let alive = true
    setTr(null)
    loadWindow(recordingId, ex.start_s, ex.end_s, 400).then(t => { if (alive) setTr(t) }, e => { if (alive) setTr({ t: [], v: [], decimated: false, nSource: 0, error: String(e?.message ?? e) }) })
    return () => { alive = false }
  }, [recordingId, ex.start_s, ex.end_s])
  const dom = tr ? measuredDomain(tr.v) : null
  const H = 64
  const colour = familyColour(ex.group ?? 1)
  const marked = ex.group_key.includes('~')
  return (
    <div className="k-slide" style={{ borderColor: colour }} data-testid={`cycle-exemplar-${ex.key}`}>
      <div className="r1"><b style={{ color: colour }}>{ex.group_key}</b><span>event {ex.event}</span></div>
      <div style={{ display: 'flex', gap: 2 }}>
        {!tr ? <div className="skeleton" style={{ height: H, flex: 1, borderRadius: 5 }} />
          : tr.error || !dom ? <div className="k-slide-note" style={{ height: H }}>{tr.error ?? 'no finite samples in this cycle'}</div>
            : <><EventTrace trace={tr} domain={dom} event={{ id: `cy${ex.key}`, title: `${ex.group_key} medoid cycle`, sort: {} }} height={H} colour={colour} /><ScaleBar domain={dom} height={H} unit={unit} /></>}
      </div>
      <div className="facts">{fmtHours(ex.start_s, 3)} + {fmtDuration(ex.end_s - ex.start_s)}{marked ? ' · marked: read its rhythm with care' : ''}</div>
    </div>
  )
}

export function CycleStack({ p, recordingId, unit }: { p: SpansetPayload; recordingId: number; unit: string }) {
  const st = cycleStackOf(p)!
  const seqs = p.cycle_sequences ?? []
  const rows = useMemo(() => [...st.rows].sort((a, b) => a.start_s - b.start_s), [st.rows])
  // the block's change points (absolute seconds) placed between the rows they fall at — read, not recomputed
  const cuts = useMemo(() => {
    const abs = rows.map(r => st.span_start_s + r.start_s)
    const out: number[] = []
    for (const cp of seqs.flatMap(s => s.change_points_s)) {
      let best = -1, d = Infinity
      abs.forEach((a, i) => { const e = Math.abs(a - cp); if (e < d) { d = e; best = i } })
      if (best >= 0 && !out.includes(best)) out.push(best)
    }
    return out
  }, [rows, seqs, st.span_start_s])
  const n = rows.length
  const H = Math.max(80, Math.min(360, n * ROW_H_MAX))
  const rowPct = (i: number) => `${(i / Math.max(1, n)) * 100}%`
  if (!n) return <div className="muted mono small" data-testid="cycle-stack" data-state="empty">no cycle to stack · {Object.entries(p.cycle_omitted ?? {}).map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`).join(' · ') || 'the chain held no two consecutive events'}</div>
  const panel = (which: 'before' | 'after', title: string, testid: string) => (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div className="mono small" style={{ color: 'var(--text-2)', marginBottom: 2 }}>{title}</div>
      <div style={{ position: 'relative', height: H, border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
        <StackCanvas rows={rows} which={which} testid={testid} />
        {cuts.map(i => <div key={i} data-testid="cycle-change-point" title={`the block's change point: the shape changes at cycle ${i + 1} (${fmtHours(st.span_start_s + rows[i].start_s, 2)})`} style={{ position: 'absolute', left: 0, right: 0, top: rowPct(i), height: 0, borderTop: '2px solid var(--amber)' }} />)}
      </div>
    </div>
  )
  return (
    <div className="stack" style={{ gap: 8, marginBottom: 14 }} data-testid="cycle-stack" data-n-rows={n}>
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Every cycle, stacked</h3>
        <span className="sg">{n} of {st.n_cycles} cycles{st.sampled ? ' (a seeded sample)' : ''} · one row per cycle, earliest at the top · each stretched to one length and z-normalised · amber lines are the block's change points</span>
        <InfoTip title="Reading the stack">Each row is one drop-to-drop cycle, its drift removed by the block, stretched to {st.n_points} points and z-normalised (blue below the cycle's mean, amber above). Left: as cut. Right: each cycle shifted onto its group's medoid. A shape that changes partway through the chain shows as a change of pattern at an amber line; the strip on the right says which group each cycle is in.</InfoTip>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'stretch' }}>
        {panel('before', 'before alignment', 'cycle-stack-before')}
        {panel('after', 'after alignment (onto the group medoid)', 'cycle-stack-after')}
        <div style={{ width: 14 }}>
          <div className="mono small" style={{ color: 'var(--text-2)', marginBottom: 2 }}>&nbsp;</div>
          <div data-testid="cycle-group-strip" style={{ height: H, display: 'flex', flexDirection: 'column', border: '1px solid var(--border)', borderRadius: 3, overflow: 'hidden' }}>
            {rows.map((r, i) => <div key={i} style={{ flex: 1, background: familyColour(r.group) }} title={`cycle ${i + 1} · ${groupKeyOf(seqs, r.sequence, r.group)} · ${fmtHours(st.span_start_s + r.start_s, 2)} + ${fmtDuration(r.length_s)}`} />)}
          </div>
        </div>
      </div>
      <div className="bp-legend" style={{ paddingLeft: 0 }}>
        <span><i style={{ background: 'rgb(10,132,255)' }} />below the cycle's mean</span>
        <span><i style={{ background: 'rgb(255,144,12)' }} />above</span>
        <span><i style={{ background: 'var(--amber)' }} />the block's change point</span>
        {[...new Set(rows.map(r => `${r.sequence}|${r.group}`))].map(k => { const [s, g] = k.split('|'); return <span key={k}><i style={{ background: familyColour(+g) }} />{groupKeyOf(seqs, s, +g)}</span> })}
      </div>
      <CycleVerdicts seqs={seqs} />
      <CycleExemplars ex={p.cycle_exemplars ?? []} recordingId={recordingId} unit={unit} />
    </div>
  )
}

function CycleVerdicts({ seqs }: { seqs: CycleSequence[] }) {
  const th = { textAlign: 'left' as const, padding: '2px 8px', fontWeight: 500, color: 'var(--text-2)' }
  const td = { padding: '2px 8px', verticalAlign: 'top' as const }
  return (
    <div data-testid="cycle-verdicts">
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Each shape against the recording's quiet stretches</h3>
        <span className="sg">the block's own verdicts · σ² first, eq. 17 beside it (eq. 17 and σ² must both beat the background for an unmarked key)</span>
      </div>
      <table className="mono" style={{ borderCollapse: 'collapse', fontSize: 11.5 }}>
        <thead><tr><th style={th}>sequence · group</th><th style={th}>cycles</th><th style={th}>verdict</th><th style={th}>σ²</th><th style={th}>eq. 17</th><th style={th}>floor · half back</th><th style={th}>notes</th></tr></thead>
        <tbody>
          {seqs.map(s => (
            <Fragment key={`s${s.key}`}>
              <tr data-testid={`cycle-sequence-${s.key}`} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={td}><b>sequence {String(s.key)}</b> · K = {s.k ?? '—'}</td>
                <td style={{ ...td, textAlign: 'right' }}>{s.n_used ?? 0} of {s.n_cycles ?? 0}</td>
                <td style={td}><CycleVerdictBadge v={s.whole_verdict} testid={`cycle-whole-verdict-${s.key}`} /></td>
                <td style={td}>{f2(s.whole_scores.squared)}</td>
                <td style={td}>{f2(s.whole_scores.eq17)}</td>
                <td style={td} />
                <td style={{ ...td, color: 'var(--text-2)' }}>{[
                  s.k_null?.source ? `split tested against the ${s.k_null.source} null` : '', s.k_note ?? '',
                  s.change_points_s.length ? `${s.change_points_s.length} change point${s.change_points_s.length === 1 ? '' : 's'}${s.order_test?.p != null ? ` · order test p ${s.order_test.p.toFixed(3)} (order, not shape)` : ''}` : '',
                  s.whole_verdict && !s.whole_verdict.tested ? s.whole_verdict.reason ?? '' : '',
                  s.omitted && Object.keys(s.omitted).length ? `left out: ${Object.entries(s.omitted).map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`).join(', ')}` : '',
                ].filter(Boolean).join(' · ')}</td>
              </tr>
              {s.groups.map(g => (
                <tr key={`g${s.key}-${g.group}`} data-testid={`cycle-group-${g.key}`}>
                  <td style={{ ...td, paddingLeft: 20 }}><i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 2, background: familyColour(g.group), marginRight: 5 }} />{g.key}</td>
                  <td style={{ ...td, textAlign: 'right' }}>{g.size}</td>
                  <td style={td}><CycleVerdictBadge v={g.verdict} testid={`cycle-group-verdict-${g.key}`} /></td>
                  <td style={td}>{f2(g.scores.squared)}</td>
                  <td style={td}>{f2(g.scores.eq17)}</td>
                  <td style={td}>{f2(g.floor_frac_median)} · {f2(g.half_recovery_frac_median)}</td>
                  <td style={{ ...td, color: 'var(--text-2)' }}>{g.length_s_median != null ? `median cycle ${fmtDuration(g.length_s_median)}` : ''}</td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CycleExemplars({ ex, recordingId, unit }: { ex: CycleExemplar[]; recordingId: number; unit: string }) {
  if (!ex.length) return <div className="muted mono small" data-testid="cycle-exemplars">the block named no medoid cycle (no group was made)</div>
  return (
    <div data-testid="cycle-exemplars">
      <div className="bp-card-title"><h3 style={{ fontSize: 13 }}>Each group's medoid cycle</h3>
        <span className="sg">a member, never an average · drawn from the recording · each on its own y, sizes on the scale bars</span>
        <InfoTip title="Which cycle">{ex[0].rule}</InfoTip>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(4, ex.length)}, minmax(0, 1fr))`, gap: 8 }}>
        {ex.map(e => <Exemplar key={e.key} ex={e} recordingId={recordingId} unit={unit} />)}
      </div>
    </div>
  )
}
