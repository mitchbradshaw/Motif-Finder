/* discovery.stages — frame discovery-3b. One disagreement window pushed through both chains (§7.8): two columns of
 * stage cards aligned by role, each badged identical / differs / A only / absent, and a role × A × B table of the
 * numbers behind the pictures. The stepper bar names the first stage whose output differs — not a causal claim. */
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { Button, EmptyState, Icon, InfoTip, Pager, Popover, ProgressBar, cx, forceSim, useNotWired, useQueryState, useSim } from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { useSize } from '../charts/useSize'
import {
  ROLES, getCompare, getStagesWindow,
  type CompareData, type Disagreement, type Role, type StageCell, type StageThumb, type StagesWindow,
} from '../api/discovery'
import { DiscoveryToolbar, LoadFailed, Loading, NullChip } from './chrome'
import { RunGlyph } from './glyphs'
import { A_COLOUR, B_COLOUR, THRESH_COLOUR, type OnlyFilter } from './ComparePage'
import { useDiscovery } from './session'

const RERUN = 'discovery.stages.rerun'
const THUMB_H: Record<Role, number> = { Source: 46, Preprocess: 56, 'Score / estimate': 74, Encode: 28, Detect: 66 }

export function StagesPage() {
  const dx = useDiscovery()
  const [aQ] = useQueryState('a', 'drop_motifs9')
  const [bQ] = useQueryState('b', 'seed_F03_native')
  const [only, setOnly] = useQueryState<OnlyFilter>('only', 'a')
  const [iQ, setIQ] = useQueryState('i', '7')
  const [stateQ] = useQueryState('state', '')
  const notWired = useNotWired()
  const channels = dx.scope?.channels ?? []
  const section = dx.scope?.section ?? [0, 0] as [number, number]
  const runA = dx.runs.find(r => r.key === aQ) ?? null
  const runB = dx.runs.find(r => r.key === bQ) ?? null
  const valid = !!runA && !!runB && aQ !== bQ
  const cmp = useSourced(
    () => valid ? getCompare(aQ, bQ, channels, section) : Promise.resolve({ data: null as CompareData | null, source: 'demo' as const }),
    [valid, aQ, bQ, channels.join(','), section.join(',')],
  )
  const list = useMemo(() => {
    const all = cmp.data?.disagreements ?? []
    return only === 'all' ? all : all.filter(d => d.kind === (only === 'a' ? 'only A' : 'only B'))
  }, [cmp.data, only])
  const i = Math.min(Math.max(1, parseInt(iQ, 10) || 1), Math.max(1, list.length))
  const current: Disagreement | null = list[i - 1] ?? null
  const win = useSourced(
    () => current ? getStagesWindow(aQ, bQ, current, i, list.length) : Promise.resolve({ data: null as StagesWindow | null, source: 'demo' as const }),
    [aQ, bQ, current?.detection, i, list.length],
  )
  const back = `discovery/compare?a=${encodeURIComponent(aQ)}&b=${encodeURIComponent(bQ)}&only=${only}&i=${i}`

  // stepping re-runs both chains on the new 40 s window (toolbar: ≈ 1 s re-run on 40 s) — not on first paint
  const rerun = useSim(RERUN)
  const lastWindow = useRef<string | null>(null)
  useEffect(() => {
    const det = current?.detection ?? null
    if (!det) return
    if (lastWindow.current === null) { lastWindow.current = det; return }   // the window we arrived on is already computed
    if (lastWindow.current !== det) { lastWindow.current = det; rerun.start({ steps: ['re-run on 40 s'], stepMs: 900, queuedMs: 120 }) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.detection])
  // deep link ?state=rerun holds the page in the re-running state the stepper shows for about a second
  useEffect(() => {
    if (stateQ === 'rerun') forceSim(RERUN, { status: 'running', steps: ['re-run on 40 s'], step: 0, fraction: 0.4, startedAt: Date.now() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ])

  const swap = () => {
    const url = `discovery/compare/stages?a=${encodeURIComponent(bQ)}&b=${encodeURIComponent(aQ)}&only=${only === 'a' ? 'b' : only === 'b' ? 'a' : 'all'}&i=${i}`
    navigate(url)
  }

  return (
    <>
      <Header workspace="Discovery" page="Compare" subtitle="every stage · one window" demo={dx.demo} />
      <div className="k-page dsc-page" data-testid="discovery-stages-page">
        <div className="k-page-inner" style={{ maxWidth: 1376, gap: 12 }}>
          {dx.error && <LoadFailed what="the Discovery session" error={dx.error} onRetry={dx.reload} />}
          {dx.loading && !dx.error && <Loading height={600} label="loading the window" />}
          {dx.scope && (
            <>
              <DiscoveryToolbar dx={dx}
                left={<Button variant="link" icon="chevron-left" onClick={() => navigate(back)} testid="back-to-compare">compare</Button>}
                right={
                  <>
                    <NullChip dx={dx} />
                    <span className="dsc-cost" data-testid="rerun-chip" title="stepping re-runs both chains on the new window; results for this one are already in"><Icon name="hourglass" size={12} /><b>≈ 1 s</b> <span className="muted">re-run on 40 s</span></span>
                    <Button icon="shuffle" onClick={swap} disabled={!valid} disabledReason={valid ? undefined : 'pick two runs first'} testid="swap-ab">Swap A / B</Button>
                  </>
                } />
              {!valid ? (
                <EmptyState icon="compare" bordered testid="stages-empty"
                  title={aQ === bQ ? 'Pick two different runs to compare' : 'Pick two runs in the runs list to compare'}
                  caption="this page walks one disagreement between two runs through both chains"
                  action={<Button icon="chevron-left" onClick={() => navigate('discovery/runs')}>all runs</Button>} />
              ) : cmp.error ? <LoadFailed what="the comparison" error={cmp.error} onRetry={cmp.reload} />
                : !cmp.data ? <Loading height={520} label="reading both runs" />
                  : !current ? (
                    <EmptyState icon="check-circle" bordered testid="stages-none" title="No disagreement in this filter" caption="A and B agree everywhere here"
                      action={<Button icon="chevron-left" onClick={() => navigate(back)}>compare</Button>} />
                  ) : (
                    <>
                      <StepBar d={current} i={i} of={list.length} onStep={p => setIQ(String(p))} only={only} onOnly={v => { setOnly(v); setIQ('1') }}
                        firstDiffering={win.data?.firstDiffering ?? null} counts={{ all: cmp.data.disagreements.length, a: cmp.data.disagreements.filter(x => x.kind === 'only A').length }} />
                      {win.error ? <LoadFailed what="this window" error={win.error} onRetry={win.reload} />
                        : !win.data ? <Loading height={520} label="pushing the window through both chains" />
                          : (<StageColumns w={win.data} a={aQ} b={bQ} busy={rerun.busy} onAnalyse={(run, ch) => { navigate('analyse/chain'); notWired(`open ${run} on ${ch} ${(current.atH - 0.006).toFixed(2)}–${(current.atH + 0.006).toFixed(2)} h in Analyse`) }} />)}
                    </>
                  )}
            </>
          )}
        </div>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ stepper bar */

function StepBar({ d, i, of, onStep, only, onOnly, firstDiffering, counts }: {
  d: Disagreement; i: number; of: number; onStep: (p: number) => void; only: OnlyFilter; onOnly: (v: OnlyFilter) => void
  firstDiffering: Role | null; counts: { all: number; a: number }
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  return (
    <section className="k-card dsc-stg-bar" data-testid="step-bar">
      <Pager page={i} pageCount={Math.max(1, of)} onPage={onStep} label="disagreement" testid="stage-pager" />
      <b className="mono">{d.atH.toFixed(1)} h · {d.channel} · 40 s</b>
      <span className={cx('mono small', d.kind === 'only A' ? 'blue' : 'purple')} data-testid="step-kind">{d.kind} fired</span>
      <span className="muted small mono">of {counts.all} disagreements{only !== 'all' && ` · ${only === 'a' ? `only A ${counts.a}` : `only B ${counts.all - counts.a}`}`}</span>
      <button type="button" className="k-badge t-grey dsc-stg-filter" onClick={() => onOnly(only === 'all' ? 'a' : 'all')} data-testid="stage-filter" title="switch between every disagreement and this side only">
        {only === 'all' ? 'all' : only === 'a' ? 'only A' : 'only B'}
      </button>
      <span className="k-spacer" />
      <button ref={ref} type="button" className="k-badge t-amber" onClick={() => setOpen(o => !o)} data-testid="first-differing">
        first stage whose output differs · {firstDiffering ?? '—'}
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} placement="bottom-end" title="First differing stage" width={330} testid="first-differing-popover">
        The first stage whose output differs here. This is not a causal claim: a later stage can differ for its own reasons.
      </Popover>
    </section>
  )
}

/* ------------------------------------------------------------------ the two columns */

function StageColumns({ w, a, b, busy, onAnalyse }: { w: StagesWindow; a: string; b: string; busy: boolean; onAnalyse: (run: string, channel: string) => void }) {
  const [hover, setHover] = useState<Role | null>(null)
  const rows = ROLES.map((role, i) => ({ role, a: w.a[i], b: w.b[i] }))
  return (
    <>
      <div className={cx('dsc-stg-grid', busy && 'busy')} data-busy={String(busy)} data-testid="stage-columns">
        <ColumnHead side="A" run={a} subtitle={w.aSubtitle} onAnalyse={() => onAnalyse(a, w.d.channel)} />
        <ColumnHead side="B" run={b} subtitle={w.bSubtitle} onAnalyse={() => onAnalyse(b, w.d.channel)} />
        {rows.map(r => (
          <Fragment key={r.role}>
            <StageCardView cell={r.a} side="A" run={a} hi={hover === r.role} onHover={setHover} />
            <StageCardView cell={r.b} side="B" run={b} hi={hover === r.role} onHover={setHover} />
          </Fragment>
        ))}
        {busy && <div className="dsc-stg-veil" data-testid="stage-rerun"><div className="dsc-stg-veil-box"><ProgressBar indeterminate size="sm" width={140} labelPosition="none" /><span className="mono small">re-running both chains on this window</span></div></div>}
      </div>
      <DecidedTable w={w} a={a} b={b} hover={hover} onHover={setHover} />
    </>
  )
}

function ColumnHead({ side, run, subtitle, onAnalyse }: { side: 'A' | 'B'; run: string; subtitle: string; onAnalyse: () => void }) {
  return (
    <div className="dsc-stg-colhead" data-testid={`column-head-${side}`}>
      <i className={cx('dsc-ab', side.toLowerCase())}>{side}</i>
      <b>{run === 'human' ? 'human annotations' : run}</b>
      <span className="muted small mono">{subtitle}</span>
      <span className="k-spacer" />
      <Button variant="link" size="sm" icon="external" onClick={onAnalyse} testid={`open-analyse-${side}`}>Open in Analyse</Button>
    </div>
  )
}

const BADGE_TONE: Record<StageCell['badge'], string> = { identical: 't-green', differs: 't-amber', 'A only': 't-amber', 'B only': 't-amber', absent: 't-grey' }

function StageCardView({ cell, side, run, hi, onHover }: { cell: StageCell; side: 'A' | 'B'; run: string; hi: boolean; onHover: (r: Role | null) => void }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const attention = cell.badge === 'differs' || cell.badge === 'A only' || cell.badge === 'B only'
  const tid = `stage-card-${side}-${cell.role.replace(/\W+/g, '-')}`
  return (
    <section className={cx('dsc-stg-card', attention && 'attention', cell.badge === 'absent' && 'absent', hi && 'hi')}
      onPointerEnter={() => onHover(cell.role)} onPointerLeave={() => onHover(null)} data-testid={tid} aria-label={`${cell.role} ${side}`}>
      <div className="dsc-stg-head">
        {cell.cell ? (
          <button ref={ref} type="button" className="dsc-stg-title" onClick={() => setOpen(o => !o)} aria-expanded={open} title="the parameters this stage ran with">
            <span className="muted mono small">{cell.role} {cell.cell.index ?? ''}</span>
            <RunGlyph kind={cell.cell.glyph} width={30} height={19} />
            <b>{cell.cell.name}</b>
            <span className="muted mono small">{cell.cell.signature}</span>
          </button>
        ) : (
          <span className="dsc-stg-title"><span className="muted mono small">{cell.role}</span><b className="muted">no {cell.role} stage</b></span>
        )}
        <span className="k-spacer" />
        <span className={cx('k-badge', BADGE_TONE[cell.badge])}>{cell.badge}</span>
      </div>
      {cell.cell && (
        <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title={`${cell.cell.index ? `${cell.cell.index} ` : ''}${cell.cell.name}`} subtitle={`${cell.role} · ${run}`} width={320} testid="stage-params-popover">
          <div className="dsc-pop-list mono small">
            <div className="row between"><span className="muted">signature</span><b>{cell.cell.signature}</b></div>
            <div className="row between"><span className="muted">parameters</span><b>{cell.cell.param || '—'}</b></div>
            <div className="row between"><span className="muted">decided here</span><b>{cell.decided}</b></div>
            <div className="muted">read-only — this run's chain is locked.</div>
          </div>
        </Popover>
      )}
      <div className="dsc-stg-thumb" style={{ height: THUMB_H[cell.role] }}><Thumb thumb={cell.thumb} height={THUMB_H[cell.role]} /></div>
      <div className="dsc-stg-cap mono small">{cell.badge === 'absent' ? cell.absentNote ?? cell.caption : cell.caption}</div>
    </section>
  )
}

/* ------------------------------------------------------------------ chain-row thumbnails (§6.8 contract) */

const SYMBOL_RAMP = ['#8B1D1D', '#C9DCF5', '#A8C8EE', '#DCE3EA', '#F4CE93', '#EFA53C']

function Thumb({ thumb, height }: { thumb: StageThumb; height: number }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const W = size.width
  return (
    <div ref={ref} className="dsc-thumb-box">
      {W > 0 && (() => {
        switch (thumb.kind) {
          case 'absent': return <div className="dsc-thumb-absent mono small">— nothing to compare in this role</div>
          case 'trace': return <TraceThumb w={W} h={height} values={thumb.values} ghost={thumb.ghost} stroke={thumb.stroke} span={thumb.span} emptyTrack={thumb.emptyTrack} />
          case 'segments': return <SegmentsThumb w={W} h={height} values={thumb.values} cut={thumb.cut} />
          case 'symbols': return <SymbolsThumb w={W} h={height} values={thumb.values} lowRun={thumb.lowRun} />
          case 'distance': return <DistanceThumb w={W} h={height} values={thumb.values} threshold={thumb.threshold} minIndex={thumb.minIndex} minValue={thumb.minValue} isSeed={thumb.isSeed} />
        }
      })()}
    </div>
  )
}

/* A stage's output carries non-finite values on purpose: a matrix profile is
 * NaN-padded to the span length, and the wire spells that null, which the
 * adapter turns back into NaN. Both the domain and the path have to know —
 * Math.min over an array holding one NaN is NaN, every y becomes NaN, and the
 * browser rejects the whole path with "attribute d: Expected number". The
 * curve breaks where the values do instead. */
const finiteOf = (vals: number[]) => vals.filter(Number.isFinite)
const domainOf = (vals: number[]) => {
  const f = finiteOf(vals)
  if (!f.length) return [0, 1] as [number, number]
  const lo = Math.min(...f), hi = Math.max(...f), p = (hi - lo) * 0.14 || 0.05
  return [lo - p, hi + p] as [number, number]
}
/** A polyline that lifts the pen at every non-finite value. */
const brokenPath = (vals: number[], x: (i: number) => number, y: (v: number) => number) => {
  let d = '', pen = false
  vals.forEach((v, i) => {
    if (!Number.isFinite(v)) { pen = false; return }
    d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`
    pen = true
  })
  return d
}

function TraceThumb({ w, h, values, ghost, stroke, span, emptyTrack }: { w: number; h: number; values: number[]; ghost?: number[]; stroke?: string; span?: [number, number]; emptyTrack?: boolean }) {
  const trackH = span || emptyTrack ? 8 : 0
  const plotH = h - trackH - (trackH ? 4 : 0)
  const [lo, hi] = domainOf([...values, ...(ghost ?? [])])
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * (w - 2) + 1
  const y = (v: number) => 2 + (1 - (v - lo) / (hi - lo)) * (plotH - 4)
  const path = (vals: number[]) => brokenPath(vals, x, y)
  const sx = span ? [x(span[0]), x(span[1])] : null
  return (
    <svg width={w} height={h} role="img" aria-label="signal in this window">
      {sx && <rect x={sx[0]} y={1} width={Math.max(2, sx[1] - sx[0])} height={plotH - 1} fill={A_COLOUR} opacity={0.13} />}
      {ghost && <path d={path(ghost)} fill="none" stroke="var(--grey-300, #cbd2d9)" strokeWidth={1} />}
      <path d={path(values)} fill="none" stroke={stroke ?? 'var(--trace)'} strokeWidth={1.2} />
      {emptyTrack && <rect x={1} y={plotH + 4} width={w - 2} height={6} rx={3} fill="#eceef1" />}
      {sx && <rect x={sx[0]} y={plotH + 3} width={Math.max(2, sx[1] - sx[0])} height={5} rx={2.5} fill={A_COLOUR} />}
    </svg>
  )
}

function SegmentsThumb({ w, h, values, cut }: { w: number; h: number; values: number[]; cut: number }) {
  const n = values.length
  const max = Math.max(cut * 1.9, ...finiteOf(values).map(Math.abs))
  const mid = h / 2
  const bw = Math.max(2, (w - 2) / n - 2)
  const y = (v: number) => mid - (v / max) * (mid - 8)
  return (
    <svg width={w} height={h} role="img" aria-label={`per-segment deviation against a ±${cut} mV cut`}>
      <line x1={0} x2={w} y1={y(cut)} y2={y(cut)} stroke="#111827" strokeWidth={0.8} />
      <line x1={0} x2={w} y1={y(-cut)} y2={y(-cut)} stroke={THRESH_COLOUR} strokeWidth={0.9} />
      <text x={w - 2} y={y(cut) - 3} textAnchor="end" className="dsc-axis-t">±{cut}</text>
      {values.map((v, i) => {
        const beyond = Math.abs(v) > cut
        const top = v >= 0 ? y(v) : mid
        return <rect key={i} x={1 + i * ((w - 2) / n)} y={top} width={bw} height={Math.max(1.5, Math.abs(y(v) - mid))} rx={1}
          fill={beyond ? '#8B1D1D' : v >= 0 ? '#BBD6F5' : '#F7C9A8'}><title>{`segment ${i + 1} · ${v.toFixed(3)} mV${beyond ? ' · beyond the cut' : ''}`}</title></rect>
      })}
    </svg>
  )
}

/** `lowRun` is null where the encoding found no run of lowest symbols: nothing is highlighted, and the
 *  label says so rather than shading an interval nobody found. */
function SymbolsThumb({ w, h, values, lowRun }: { w: number; h: number; values: number[]; lowRun: [number, number] | null }) {
  const n = values.length
  const cw = (w - 2) / n
  return (
    <svg width={w} height={h} role="img" aria-label={lowRun ? `SAX symbols, a run of ${lowRun[1] - lowRun[0]} lowest symbols at the fall` : 'SAX symbols, no run of lowest symbols here'}>
      {values.map((v, i) => (
        <rect key={i} x={1 + i * cw} y={2} width={Math.max(1.5, cw - 1.5)} height={h - 4} rx={1.5}
          fill={lowRun && i >= lowRun[0] && i < lowRun[1] ? SYMBOL_RAMP[0] : SYMBOL_RAMP[Math.max(1, Math.min(5, v))]}><title>{`symbol ${i + 1}: ${v}`}</title></rect>
      ))}
    </svg>
  )
}

/** A stage that emits no threshold (or no score at all) sends null for it: draw the curve without the
 *  line rather than a line at nothing. The cell's caption is the server's account of why. */
function DistanceThumb({ w, h, values, threshold, minIndex, minValue, isSeed }: { w: number; h: number; values: number[]; threshold: number | null; minIndex: number; minValue: number | null; isSeed: boolean }) {
  const scale = finiteOf(threshold != null ? [...values, threshold] : values)
  const lo = scale.length ? Math.min(...scale) : 0
  const hi = scale.length ? Math.max(...scale) : 1
  const pad = (hi - lo) * 0.2 || 0.2
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * (w - 2) + 1
  const y = (v: number) => 4 + (1 - (v - (lo - pad)) / ((hi + pad) - (lo - pad))) * (h - 14)
  return (
    <svg width={w} height={h} role="img" aria-label={`${isSeed ? 'distance profile' : 'score'} against its threshold`}>
      <path d={brokenPath(values, x, y)} fill="none" stroke={B_COLOUR} strokeWidth={1.2} />
      {threshold != null
        ? <>
          <line x1={0} x2={w} y1={y(threshold)} y2={y(threshold)} stroke={THRESH_COLOUR} strokeWidth={1.4} />
          <text x={w - 2} y={y(threshold) + 11} textAnchor="end" className="dsc-axis-t" style={{ fill: 'var(--muted)' }}>{isSeed ? `d ${threshold}` : `score ${threshold}`}</text>
        </>
        : <text x={w - 2} y={h - 3} textAnchor="end" className="dsc-axis-t" style={{ fill: 'var(--muted)' }}>no threshold</text>}
      {minValue != null && <>
        <circle cx={x(minIndex)} cy={y(minValue)} r={3} fill="#fff" stroke={B_COLOUR} strokeWidth={1.3} />
        <text x={x(minIndex) + 6} y={y(minValue) + 4} className="dsc-axis-t" style={{ fill: B_COLOUR }}>{isSeed ? minValue.toFixed(1) : minValue.toFixed(2)}</text>
      </>}
    </svg>
  )
}

/* ------------------------------------------------------------------ what each stage decided here */

function DecidedTable({ w, a, b, hover, onHover }: { w: StagesWindow; a: string; b: string; hover: Role | null; onHover: (r: Role | null) => void }) {
  const rows = ROLES.map((role, i) => ({ role, a: w.a[i], b: w.b[i] })).filter(r => r.role !== 'Source')
  return (
    <section className="k-card dsc-decided" data-testid="decided-table">
      <div className="dsc-card-head">
        <h3>What each stage decided here</h3>
        <InfoTip title="What each stage decided here">The numbers behind the pictures above — the same 40 s window, both runs. A tinted row is a role where the two runs' outputs differ.</InfoTip>
        <span className="muted small">same window, both runs</span>
      </div>
      <table className="dsc-decided-table">
        <thead>
          <tr>
            <th>role</th>
            <th style={{ color: A_COLOUR }}><i className="dsc-ab a">A</i> · {a === 'human' ? 'human annotations' : a}</th>
            <th style={{ color: B_COLOUR }}><i className="dsc-ab b">B</i> · {b === 'human' ? 'human annotations' : b}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const differs = r.a.badge !== 'identical' || r.b.badge !== 'identical'
            return (
              <tr key={r.role} className={cx(differs && 'differs', hover === r.role && 'hi')} onPointerEnter={() => onHover(r.role)} onPointerLeave={() => onHover(null)} data-testid={`decided-${r.role.replace(/\W+/g, '-')}`}>
                <th scope="row">{r.role}</th>
                <td className="mono">{r.a.decided}</td>
                <td className="mono">{r.b.decided}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
