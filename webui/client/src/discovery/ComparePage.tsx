/* discovery.compare — frame discovery-3. Two runs side by side (§7.7): what differs (chains aligned by role),
 * where A and B fire on one channel, set overlap at IoU ≥ 0.5, and a stepper through every disagreement with the
 * non-firing side's own score at that place. "Compare every stage" opens discovery.stages (3b). */
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  Button, Chip, Dropdown, EmptyState, Icon, InfoTip, Pager, Popover, Seg, StatTile, cx, useNotWired, useQueryState,
} from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { useSize } from '../charts/useSize'
import {
  ROLES, getChannelSignal, getCompare, getDisagreementWindow,
  type CompareData, type CompareSide, type Disagreement, type Role, type RoleCell,
} from '../api/discovery'
import { DiscoveryToolbar, LoadFailed, Loading, NullChip, RunsCard, ScopeCard } from './chrome'
import { RunGlyph } from './glyphs'
import { ViewPopover, parseView } from './SeedPage'
import { useDiscovery, type Discovery } from './session'

export const A_COLOUR = '#0A84FF', B_COLOUR = '#AF52DE', BOTH_COLOUR = '#9AA3AF', THRESH_COLOUR = '#E8900C'
export type OnlyFilter = 'all' | 'a' | 'b'

