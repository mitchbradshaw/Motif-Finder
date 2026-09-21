/* discovery.runs — frames discovery-1 (runs), -1b (add-template modal), -1c (six channels, paged three at a time).
 * Toolbar · Scope · Runs list | where each run fires · scoreboard · browse detections · run acts (spec §7.1–7.5, P17). */
import { Fragment, useEffect, useMemo, useState } from 'react'
import {
  Button, Callout, DisabledReason, Dropdown, EmptyState, Icon, InfoTip, Modal, Pager, Seg, Trace, cx, recordDemoWrite, useDemoState, useNotWired, useQueryState, useSim, startSim,
} from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import {
  getDetectionWindow, getDetections, getFires, fmtMin, type Detection, type DiscoveryRun, type FiresData, type Recall, type ScoreRow, type ScoreRun,
} from '../api/discovery'
import { CostChip, DiscoveryToolbar, HistoryButton, LoadFailed, Loading, NullChip, RunsCard, ScopeCard, SlurmModal } from './chrome'
import { AddTemplateModal } from './AddTemplateModal'
import { hasResults, useDiscovery, type Discovery } from './session'

export function RunsPage() {
  const dx = useDiscovery()
  const [runQ, setRunQ] = useQueryState('run', 'drop_motifs9')
  const [modal, setModal] = useQueryState('modal', '')
  const [slurmKeys, setSlurmKeys] = useDemoState<string[] | null>('discovery.slurm.keys', () => null)
  const [stateQ] = useQueryState('state', '')
  const selected = dx.runs.find(r => r.key === runQ) ?? dx.runs.find(hasResults) ?? dx.runs[0] ?? null
  const slurmRuns = slurmKeys ? dx.runs.filter(r => slurmKeys.includes(r.key) && (r.status === 'new' || r.status === 'failed')) : dx.pending

  const runLocal = () => {
    dx.pending.forEach(r => {
      dx.patchRun(r.key, { status: 'running', error: undefined })
      startSim(`discovery.run.${r.key}`, { steps: ['01 stage', '02 stage', '03 stage', 'null 200×'], stepMs: 1100 })
    })
    recordDemoWrite('discovery', 'run-local', { runs: dx.pending.map(r => r.key) })
  }
  const primary = dx.pending.length === 0
    ? <DisabledReason reason="nothing to run — every run in this session has results or is on the cluster"><Button icon="play" disabled disabledReason="nothing to run — every run in this session has results or is on the cluster" testid="toolbar-run">Run</Button></DisabledReason>
    : dx.overLimit
      ? <Button variant="cluster" icon="file" onClick={() => { setSlurmKeys(null); setModal('slurm') }} testid="toolbar-slurm">Create SLURM script for {dx.pending.length}</Button>
      : <Button variant="primary" icon="play" onClick={runLocal} testid="toolbar-run">Run {dx.pending.length}</Button>

  return (
    <>
      <Header workspace="Discovery" page="Runs" subtitle="apply saved templates and seed searches across channels" demo={dx.demo} />
      <div className="k-page dsc-page" data-testid="discovery-runs-page">
        <div className="k-page-inner" style={{ maxWidth: 1376, gap: 12 }}>
          {dx.error && <LoadFailed what="the Discovery session" error={dx.error} onRetry={dx.reload} />}
          {dx.loading && !dx.error && <Loading height={600} label="loading the session" />}
          {dx.scope && (
            <>
              <DiscoveryToolbar dx={dx} right={<><NullChip dx={dx} /><CostChip dx={dx} /><HistoryButton dx={dx} />{primary}</>} />
              <ScopeCard dx={dx} />
              {dx.recording?.heldOut ? null : (
                <div className="dsc-cols">
                  <RunsCard dx={dx} mode="runs" selected={selected?.key} onSelect={k => setRunQ(k)} onAddTemplate={() => setModal('add-template')} />
                  <div className="dsc-right">
                    {stateQ === 'failed' && <Callout tone="red" icon="alert-triangle" title="seed_E0102_bank failed" testid="run-failed-callout" action={<Button size="sm" icon="refresh" onClick={() => navigate('discovery/runs')}>Dismiss</Button>}>MASS failed on CH7_B2 · scale bank length 63 s ran out of memory (simulated). Nothing was written; Retry on the row re-queues it.</Callout>}
                    {dx.runs.filter(hasResults).length === 0 ? (
                      <div className="k-card dsc-empty-results" data-testid="results-empty">
                        <EmptyState icon="target" title="No run has results yet" caption="Apply a template or set up a seed search; results fill in here as runs finish"
                          action={<div className="row" style={{ gap: 8 }}><Button icon="layers" onClick={() => setModal('add-template')}>Apply template</Button><Button icon="target" onClick={() => navigate('discovery/seed')}>Seed search</Button></div>} />
                      </div>
                    ) : (
                      <>
                        <WhereFires dx={dx} />
                        <Scoreboard dx={dx} />
                        <Browser dx={dx} run={selected} />
                        <RunActs dx={dx} run={selected} />
                      </>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      {dx.scope && <AddTemplateModal open={modal === 'add-template'} onClose={() => setModal(null)} dx={dx}
        onSlurm={keys => { setSlurmKeys(keys); setModal('slurm') }} />}
      {dx.scope && <SlurmModal open={modal === 'slurm'} onClose={() => setModal(null)} dx={dx} runs={slurmRuns} />}
    </>
  )
}

/* ------------------------------------------------------------------ where each run fires */
const opacityFor = (n: number) => n <= 0 ? 0 : n === 1 ? 0.22 : n === 2 ? 0.42 : n === 3 ? 0.68 : 1

function WhereFires({ dx }: { dx: Discovery }) {
  const s = dx.scope!
  const [mode, setMode] = useQueryState<'density' | 'spans'>('fires', 'density')
  const [, setRunQ] = useQueryState('run', 'drop_motifs9')
  const [chQ, setChQ] = useQueryState('ch', 'CH4_A2')
  const [, setAt] = useQueryState('at', '')
  const shown = dx.runs.filter(r => r.kind === 'reference' || hasResults(r) || r.status === 'on cluster' || r.status === 'running')
  const notShown = dx.runs.filter(r => !shown.includes(r) && r.status !== 'draft')
  const fires = useSourced(() => getFires(dx.visibleChannels, s.section, shown), [dx.visibleChannels.join(','), s.section.join(','), shown.map(r => r.key + r.status).join(',')])
  const sectionH = s.section[1] - s.section[0]
  const ticks = useMemo(() => Array.from({ length: 7 }, (_, i) => Math.round(s.section[0] + (i * sectionH) / 6)), [s.section, sectionH])
  const browserMarker = useBrowserMarker(dx)
  const paged = s.channels.length > 3
  return (
    <section className="k-card dsc-fires" data-testid="where-fires" aria-label="Where each run fires">
      <div className="dsc-card-head">
        <h3>Where each run fires</h3>
        <InfoTip title="Where each run fires">Small multiples by channel, one row per run, on one time axis. At section scale a span is thinner than a pixel, so rows show detections per 3 h bin — colour by run, opacity by count. The human row shows reviewed hours as a grey underlay: recall exists only there.</InfoTip>
        <span className="muted small">{paged ? `channels ${(dx.chPage - 1) * 3 + 1}–${Math.min(s.channels.length, dx.chPage * 3)} of ${s.channels.length} · follows the scope pager` : 'detections per 3 h · grouped by channel'}</span>
        <span className="k-spacer" />
        <Seg size="sm" value={mode} onChange={v => setMode(v)} options={[{ value: 'density', label: 'density' }, { value: 'spans', label: 'spans' }]} testid="fires-mode" />
        <span className="dsc-ramp small" aria-label="legend">
          <i className="sw" style={{ background: 'var(--grey-200)' }} /> reviewed hours
          <span className="muted">0</span>{[1, 2, 3, 4].map(n => <i key={n} className="sw" style={{ background: '#374151', opacity: opacityFor(n) }} />)}<span className="muted">4+ per 3 h</span>
        </span>
      </div>
      {mode === 'spans' && sectionH > 24 && <div className="dsc-note small" data-testid="spans-note">spans are thinner than a pixel at this scale · zoom the section below 24 h</div>}
      {fires.error && <LoadFailed what="where each run fires" error={fires.error} onRetry={fires.reload} />}
      {!fires.data && !fires.error && <Loading height={200} />}
      {fires.data && (
        <div className="dsc-fires-body">
          {fires.data.channels.map(ch => (
            <div key={ch.channel} className="dsc-fires-group" data-testid={`fires-group-${ch.channel}`}>
              <b className="dsc-fires-ch mono">{ch.channel}</b>
              <div className="dsc-fires-rows">
                {ch.rows.map(row => {
                  // a discarded run drops out of `shown` a frame before the refetch returns, so its row can outlive it
                  const run = shown.find(r => r.key === row.run)
                  if (!run) return null
                  const isHuman = run.kind === 'reference'
                  return (
                    <div key={row.run} className="dsc-fires-row">
                      <span className="dsc-fires-label"><i className="sw" style={{ background: run.colour }} />{isHuman ? 'human' : run.label}</span>
                      <div className="dsc-fires-cells">
                        <FiresCells data={fires.data!} channel={ch.channel} counts={row.counts} reviewed={isHuman ? ch.reviewed : null} colour={run.colour} mode={mode} unfinishedFrom={row.unfinishedFrom}
                          label={isHuman ? 'human' : run.label} onCell={(bin) => { if (isHuman) return; setRunQ(run.key); setChQ(ch.channel); setAt(String(bin * fires.data!.binH)) }} />
                        {isHuman && ch.reviewedH === 0 && <span className="dsc-fires-none">no reviewed hours in this section</span>}
                        {row.unfinishedFrom != null && <span className="dsc-fires-unfinished" style={{ left: `${(row.unfinishedFrom / fires.data!.nBins) * 100}%` }}>{run.status === 'running' ? 'running locally' : 'on cluster'} · {Math.round((run.progress ?? 0) * 100)} %</span>}
                      </div>
                    </div>
                  )
                })}
                {browserMarker && browserMarker.channel === ch.channel && (
                  <span className="dsc-fires-marker" style={{ left: `calc(110px + (100% - 110px) * ${(browserMarker.atH - s.section[0]) / sectionH})` }} title={`${browserMarker.id} · ${browserMarker.atH.toFixed(2)} h — the detection in the browser`} data-testid="fires-marker" />
                )}
              </div>
            </div>
          ))}
          <div className="dsc-fires-axis mono">{ticks.map((t, i) => <span key={i} style={{ left: `calc(${(i / 6) * 100}%)` }}>{i === 0 || i === 6 ? `${t} h` : t}</span>)}</div>
          {notShown.length > 0 && <div className="muted small dsc-fires-foot">not drawn: {notShown.map(r => `${r.label} (${r.status === 'paused' ? `paused ${r.pausedAt?.stage}/${r.pausedAt?.of}` : r.status})`).join(' · ')} — nothing to draw in this section</div>}
        </div>
      )}
    </section>
  )
}

function FiresCells({ data, channel, counts, reviewed, colour, mode, unfinishedFrom, label, onCell }: { data: FiresData; channel: string; counts: number[]; reviewed: number[] | null; colour: string; mode: 'density' | 'spans'; unfinishedFrom?: number; label: string; onCell: (bin: number) => void }) {
  const n = data.nBins
  return (
    <svg className="dsc-fires-svg" viewBox={`0 0 ${n * 10} 10`} preserveAspectRatio="none" width="100%" height={11} role="img" aria-label={`${channel} ${label} detections per 3 h`}>
      <rect x={0} y={0} width={n * 10} height={10} fill="#f3f4f6" />
      {reviewed?.map((h, i) => h > 0 ? <rect key={`r${i}`} x={i * 10} y={0} width={10} height={10} fill="#d1d5db" opacity={0.35 + (h / 3) * 0.5} /> : null)}
      {counts.map((c, i) => {
        if (unfinishedFrom != null && i >= unfinishedFrom) return null
        if (c <= 0) return null
        const bin = data.firstBin + i
        const title = `${channel} · ${label} · ${bin * data.binH}–${(bin + 1) * data.binH} h · ${c} detection${c === 1 ? '' : 's'}`
        if (mode === 'spans') return <g key={i} onClick={() => onCell(bin)} style={{ cursor: 'pointer' }}><title>{title}</title>{Array.from({ length: c }, (_, k) => <rect key={k} x={i * 10 + ((k * 3.7 + 1.3) % 9)} y={0} width={0.9} height={10} fill={colour} />)}</g>
        return <rect key={i} x={i * 10 + 0.4} y={0} width={9.2} height={10} fill={colour} opacity={opacityFor(c)} onClick={() => onCell(bin)} style={{ cursor: 'pointer' }} data-testid="fires-cell"><title>{title}</title></rect>
      })}
    </svg>
  )
}

/** The browser's current detection, for the ▼ marker on its channel. */
function useBrowserMarker(dx: Discovery): Detection | null {
  const [runQ] = useQueryState('run', 'drop_motifs9')
  const [chQ] = useQueryState('ch', 'CH4_A2')
  const [iQ] = useQueryState('i', '')
  const s = dx.scope!
  const ch = s.channels.includes(chQ) ? chQ : s.channels[0]
  const run = dx.runs.find(r => r.key === runQ)
  const dets = useSourced(() => run && hasResults(run) ? getDetections(run.key, ch, s.section) : Promise.resolve({ data: [] as Detection[], source: 'demo' as const }), [run?.key, run?.status, ch, s.section.join(',')])
  if (!dets.data?.length) return null
  const i = defaultIndex(iQ, run?.key, ch, dets.data.length)
  return dets.data[i - 1] ?? null
}
const defaultIndex = (iQ: string, run: string | undefined, ch: string, n: number) => Math.min(n, Math.max(1, parseInt(iQ, 10) || (run === 'drop_motifs9' && ch === 'CH4_A2' ? 12 : 1)))

/* ------------------------------------------------------------------ scoreboard */
const fmtRecall = (r: Recall) => 'value' in r ? `${r.value.toFixed(2)} over ${r.overH} h` : 'none' in r ? 'no reviewed overlap' : `${r.tooFewH} h · too few`
type SortKey = 'found' | 'judged' | 'reviewed' | 'interesting' | 'precision' | 'nullExpects' | 'xNull'

function Scoreboard({ dx }: { dx: Discovery }) {
  const [expandQ, setExpandQ] = useQueryState('expand', 'drop_motifs9')
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 } | null>(null)
  const refresh = useSim('discovery.scores.refresh')
  const toast = useToast()
  const notWired = useNotWired()
  const expanded = expandQ ? expandQ.split(',') : []
  const toggle = (k: string) => setExpandQ((expanded.includes(k) ? expanded.filter(x => x !== k) : [...expanded, k]).join(',') || '')
  useEffect(() => {
    if (refresh.status === 'done') { toast.push({ text: 'scores refreshed · no new verdicts since 11:40' }); notWired('GET /discovery/sessions/ch_screen_sep14/scores'); refresh.reset() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh.status])
  const scores = dx.scores ?? []
  const colourOf = (k: string) => dx.runs.find(r => r.key === k)?.colour ?? '#9ca3af'
  let done: ScoreRun[] = scores.filter(s => dx.runs.some(r => r.key === s.run && hasResults(r)))
  if (sort) done = [...done].sort((a, b) => ((a.total[sort.key] ?? -1) - (b.total[sort.key] ?? -1)) * sort.dir)
  const others = dx.runs.filter(r => r.kind !== 'reference' && !hasResults(r) && r.status !== 'draft')
  const th = (label: string, key?: SortKey) => key
    ? <th><button type="button" className="dsc-th-sort" onClick={() => setSort(s => s?.key === key ? (s.dir === -1 ? { key, dir: 1 } : null) : { key, dir: -1 })} aria-sort={sort?.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>{label}{sort?.key === key && <Icon name={sort.dir === 1 ? 'chevron-up' : 'chevron-down'} size={10} />}</button></th>
    : <th>{label}</th>
  const cells = (row: ScoreRow) => <>
    <td>{row.found}</td><td>{row.judged}</td><td>{row.reviewed}</td><td>{row.interesting}</td>
    <td>{row.precision == null ? <span className="muted">not yet scored</span> : `${Math.round(row.precision * 100)} %`}</td>
    <td className={cx(!('value' in row.recall) && 'muted')}>{fmtRecall(row.recall)}</td>
    <td>{row.nullExpects}</td><td>{row.xNull == null ? '—' : `${row.xNull.toFixed(1)}×`}</td>
  </>
  return (
    <section className="k-card dsc-score" data-testid="scoreboard" aria-label="Scoreboard">
      <div className="dsc-card-head">
        <h3>Scoreboard</h3>
        <InfoTip title="Scoreboard">Precision is labelled precision: alone it rewards timidity. Recall is per channel, over that channel's reviewed overlap; the run row states the hours it pooled. Already judged counts detections that had a verdict before the run started. Null expects is what the circular-shift null finds on the same scope; × null is the ratio.</InfoTip>
        <span className="muted small">per run · expand a run for its channels</span>
        <span className="k-spacer" />
        <Button variant="link" icon="refresh" loading={refresh.busy} onClick={() => refresh.start({ stepMs: 600, queuedMs: 100 })} testid="refresh-scores">Refresh after reviewing</Button>
      </div>
      <div className="k-table-wrap">
        <table className="dsc-table" data-testid="scoreboard-table">
          <thead><tr>{th('run')}{th('found', 'found')}{th('already judged', 'judged')}{th('reviewed', 'reviewed')}{th('interesting', 'interesting')}{th('precision', 'precision')}{th('recall · reviewed overlap')}{th('null expects', 'nullExpects')}{th('× null', 'xNull')}</tr></thead>
          <tbody>
            {done.map(s => {
              const open = expanded.includes(s.run)
              return (
                <Fragment key={s.run}>
                  <tr className={cx('parent', open && 'open')} data-testid={`score-row-${s.run}`}>
                    <td><button type="button" className="dsc-expand" onClick={() => toggle(s.run)} aria-expanded={open} data-testid={`score-expand-${s.run}`}><Icon name={open ? 'chevron-down' : 'chevron-right'} size={12} /><span className="dot" style={{ background: colourOf(s.run) }} /><b>{s.run}</b>{dx.stale && <span className="k-badge t-amber">stale</span>}</button></td>
                    {cells(s.total)}
                  </tr>
                  {open && s.channels.map(c => <tr key={c.channel} className="child" data-testid={`score-child-${s.run}-${c.channel}`}><td className="indent">{c.channel}</td>{cells(c)}</tr>)}
                </Fragment>
              )
            })}
            {others.map(r => (
              <tr key={r.key} className="parent other" data-testid={`score-row-${r.key}`}>
                <td><span className="dsc-expand static"><Icon name="chevron-right" size={12} /><span className="dot" style={{ background: r.colour }} /><b>{r.label.replace(/ · r-\d+$/, '')}</b></span></td>
                <td colSpan={8} className="muted">{otherLine(r)}{r.status === 'paused' && r.id && <Button variant="link" size="sm" icon="external" onClick={() => navigate(`jobs/run/${r.id}`)}>Open in Jobs</Button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
function otherLine(r: DiscoveryRun) {
  switch (r.status) {
    case 'on cluster': return `running on cluster · ${Math.round((r.progress ?? 0) * 100)} % · scores appear when it finishes`
    case 'running': return 'running locally · scores appear when it finishes'
    case 'queued': return 'queued · scores appear when it finishes'
    case 'new': return 'new · local'
    case 'paused': return `paused at stage ${r.pausedAt?.stage} of ${r.pausedAt?.of} · waiting on ${r.job} · `
    case 'failed': return `failed · ${r.error ?? 'see the run row'}`
    case 'superseded': return 'superseded · no verdicts written'
    default: return r.status
  }
}

/* ------------------------------------------------------------------ browse detections */
function Browser({ dx, run }: { dx: Discovery; run: DiscoveryRun | null }) {
  const s = dx.scope!
  const [, setRunQ] = useQueryState('run', 'drop_motifs9')
  const [chQ, setChQ] = useQueryState('ch', 'CH4_A2')
  const [iQ, setIQ] = useQueryState('i', '')
  const [atQ, setAtQ] = useQueryState('at', '')
  const ch = s.channels.includes(chQ) ? chQ : s.channels[0]
  const browsable = run && hasResults(run)
  const dets = useSourced(() => browsable ? getDetections(run!.key, ch, s.section) : Promise.resolve({ data: [] as Detection[], source: 'demo' as const }), [run?.key, browsable, ch, s.section.join(',')])
  const n = dets.data?.length ?? 0
  const i = defaultIndex(iQ, run?.key, ch, n)
  const det = dets.data?.[i - 1] ?? null
  const win = useSourced(() => det ? getDetectionWindow(det) : Promise.resolve({ data: null, source: 'demo' as const }), [det?.id])
  // a click in where-each-run-fires lands here as ?at=<hour>: step to the first detection at or after it
  useEffect(() => {
    if (!atQ || !dets.data) return
    const h = parseFloat(atQ)
    const idx = dets.data.findIndex(d => d.atH >= h)
    setIQ(String(idx >= 0 ? idx + 1 : dets.data.length)); setAtQ(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atQ, dets.data])
  const runOptions = dx.runs.filter(r => r.kind !== 'reference' && r.status !== 'draft').map(r => ({ value: r.key, label: r.label, disabled: !hasResults(r), reason: hasResults(r) ? undefined : 'no detections yet' }))
  const channelOptions = s.channels.map(c => ({ value: c, label: c, hint: dx.scores?.find(x => x.run === run?.key)?.channels.find(x => x.channel === c)?.found?.toString() }))
  return (
    <section className="k-card dsc-browser" data-testid="browser" aria-label="Browse detections">
      <div className="dsc-card-head">
        <h3>Browse detections</h3>
        <InfoTip title="Browse detections">Step through one run's detections on one channel, in time order. Browse only: verdicts are given in Review (P6).</InfoTip>
        <span className="k-spacer" />
        <Dropdown prefix="run" value={run?.key ?? ''} onChange={v => { setRunQ(v); setIQ(null) }} options={runOptions} variant="grey" active testid="browser-run" />
        <Dropdown prefix="channel" value={ch} onChange={v => { setChQ(v); setIQ(null) }} options={channelOptions} testid="browser-channel" />
        <Pager page={i} pageCount={Math.max(1, n)} onPage={p => setIQ(String(p))} boxed label="detection" testid="browser-pager" />
        <span className="muted small row" style={{ gap: 4 }}><Icon name="eye" size={12} /> browse only</span>
      </div>
      {!run || run.kind === 'reference' ? (
        <EmptyState size="sm" icon="eye" title="human annotations have no detections to browse" caption="pick a run in the runs list" testid="browser-human" />
      ) : !browsable ? (
        <EmptyState size="sm" icon="hourglass" title={`${run.label} has no detections yet`} caption={otherLine(run)} testid="browser-no-results" />
      ) : dets.error ? <LoadFailed what="detections" error={dets.error} onRetry={dets.reload} />
        : !det ? (n === 0 && dets.data ? <EmptyState size="sm" title={`no detections on ${ch}`} testid="browser-none" /> : <Loading height={150} />) : (
          <div className="dsc-browser-body">
            <div className="dsc-det-info" data-testid="browser-detection">
              <b className="mono">{det.id}</b>
              <span>{det.atH.toFixed(2)} h · {det.channel}</span>
              {/* a block that emits no score, or a window of NaNs, gives no number here — say which field is absent */}
              <span>{det.depthMv != null ? `depth ${det.depthMv.toFixed(2)} mV` : 'no depth recorded'} · {det.score != null ? `score ${det.score.toFixed(2)}` : 'no score from this chain'}</span>
              <span className="muted">{det.priorVerdict ? `prior verdict · ${det.priorVerdict}` : 'no prior verdict'}</span>
              <span className="muted">also found by {det.alsoFoundBy.length ? det.alsoFoundBy.map(k => (
                <button key={k} type="button" className="dsc-inline-link" onClick={() => { setRunQ(k); setIQ(null) }} data-testid={`also-found-${k}`}><span className="dot" style={{ background: dx.runs.find(r => r.key === k)?.colour }} />{k}</button>
              )) : '—'}</span>
              {det.nearMiss && <span className="muted small">{det.nearMiss.run} came within d {det.nearMiss.d.toFixed(1)} (near miss)</span>}
            </div>
            <div className="dsc-det-plot">
              {win.data ? <Trace values={win.data.values} fs={1} t0={win.data.t0H * 3600} height={150} testid="browser-trace"
                bands={[{ start_s: det.atH * 3600 - det.durationS / 2, end_s: det.atH * 3600 + det.durationS / 2, kind: 'detected' }]} /> : <Loading height={150} />}
            </div>
          </div>
        )}
    </section>
  )
}

/* ------------------------------------------------------------------ run acts */
function RunActs({ dx, run }: { dx: Discovery; run: DiscoveryRun | null }) {
  const [confirm, setConfirm] = useQueryState('confirm', '')
  const [sent, setSent] = useDemoState<Record<string, number>>('discovery.sent', () => ({}))
  const toast = useToast()
  const notWired = useNotWired()
  if (!run) return null
  const total = dx.scores?.find(s => s.run === run.key)?.total
  const results = hasResults(run)
  const unjudged = total ? total.found - total.reviewed : 0
  const reason = run.kind === 'reference' ? 'human annotations are the reference, not a run'
    : run.status === 'superseded' ? 'discarded — marked superseded, no verdicts written'
      : !results ? 'no detections yet' : null
  const discard = () => {
    dx.patchRun(run.key, { status: 'superseded' })
    dx.setPicks(dx.picks.filter(k => k !== run.key))
    recordDemoWrite('discovery', 'discard-run', { run: run.key, adjudications_written: 0 })
    toast.push({ text: `${run.label} discarded · marked superseded, no verdicts written` })
    setConfirm(null)
  }
  const send = () => {
    const q = `q-${20 + Object.keys(sent).length}`
    setSent({ ...sent, [run.key]: unjudged })
    recordDemoWrite('review', 'add-queue', { id: q, source: `${run.label} · ${dx.scope!.name}`, kind: 'discovery run', count: unjudged })
    recordDemoWrite('discovery', 'send-to-review', { run: run.key, count: unjudged, queue: q })
    toast.push({ text: `${unjudged} detections sent to Review · tagged ${run.label}`, action: { label: 'Open Review', onClick: () => navigate(`review/queue/${q}`) } })
  }
  return (
    <section className="k-card dsc-acts" data-testid="run-acts" aria-label="Run acts">
      <span className="dot" style={{ background: run.colour, width: 9, height: 9 }} />
      <b>{run.label}</b>
      {total && results ? <span className="muted small">{total.found} detections · {dx.scope!.channels.length} channels · {total.judged} already judged</span> : <span className="muted small">{reason}</span>}
      <span className="k-spacer" />
      <Button icon="trash" onClick={() => setConfirm('discard')} disabled={!!reason} disabledReason={reason ?? undefined} testid="discard-run">Discard run</Button>
      <Button icon="branch" onClick={() => { recordDemoWrite('analyse', 'import-spanset', { run: run.key }); notWired(`send SpanSet of ${run.label} to Analyse`); navigate('analyse/chain') }} disabled={!!reason} disabledReason={reason ?? undefined} testid="analyse-events">Analyse events</Button>
      {sent[run.key] != null
        ? <Button icon="check" disabled disabledReason="already sent — judge them in Review, then Refresh after reviewing" testid="send-to-review">Sent {sent[run.key]} · refresh after reviewing</Button>
        : <Button variant="primary" icon="arrow-right" onClick={send} disabled={!!reason || unjudged === 0} disabledReason={reason ?? 'nothing unjudged'} testid="send-to-review">Send {unjudged} unjudged to Review</Button>}
      <Modal open={confirm === 'discard' && !reason} onClose={() => setConfirm(null)} title={`Discard ${run.label}?`} size="sm" testid="discard-modal"
        footer={<><Button onClick={() => setConfirm(null)}>Cancel</Button><Button variant="danger-solid" icon="trash" onClick={discard} testid="discard-confirm">Discard run</Button></>}>
        <p>Marks the run superseded. Writes <b>no adjudications</b> — its {total?.found ?? 0} detections are not marked not_interesting.</p>
        <p className="muted small">Bulk not_interesting verdicts would poison the RQ5 divergence measurement, invisibly.</p>
      </Modal>
    </section>
  )
}