export function ComparePage() {
  const dx = useDiscovery()
  const [aQ, setAQ] = useQueryState('a', 'drop_motifs9')
  const [bQ, setBQ] = useQueryState('b', 'seed_F03_native')
  const [only, setOnlyQ] = useQueryState<OnlyFilter>('only', 'a')
  const [iQ, setIQ] = useQueryState('i', '7')
  const init = useRef(false)

  // the pick boxes in the runs card and the route are the same thing: the route seeds the picks on arrival,
  // and after that a pick (or an unpick) rewrites the route.
  const picksKey = dx.picks.join(',')
  useEffect(() => {
    if (!init.current) {
      init.current = true
      const want = [aQ, bQ].filter(k => k && k !== 'none')
      if (want.join(',') !== picksKey) dx.setPicks(want)
      return
    }
    setAQ(dx.picks[0] ?? 'none')
    setBQ(dx.picks[1] ?? 'none')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picksKey])

  const runA = dx.runs.find(r => r.key === aQ) ?? null
  const runB = dx.runs.find(r => r.key === bQ) ?? null
  const channels = dx.scope?.channels ?? []
  const section = dx.scope?.section ?? [0, 0] as [number, number]
  const valid = !!runA && !!runB && aQ !== bQ
  const cmp = useSourced(
    () => valid ? getCompare(aQ, bQ, channels, section) : Promise.resolve({ data: null as CompareData | null, source: 'demo' as const }),
    [valid, aQ, bQ, channels.join(','), section.join(',')],
  )
  const setOnly = (v: OnlyFilter) => { setOnlyQ(v); setIQ('1') }
  const list = useMemo(() => {
    const all = cmp.data?.disagreements ?? []
    return only === 'all' ? all : all.filter(d => d.kind === (only === 'a' ? 'only A' : 'only B'))
  }, [cmp.data, only])
  const i = Math.min(Math.max(1, parseInt(iQ, 10) || 1), Math.max(1, list.length))
  const current: Disagreement | null = list[i - 1] ?? null

  return (
    <>
      <Header workspace="Discovery" page="Compare" subtitle={valid ? `A ${runA!.label} · B ${runB!.label}` : 'pick two runs'} demo={dx.demo} />
      <div className="k-page dsc-page" data-testid="discovery-compare-page">
        <div className="k-page-inner" style={{ maxWidth: 1376, gap: 12 }}>
          {dx.error && <LoadFailed what="the Discovery session" error={dx.error} onRetry={dx.reload} />}
          {dx.loading && !dx.error && <Loading height={600} label="loading the comparison" />}
          {dx.scope && (
            <>
              <DiscoveryToolbar dx={dx}
                left={<Button variant="link" icon="chevron-left" onClick={() => navigate('discovery/runs')} testid="all-runs">all runs</Button>}
                right={
                  <>
                    <NullChip dx={dx} />
                    <Chip tone="grey" icon="database" testid="cached-chip">cached</Chip>
                    <InfoTip title="Cached">Both runs' results are cached; nothing re-runs to compare them. Stepping through disagreements re-reads one 40 s window at a time.</InfoTip>
                    <Button icon="shuffle" onClick={() => { setAQ(bQ); setBQ(aQ); dx.setPicks([bQ, aQ].filter(k => k && k !== 'none')) }}
                      disabled={!valid} disabledReason={valid ? undefined : 'pick two runs first'} testid="swap-ab">Swap A / B</Button>
                  </>
                } />
              <ScopeCard dx={dx} />
              {!dx.recording?.heldOut && (
                <div className="dsc-cols">
                  <RunsCard dx={dx} mode="compare" compareActive={valid} onAddTemplate={() => navigate('discovery/runs?modal=add-template')} />
                  <div className="dsc-right">
                    {!valid ? (
                      <EmptyState icon="compare" bordered testid="compare-empty"
                        title={aQ === bQ && runA ? 'Pick two different runs to compare' : dx.picks.length === 1 ? 'Pick a second run to compare' : 'Pick two runs in the runs list to compare'}
                        caption={aQ === bQ && runA ? 'A and B are the same run — its chain cannot differ from itself' : 'the pick boxes on the right of each run row choose A and B'}
                        action={<Button icon="chevron-left" onClick={() => navigate('discovery/runs')}>all runs</Button>} />
                    ) : cmp.error ? <LoadFailed what="the comparison" error={cmp.error} onRetry={cmp.reload} />
                      : !cmp.data ? <Loading height={520} label="comparing the two runs" />
                        : (
                          <>
                            <WhatDiffers data={cmp.data} />
                            <WhereFire dx={dx} data={cmp.data} current={current}
                              onJump={(d) => { const all = cmp.data!.disagreements; const kind: OnlyFilter = d.kind === 'only A' ? 'a' : 'b'; const within = all.filter(x => x.kind === d.kind); setOnlyQ(kind); setIQ(String(within.indexOf(d) + 1)) }} />
                            <SetOverlap data={cmp.data}
                              onSegment={(kind, channel) => {
                                if (kind === 'both') return
                                const want: OnlyFilter = kind === 'onlyA' ? 'a' : 'b'
                                const within = cmp.data!.disagreements.filter(d => d.kind === (want === 'a' ? 'only A' : 'only B'))
                                const at = channel === 'all channels' ? 0 : within.findIndex(d => d.channel === channel)
                                setOnlyQ(want); setIQ(String(Math.max(1, at + 1)))
                              }} />
                            <Disagreements data={cmp.data} a={aQ} b={bQ} only={only} setOnly={setOnly} list={list} i={i} setI={p => setIQ(String(p))} current={current} />
                          </>
                        )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ what differs */

export function WhatDiffers({ data }: { data: CompareData }) {
  const [pop, setPop] = useQueryState('popover', '')
  const ref = useRef<HTMLButtonElement>(null)
  const n = data.differing.length
  const attributable = n === 1
  return (
    <section className="k-card dsc-diffs" data-testid="what-differs" aria-label="What differs">
      <div className="dsc-card-head">
        <h3>What differs</h3>
        <InfoTip title="What differs">Both chains laid out in columns by role, so stages that do the same job line up. Identical stages are grey, differing stages amber, and an empty slot means that chain has no stage in that role.</InfoTip>
        <span className="muted small">stages aligned by role</span>
        <span className="k-spacer" />
        <button ref={ref} type="button" className={cx('k-badge', attributable ? 't-green' : 't-amber')} onClick={() => setPop(pop === 'roles' ? null : 'roles')} data-testid="roles-differ">
          {n} of {ROLES.length} role{n === 1 ? ' differs' : 's differ'}{attributable ? ' · attributable' : ''}
        </button>
        <Popover open={pop === 'roles'} onClose={() => setPop(null)} anchorRef={ref} placement="bottom-end" title="Differing roles" width={330} testid="roles-popover">
          {attributable
            ? <span>Exactly one role differs, so the difference in output can be attributed to that stage.</span>
            : <span>More than one role differs, so a difference in output cannot be attributed to any single stage. Step through a disagreement and open <b>Compare every stage</b> to see where the two chains part company in one window.</span>}
        </Popover>
      </div>
      <div className="dsc-diff-grid" role="table">
        <span />
        {ROLES.map(r => <span key={r} className="dsc-diff-col mono">{r}</span>)}
        {(['A', 'B'] as const).map(side => {
          const s: CompareSide = side === 'A' ? data.a : data.b
          return (
            <Fragment key={side}>
              <span className="dsc-diff-head">
                <i className={cx('dsc-ab', side.toLowerCase())}>{side}</i>
                <b className="mono" title={s.label}>{s.label.length > 15 ? `${s.label.slice(0, 13)}.` : s.label}</b>
              </span>
              {ROLES.map(role => <StageChip key={role} role={role} cell={s.cells[role]} run={s.label} differs={data.differing.includes(role)} side={side} other={(side === 'A' ? data.b : data.a).label} />)}
            </Fragment>
          )
        })}
      </div>
    </section>
  )
}

export function StageChip({ role, cell, run, differs, side, other }: { role: Role; cell: RoleCell | null; run: string; differs: boolean; side: 'A' | 'B'; other: string }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const notWired = useNotWired()
  if (!cell) return (
    <span className="dsc-stage empty mono" data-testid={`stage-${side}-${role.replace(/\W+/g, '-')}`} title={`${run} has no ${role} stage — ${other} does`}>
      <span className="dsc-stage-glyph">—</span><span className="dsc-stage-text"><b>—</b><span className="muted">no stage</span></span>
    </span>
  )
  return (
    <>
      <button ref={ref} type="button" className={cx('dsc-stage', differs && 'differs')} onClick={() => setOpen(o => !o)} data-testid={`stage-${side}-${role.replace(/\W+/g, '-')}`} aria-expanded={open} title={`${cell.name} · ${cell.signature}`}>
        <RunGlyph kind={cell.glyph} width={34} height={22} />
        <span className="dsc-stage-text"><b>{cell.short ?? cell.name}</b><span className={cx('mono', differs ? 'amber' : 'muted')}>{cell.param}</span></span>
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title={`${cell.index ? `${cell.index} ` : ''}${cell.name}`} subtitle={`${role} · ${run}`} width={320} testid="stage-popover">
        <div className="dsc-pop-list mono small">
          <div className="row between"><span className="muted">signature</span><b>{cell.signature}</b></div>
          <div className="row between"><span className="muted">parameters</span><b>{cell.param}</b></div>
          <div className="muted">locked here — parameters are edited in the chain this run came from.</div>
        </div>
        <Button variant="link" size="sm" icon="external" onClick={() => { navigate('analyse/chain'); notWired(`open ${run} in Analyse`) }} testid="stage-open-analyse">Open in Analyse</Button>
      </Popover>
    </>
  )
}

/* ------------------------------------------------------------------ where A and B fire */

function WhereFire({ dx, data, current, onJump }: { dx: Discovery; data: CompareData; current: Disagreement | null; onJump: (d: Disagreement) => void }) {
  const s = dx.scope!
  const [chQ, setChQ] = useQueryState('wch', 'CH4_A2')
  const [viewQ, setViewQ] = useQueryState('wview', `${s.section[0]}-${s.section[1]}`)
  const viewRef = useRef<HTMLButtonElement>(null)
  const [viewOpen, setViewOpen] = useState(false)
  const ch = s.channels.includes(chQ) ? chQ : s.channels[0]
  const view = parseView(viewQ, s.section)
  const sig = useSourced(() => getChannelSignal(ch, view), [ch, view.join(',')])
  const [ref, size] = useSize<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const W = size.width, labelW = 74, padR = 10
  const x = (h: number) => labelW + ((h - view[0]) / (view[1] - view[0])) * (W - labelW - padR)
  const inView = (h: number) => h >= view[0] && h <= view[1]
  const onlyA = data.disagreements.filter(d => d.kind === 'only A' && d.channel === ch && inView(d.atH))
  const onlyB = data.disagreements.filter(d => d.kind === 'only B' && d.channel === ch && inView(d.atH))
  const both = data.both.filter(e => e.channel === ch && inView(e.atH))
  const ticks = Array.from({ length: 7 }, (_, i) => view[0] + (i * (view[1] - view[0])) / 6)
  const tol = (view[1] - view[0]) / 120
  const nearest = hover == null ? null : (() => {
    const h = view[0] + ((hover - labelW) / (W - labelW - padR)) * (view[1] - view[0])
    const bothHit = both.find(e => Math.abs(e.atH - h) < tol)
    if (bothHit) return { h, kind: 'both fire' as const }
    const aHit = onlyA.find(d => Math.abs(d.atH - h) < tol)
    if (aHit) return { h, kind: 'only A fires' as const }
    const bHit = onlyB.find(d => Math.abs(d.atH - h) < tol)
    if (bHit) return { h, kind: 'only B fires' as const }
    return { h, kind: 'neither fires' as const }
  })()
  const TRACKS = { a: 104, b: 122, agree: 140 }
  return (
    <section className="k-card dsc-fire" data-testid="where-fire" aria-label="Where A and B fire">
      <div className="dsc-card-head">
        <h3>Where A and B fire</h3>
        <InfoTip title="Where A and B fire">The signal is drawn clean — no ticks or marks over it. Beneath it, on the same axis: A's detections, B's detections, and one agreement track (grey where both fire, blue only A, purple only B). The faint band is the disagreement the stepper is on.</InfoTip>
        <span className="k-spacer" />
        <span className="dsc-legend-row small mono">
          <span><i className="sw" style={{ background: BOTH_COLOUR }} />both</span>
          <span><i className="sw" style={{ background: A_COLOUR }} />only A</span>
          <span><i className="sw" style={{ background: B_COLOUR }} />only B</span>
        </span>
        <Dropdown prefix="channel" value={ch} onChange={v => setChQ(v)} options={s.channels.map(c => ({ value: c, label: c }))} size="sm" testid="fire-channel" />
        <button ref={viewRef} type="button" className="dsc-section-chip" onClick={() => setViewOpen(o => !o)} data-testid="fire-view">
          <span className="muted">view</span> {view[0].toFixed(0)}–{view[1].toFixed(0)} h <Icon name="chevron-down" size={11} />
        </button>
        <ViewPopover open={viewOpen} onClose={() => setViewOpen(false)} anchorRef={viewRef} view={view} section={s.section} minW={0.5} maxW={s.section[1] - s.section[0]}
          onApply={v => setViewQ(`${v[0].toFixed(1)}-${v[1].toFixed(1)}`)} />
      </div>
      <div className="dsc-fire-body" ref={ref}>
        {sig.error ? <LoadFailed what="the channel signal" error={sig.error} onRetry={sig.reload} /> : !sig.data || W === 0 ? <Loading height={200} /> : (() => {
          const vals = sig.data.values
          const n = vals.length
          const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * 0.12 || 0.1
          const sy = (v: number) => 14 + (1 - (v - (lo - pad)) / ((hi + pad) - (lo - pad))) * 74
          const hAt = (i: number) => view[0] + (i / Math.max(1, n - 1)) * (view[1] - view[0])
          const step = Math.max(1, Math.floor(n / Math.max(1, W - labelW)))
          let d = ''
          for (let i = 0; i < n; i += step) d += `${i ? 'L' : 'M'}${x(hAt(i)).toFixed(1)} ${sy(vals[i]).toFixed(1)}`
          const bandX = current && current.channel === ch && inView(current.atH) ? x(current.atH) : null
          return (
            <svg width={W} height={176} role="img" aria-label={`where A and B fire on ${ch}: ${onlyA.length} only A, ${both.length} both, ${onlyB.length} only B`}
              onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); const px = e.clientX - r.left; setHover(px >= labelW && px <= W - padR ? px : null) }}
              onPointerLeave={() => setHover(null)}>
              <text x={0} y={34} className="dsc-axis-t">signal</text>
              <text x={0} y={46} className="dsc-axis-t">{ch}</text>
              <text x={0} y={TRACKS.a + 9} className="dsc-axis-t">A</text>
              <text x={0} y={TRACKS.b + 9} className="dsc-axis-t">B</text>
              <text x={0} y={TRACKS.agree + 9} className="dsc-axis-t">agreement</text>
              <text x={labelW - 8} y={20} textAnchor="end" className="dsc-axis-t">{(hi + pad).toFixed(2)}</text>
              <text x={labelW - 8} y={90} textAnchor="end" className="dsc-axis-t">{(lo - pad).toFixed(2)} mV</text>
              {bandX != null && <rect x={bandX - 5} y={8} width={10} height={140} fill={A_COLOUR} opacity={0.1} data-testid="fire-band" />}
              <path d={d} fill="none" stroke="var(--trace)" strokeWidth={1.1} />
              {(['a', 'b', 'agree'] as const).map(k => <rect key={k} x={labelW} y={TRACKS[k]} width={Math.max(0, W - labelW - padR)} height={12} fill="#f3f4f6" rx={2} />)}
              {onlyA.map(t => <rect key={`a${t.detection}`} x={x(t.atH) - 1} y={TRACKS.a} width={2} height={12} fill={A_COLOUR}><title>{`${t.detection} · ${t.atH.toFixed(2)} h · only A fires`}</title></rect>)}
              {both.map((t, i) => <rect key={`ab${i}`} x={x(t.atH) - 1} y={TRACKS.a} width={2} height={12} fill={A_COLOUR} opacity={0.75}><title>{`${t.atH.toFixed(2)} h · both fire`}</title></rect>)}
              {onlyB.map(t => <rect key={`b${t.detection}`} x={x(t.atH) - 1} y={TRACKS.b} width={2} height={12} fill={B_COLOUR}><title>{`${t.detection} · ${t.atH.toFixed(2)} h · only B fires`}</title></rect>)}
              {both.map((t, i) => <rect key={`bb${i}`} x={x(t.atH) - 1} y={TRACKS.b} width={2} height={12} fill={B_COLOUR} opacity={0.75}><title>{`${t.atH.toFixed(2)} h · both fire`}</title></rect>)}
              {both.map((t, i) => <rect key={`g${i}`} x={x(t.atH) - 1} y={TRACKS.agree} width={2} height={12} fill={BOTH_COLOUR}><title>{`${t.atH.toFixed(2)} h · both fire · nothing to step through`}</title></rect>)}
              {onlyA.map(t => <rect key={`ga${t.detection}`} x={x(t.atH) - 1.5} y={TRACKS.agree} width={3} height={12} fill={A_COLOUR} style={{ cursor: 'pointer' }} onClick={() => onJump(t)} data-testid="agree-tick"><title>{`${t.detection} · ${t.atH.toFixed(2)} h · only A — click to step here`}</title></rect>)}
              {onlyB.map(t => <rect key={`gb${t.detection}`} x={x(t.atH) - 1.5} y={TRACKS.agree} width={3} height={12} fill={B_COLOUR} style={{ cursor: 'pointer' }} onClick={() => onJump(t)} data-testid="agree-tick"><title>{`${t.detection} · ${t.atH.toFixed(2)} h · only B — click to step here`}</title></rect>)}
              <line x1={labelW} x2={W - padR} y1={160} y2={160} stroke="var(--border)" />
              {ticks.map((t, i) => <text key={i} x={x(t)} y={172} textAnchor={i === 0 ? 'start' : i === 6 ? 'end' : 'middle'} className="dsc-axis-t">{i === 0 || i === 6 ? `${t.toFixed(0)} h` : t.toFixed(0)}</text>)}
              {hover != null && nearest && (
                <g pointerEvents="none">
                  <line x1={hover} x2={hover} y1={8} y2={152} stroke="var(--blue)" strokeOpacity={0.55} strokeDasharray="3 3" />
                  <g transform={`translate(${Math.min(hover + 8, W - 150)},${28})`}>
                    <rect x={0} y={-12} width={140} height={20} rx={5} fill="#111827" />
                    <text x={8} y={2} className="dsc-axis-t" style={{ fill: '#fff' }}>{nearest.h.toFixed(1)} h ● {nearest.kind}</text>
                  </g>
                </g>
              )}
            </svg>
          )
        })()}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ set overlap */

function SetOverlap({ data, onSegment }: { data: CompareData; onSegment: (kind: 'onlyA' | 'both' | 'onlyB', channel: string) => void }) {
  const rows = [data.total, ...data.overlap]
  const max = Math.max(...rows.map(r => r.onlyA + r.both + r.onlyB), 1)
  const pct = (v: number | null) => v == null ? '—' : `${Math.round(v * 100)} %`
  return (
    <section className="k-card dsc-overlap" data-testid="set-overlap" aria-label="Set overlap">
      <div className="dsc-card-head">
        <h3>Set overlap</h3>
        <InfoTip title="Set overlap">Two detections count as the same event when their spans overlap by IoU ≥ 0.5 (Settings › Analysis defaults). Everything else is only-A or only-B and lands in the stepper below.</InfoTip>
        <span className="muted small">matched at IoU ≥ 0.5</span>
      </div>
      <div className="dsc-overlap-body">
        <div className="dsc-overlap-rows">
          {rows.map((r, i) => {
            const total = r.onlyA + r.both + r.onlyB
            return (
              <div key={r.channel} className="dsc-overlap-row" data-testid={`overlap-${r.channel.replace(/\s+/g, '-')}`}>
                <span className={cx('mono small', i === 0 && 'strong')}>{r.channel}</span>
                <span className="dsc-overlap-bar" style={{ width: `${(total / max) * 100}%` }}>
                  {([['onlyA', r.onlyA, A_COLOUR], ['both', r.both, BOTH_COLOUR], ['onlyB', r.onlyB, B_COLOUR]] as const).map(([kind, v, colour]) => v > 0 && (
                    <button key={kind} type="button" className="dsc-overlap-seg" style={{ flexGrow: v, background: colour }}
                      onClick={() => onSegment(kind, r.channel)} data-testid={`overlap-seg-${kind}`}
                      title={kind === 'both' ? `${v} detections both runs found · both fire here, nothing to step` : `${v} found by ${kind === 'onlyA' ? 'A only' : 'B only'} — step through them`}>{v}</button>
                  ))}
                </span>
              </div>
            )
          })}
        </div>
        <div className="dsc-overlap-tiles">
          <StatTile label="A precision" value={pct(data.a.precision)} caption={`${data.a.reviewed} reviewed`} tone="blue" variant="card"
            info={<InfoTip title="Precision">Of the detections a human has reviewed, the share judged interesting. It exists only where reviewed hours overlap the run — a run with no reviewed overlap shows —.</InfoTip>} />
          <StatTile label="B precision" value={pct(data.b.precision)} caption={`${data.b.reviewed} reviewed`} tone="purple" variant="card" />
          <StatTile label="× null" value={`${data.a.xNull?.toFixed(1) ?? '—'} · ${data.b.xNull?.toFixed(1) ?? '—'}`} caption="A · B" variant="card"
            info={<InfoTip title="× null">How many times more than the null expects each run found on this scope (circular shift, 200×).</InfoTip>} />
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ step through the disagreements */

function Disagreements({ data, a, b, only, setOnly, list, i, setI, current }: {
  data: CompareData; a: string; b: string; only: OnlyFilter; setOnly: (v: OnlyFilter) => void
  list: Disagreement[]; i: number; setI: (p: number) => void; current: Disagreement | null
}) {
  const nA = data.disagreements.filter(d => d.kind === 'only A').length
  const nB = data.disagreements.length - nA
  const win = useSourced(() => current ? getDisagreementWindow(a, b, current) : Promise.resolve({ data: null, source: 'demo' as const }), [a, b, current?.detection])
  const [ref, size] = useSize<HTMLDivElement>()
  const W = size.width, labelW = 26, padR = 10
  // The list has no `otherNearest`: the other side's score at a place is computed for the window you step
  // to (/compare/window returns it as `bScore`). So the readout reads the window, and says what it is
  // waiting for until the window lands — never a margin against a number nobody computed.
  const w = win.data
  const nearestAt = w && w.minAt != null && Number.isFinite(w.bScore[w.minAt]) ? w.minAt : null
  const nearest = w && nearestAt != null ? w.bScore[nearestAt] : null
  const thr = w ? w.otherThreshold : current?.otherThreshold ?? null
  const margin = nearest != null && thr != null && thr !== 0 ? Math.abs(nearest - thr) / thr : null
  return (
    <section className="k-card dsc-steps" data-testid="disagreements" aria-label="Step through the disagreements">
      <div className="dsc-card-head">
        <h3>Step through the disagreements</h3>
        <InfoTip title="Step through the disagreements">One window at a time: the clean signal, the span the firing run found, and the other run's own score at that place against its own threshold — so the run that did not fire shows how close it came.{data.sortedBy ? ` Ordered by ${data.sortedBy}.` : ''}{data.disagreementsCapped ? ` Showing ${data.disagreements.length} of ${data.disagreementsTotal}.` : ''}</InfoTip>
        <span className="k-spacer" />
        <Seg size="sm" value={only} onChange={v => setOnly(v as OnlyFilter)} testid="step-filter"
          options={[{ value: 'all', label: `all ${data.disagreements.length}` }, { value: 'a', label: `only A ${nA}` }, { value: 'b', label: `only B ${nB}`, disabled: nB === 0, reason: 'B found nothing A missed on this scope' }]} />
        <Pager page={i} pageCount={Math.max(1, list.length)} onPage={setI} label="disagreement" testid="step-pager" />
        <Button variant="primary" icon="list" disabled={!current} disabledReason={current ? undefined : 'no disagreement to open'}
          onClick={() => navigate(`discovery/compare/stages?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}&only=${only}&i=${i}`)} testid="compare-every-stage">Compare every stage</Button>
      </div>
      {!current ? <EmptyState size="sm" icon="check-circle" title="No disagreement in this filter" caption="A and B agree everywhere here" testid="steps-empty" /> : (
        <div className="dsc-steps-body">
          <div className="dsc-steps-text mono small" data-testid="step-text">
            <b>{current.atH.toFixed(1)} h · {current.channel} · 40 s</b>
            <span className={current.kind === 'only A' ? 'blue' : 'purple'}>{current.kind} fired</span>
            <span className="dsc-steps-gap" />
            <span style={{ color: current.kind === 'only A' ? B_COLOUR : A_COLOUR }} data-testid="step-nearest">{current.kind === 'only A' ? 'B' : 'A'} nearest {nearest != null
              ? (current.otherIsSeed ? `d ${nearest.toFixed(1)}` : `score ${nearest.toFixed(2)}`)
              : win.loading ? 'computing for this window…'
                : w ? (w.scoreNote ?? 'no score in this window')
                  : (data.sortedBy ?? 'computed for the window you step to')}</span>
            {thr != null
              ? <span className="amber">threshold {thr}{margin != null ? ` · ${margin < 0.25 ? 'near miss' : 'not close'}` : ' · nothing to compare it against here'}</span>
              : <span className="amber">the other side has no threshold on this scope</span>}
          </div>
          <div className="dsc-steps-plot" ref={ref}>
            {win.error ? <LoadFailed what="the window" error={win.error} onRetry={win.reload} /> : !win.data || W === 0 ? <Loading height={150} /> : (() => {
              const w = win.data
              const n = w.values.length
              const lo = Math.min(...w.values), hi = Math.max(...w.values), pad = (hi - lo) * 0.15 || 0.1
              const sx = (s: number) => labelW + (s / w.windowS) * (W - labelW - padR)
              const sy = (v: number) => 8 + (1 - (v - (lo - pad)) / ((hi + pad) - (lo - pad))) * 62
              let d = ''
              for (let k = 0; k < n; k++) d += `${k ? 'L' : 'M'}${sx(k).toFixed(1)} ${sy(w.values[k]).toFixed(1)}`
              const aSpan = w.aSpan, span = w.aSpan ?? w.bSpan
              const firedA = !!w.aSpan
              // the non-firing side's own score, scaled to what it actually does in this window (its threshold
              // always in view). A chain with no scoring stage sends an empty track and a note instead.
              const finite = w.bScore.filter(v => Number.isFinite(v))
              const scale = [...finite, ...(thr != null ? [thr] : [])]
              const sLo = Math.min(...scale), sHi = Math.max(...scale)
              const sPad = (sHi - sLo) * 0.18 || 0.2
              const py = (v: number) => 102 + (1 - (v - (sLo - sPad)) / ((sHi + sPad) - (sLo - sPad))) * 36
              let pd = ''
              for (let k = 0; k < w.bScore.length; k++) pd += `${k ? 'L' : 'M'}${sx(k).toFixed(1)} ${py(w.bScore[k]).toFixed(1)}`
              const t0 = current.atH - w.windowS / 2 / 3600
              return (
                <svg width={W} height={158} role="img" aria-label={`the ${w.windowS.toFixed(0)} s window at ${current.atH.toFixed(2)} h`} data-testid="step-plot">
                  {span && <rect x={sx(span[0])} y={6} width={sx(span[1]) - sx(span[0])} height={66} fill={A_COLOUR} opacity={0.12} />}
                  <path d={d} fill="none" stroke="var(--trace)" strokeWidth={1.2} />
                  <text x={0} y={92} className="dsc-axis-t">A</text>
                  <text x={0} y={120} className="dsc-axis-t">B</text>
                  {aSpan
                    ? <><rect x={sx(aSpan[0])} y={86} width={sx(aSpan[1]) - sx(aSpan[0])} height={4} rx={2} fill={A_COLOUR} /><text x={sx(aSpan[1]) + 6} y={91} className="dsc-axis-t" style={{ fill: A_COLOUR }}>{current.detection} · {current.score != null ? `score ${current.score.toFixed(2)}` : 'no score on this detection'}</text></>
                    : <line x1={labelW} x2={W - padR} y1={88} y2={88} stroke="#e5e7eb" strokeWidth={4} />}
                  {finite.length > 0 && <path d={pd} fill="none" stroke={firedA ? B_COLOUR : A_COLOUR} strokeWidth={1.1} />}
                  {finite.length === 0 && <text x={labelW} y={124} className="dsc-axis-t" data-testid="no-other-score">{w.scoreNote ?? 'the other side produced no score in this window'}</text>}
                  {thr != null && <line x1={labelW} x2={W - padR} y1={py(thr)} y2={py(thr)} stroke={THRESH_COLOUR} strokeWidth={1.6} />}
                  {nearest != null && nearestAt != null && <>
                    <circle cx={sx(nearestAt)} cy={py(nearest)} r={3} fill="none" stroke={firedA ? B_COLOUR : A_COLOUR} strokeWidth={1.4} />
                    <text x={sx(nearestAt) + 6} y={py(nearest) + 4} className="dsc-axis-t" style={{ fill: firedA ? B_COLOUR : A_COLOUR }}>{current.otherIsSeed ? nearest.toFixed(1) : nearest.toFixed(2)}</text>
                  </>}
                  <line x1={labelW} x2={W - padR} y1={144} y2={144} stroke="var(--border)" />
                  {[0, 0.5, 1].map((f, k) => <text key={k} x={sx(f * w.windowS)} y={155} textAnchor={k === 0 ? 'start' : k === 2 ? 'end' : 'middle'} className="dsc-axis-t">{(t0 + (f * w.windowS) / 3600).toFixed(2)}{k === 0 || k === 2 ? ' h' : ''}</text>)}
                </svg>
              )
            })()}
          </div>
        </div>
      )}
    </section>
  )
}
