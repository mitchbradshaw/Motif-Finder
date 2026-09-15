/* library.import — frame library-5: the empty Motifs section (two ways in) beside the motif import dry run.
 * The dry run reads the bundle and writes nothing; Import runs sim job l-0032 (all-or-nothing), then offers the library. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Checkbox, Chip, Icon, KeyValue, MiniTrace, Page, ProgressBar, SelectField, StatRow, StatTile, fmtInt, getSim, recordDemoWrite, useQueryState, useSim } from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { IMPORT_BUNDLE_PATHS, IMPORT_FAIL_ERROR, IMPORT_STEPS, dryRunImport, getLibraryCounts, motifShape, type ImportBundle, type ImportCheck } from '../api/library'
import { LoadFailed, SectionBar, useEmptyLibrary, useExternalNavKey, useQueueToast } from './chrome'
import { EmptyLibraryCard } from './EmptyLibrary'

const SIM_ID = 'library.import.l-0032'

export function ImportPage() {
  const [empty] = useEmptyLibrary()
  const counts = useSourced(getLibraryCounts, [])
  const navKey = useExternalNavKey()
  const selectRef = useRef<HTMLDivElement>(null)
  const focusBundle = () => selectRef.current?.querySelector('select')?.focus()
  return (
    <>
      <Header workspace="Library" page="Motifs" subtitle={empty ? 'empty' : 'import · dry run'} search="Search spans, runs, families" demo={counts.source === 'demo'} />
      <Page testid="import-page">
        <SectionBar section="motifs" crumbs={empty ? undefined : [{ label: 'Recurrence', onClick: () => navigate('library/recurrence') }, { label: 'Import' }]}
          actions={<Button variant={empty ? 'primary' : 'default'} icon="download" testid="library-import" onClick={focusBundle}>Import</Button>} />
        <div className="lib-import">
          <div className="stack" style={{ gap: 16 }}>
            {empty ? <EmptyLibraryCard highlightImport onImport={focusBundle} /> : (
              <div className="k-card" style={{ padding: 18 }} data-testid="library-now">
                <div className="row" style={{ marginBottom: 10 }}><Icon name="library" size={16} /><b style={{ fontSize: 14 }}>Library now</b></div>
                <KeyValue align="right" items={[{ k: 'motifs', v: fmtInt(counts.data?.motifs ?? 0) }, { k: 'families', v: 10 }, { k: 'grouping', v: 'g-07' }, { k: 'spike trains', v: counts.data?.spikeTrains ?? '…' }]} />
                <div style={{ marginTop: 10 }}><Button variant="link" onClick={() => navigate('library/recurrence')}>‹ back to recurrence</Button></div>
              </div>
            )}
          </div>
          <ImportPanel key={navKey} empty={empty} selectRef={selectRef} />
        </div>
      </Page>
    </>
  )
}

function ImportPanel({ empty, selectRef }: { empty: boolean; selectRef: React.RefObject<HTMLDivElement | null> }) {
  const [bundleQ, setBundleQ] = useQueryState('bundle', '')
  const bundle = bundleQ === 'no-provenance' ? 'DATA/library_seed/untitled_bundle' : bundleQ === 'held-out' ? 'DATA/library_seed/M4_aug_holdout' : IMPORT_BUNDLE_PATHS[0]
  const [stateQ, setStateQ] = useQueryState('state', '')
  const dry = useSourced(() => dryRunImport(bundle), [bundle])
  const run = useSim(SIM_ID)
  const forced = useRef(false)
  const [sendToReview, setSendToReview] = useState(true)
  const [seed, setSeed] = useState(1)
  const [open, setOpen] = useState<string | null>(null)
  const { push } = useToast()
  const queue = useQueueToast()
  const leave = () => { if (run.busy) run.cancel(); run.reset(); navigate(empty ? 'library/recurrence?library=empty' : 'library/recurrence') }

  useEffect(() => {
    const idle = getSim(SIM_ID).status === 'idle'
    if (!idle || !stateQ) return
    forced.current = true
    if (stateQ === 'running') run.force({ status: 'running', steps: IMPORT_STEPS, step: 1, fraction: 0.4, startedAt: Date.now() })
    if (stateQ === 'failed') run.force({ status: 'failed', steps: IMPORT_STEPS, step: 2, fraction: 0.62, error: IMPORT_FAIL_ERROR })
    if (stateQ === 'done') run.force({ status: 'done', steps: IMPORT_STEPS, step: 3, fraction: 1 })
  }, [stateQ]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { if (forced.current) run.reset() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const doneOnce = useRef(false)
  useEffect(() => {
    if (run.status !== 'done' || forced.current || doneOnce.current) return
    doneOnce.current = true
    recordDemoWrite('library', 'import', { bundle, motifs: dry.data?.counts.motifs, job: 'l-0032' })
    if (sendToReview && dry.data) queue('Library · import drop_motifs5', dry.data.counts.motifs)
  }, [run.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const b = dry.data
  const alreadyIn = !empty && b && !b.blockedReason
  const blocked = b?.blockedReason ?? (alreadyIn ? 'nothing new to import — every motif hash is already in the library' : null)
  const checks: ImportCheck[] = b ? b.checks.map(c => alreadyIn && c.title === 'safe to run twice' ? { ...c, detail: `content hash per motif · ${b.counts.motifs} already in the library · re-import skips` } : c) : []
  const creates = b ? (alreadyIn ? ['0 new entries — every motif hash is already present', 'grouping g-07 unchanged'] : b.creates) : []
  const sample = useMemo(() => {
    if (!b) return []
    const n = b.sample.length, out = []
    for (let k = 0; k < 9; k++) out.push(b.sample[(k * 47 + seed * 131) % n])
    return out
  }, [b, seed])
  const traces = useMemo(() => sample.map(s => motifShape(s.shape, s.amp, s.seed, { n: 70 })), [sample])
  const yDomain: [number, number] = [-0.35, 0.35]
  const status = run.status
  const cancellable = run.busy && run.step < 2

  return (
    <div className="k-card" style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 12, minHeight: 618 }} data-testid="import-panel">
      <div className="row">
        <Icon name="download" size={16} />
        <b style={{ fontSize: 16 }}>Import motifs</b>
        {status === 'done' ? <Chip tone="green" size="sm" icon="check">imported · job l-0032</Chip> : run.busy ? <Chip tone="blue" size="sm">importing · job l-0032</Chip> : <Chip tone="blue" size="sm">dry run · nothing written yet</Chip>}
        <span style={{ marginLeft: 'auto' }} />
        <Button variant="ghost" icon="x" aria-label="close the import" testid="import-close" onClick={leave} />
      </div>
      <div className="stack" style={{ gap: 4 }}>
        <span className="lib-cap" style={{ fontSize: 11 }}>bundle</span>
        <div className="row" ref={selectRef}>
          <SelectField value={bundle} width={400} testid="bundle-select" ariaLabel="bundle" disabled={run.busy} disabledReason="an import is running"
            onChange={v => { if (v === '__browse') { push({ text: 'not wired yet: bundle picker (the bridge would list folders under DATA/library_seed/)' }); return } setBundleQ(v === IMPORT_BUNDLE_PATHS[0] ? null : v.endsWith('untitled_bundle') ? 'no-provenance' : 'held-out'); run.reset() }}
            options={[...IMPORT_BUNDLE_PATHS.map(p => ({ value: p, label: p })), { value: '__browse', label: 'Browse…' }]} />
          {b && (b.provenanceFound ? <Chip tone="green" size="sm" testid="provenance-chip">PROVENANCE.md found</Chip> : <Chip tone="red" size="sm" testid="provenance-chip">PROVENANCE.md missing</Chip>)}
          {b?.heldOut && <Chip tone="grey" size="sm" icon="lock">M4_aug held out</Chip>}
        </div>
      </div>
      {dry.error && <LoadFailed what="the bundle" error={dry.error} onRetry={dry.reload} />}
      {dry.loading && <div className="stack" style={{ gap: 8 }} data-testid="dry-run-checking">{[0, 1, 2, 3, 4].map(i => <div key={i} className="skeleton" style={{ height: i === 0 ? 50 : 16 }} />)}<span className="lib-cap">checking…</span></div>}
      {b && !dry.loading && <>
        <StatRow columns={4}>
          <StatTile label="motifs" value={fmtInt(b.counts.motifs)} />
          <StatTile label="spike trains" value={b.counts.spikeTrains} />
          <StatTile label="recordings" value={b.counts.recordings} />
          <StatTile label="channels" value={b.counts.channels} />
        </StatRow>
        <div className="stack" style={{ gap: 6 }} data-testid="import-checks">
          <b style={{ fontSize: 13 }}>Checks</b>
          <div className="lib-checks">
            {checks.map(c => (
              <div key={c.title}>
                <button type="button" className={`lib-check ${c.status} lib-plain`} style={{ width: '100%', cursor: c.items || c.link ? 'pointer' : 'default' }} aria-expanded={c.items || c.link ? open === c.title : undefined} data-testid={`check-${c.status}`}
                  onClick={() => (c.items || c.link) && setOpen(o => (o === c.title ? null : c.title))}>
                  <Icon name={c.status === 'ok' ? 'check-circle' : c.status === 'warn' ? 'alert-triangle' : 'x-circle'} size={14} className="ic" />
                  <span>{c.title}</span>{(c.items || c.link) && <Icon name={open === c.title ? 'chevron-up' : 'chevron-down'} size={11} />}
                  <span className="detail">{c.detail}</span>
                </button>
                {open === c.title && <div className="lib-cap" style={{ margin: '4px 0 4px 22px', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {c.items?.map(i => <span key={i}>{i}</span>)}
                  {c.link && <Button variant="link" size="sm" onClick={() => navigate(c.link!.to)}>{c.link.label} →</Button>}
                </div>}
              </div>
            ))}
          </div>
        </div>
        <div className="stack" style={{ gap: 6 }} data-testid="import-creates">
          <b style={{ fontSize: 13 }}>What the import creates</b>
          <div className="lib-creates">{creates.map(c => <span key={c}><span className="plus">+</span>{c}</span>)}</div>
        </div>
        <div className="stack" style={{ gap: 6 }} data-testid="import-sample">
          <div className="row"><b style={{ fontSize: 13 }}>Sample</b><span className="lib-cap">{b.heldOut ? 'withheld' : `9 of ${fmtInt(b.counts.motifs)} · shared mV scale`}</span>
            <Button variant="link" icon="shuffle" style={{ marginLeft: 'auto' }} testid="import-resample" disabled={!!b.heldOut} disabledReason="nothing from a held-out recording is sampled" onClick={() => setSeed(s => s + 1)}>resample</Button></div>
          {b.heldOut ? <div className="lib-locked" style={{ width: 'auto' }} data-testid="sample-withheld"><span className="row" style={{ gap: 6 }}><Icon name="lock" size={13} />sample withheld — M4_aug is held out and locked (D6); nothing from it is shown or imported</span></div> : <div className="row" style={{ gap: 6 }}>
            {sample.map((s, i) => <MiniTrace key={`${s.id}-${i}`} values={traces[i]} yDomain={yDomain} width={62} height={42} ground="grey" zeroLine={false} title={`motif ${s.id} · ${s.recording} · ${s.channel} · ${s.onsetH} h · ${s.durationS} s${s.provisional ? ' (provisional)' : ''}`} style={{ borderRadius: 4 }} />)}
          </div>}
        </div>
      </>}
      <span style={{ marginTop: 'auto' }} />
      {status === 'failed' && (
        <div className="error-card" role="alert" data-testid="import-failed">
          <b>Import l-0032 failed at “{run.steps[run.step]}”</b>
          <div className="mono small" style={{ color: 'var(--red)', margin: '4px 0' }}>{run.error}</div>
          <div className="row"><span className="lib-cap">nothing was written — imports are all-or-nothing</span><Button size="sm" icon="refresh" style={{ marginLeft: 'auto' }} testid="import-retry" onClick={() => { forced.current = false; setStateQ(null); run.reset(); run.start({ steps: IMPORT_STEPS, stepMs: 900 }) }}>Retry</Button></div>
        </div>
      )}
      {status === 'done' && (
        <div className="k-card flat" style={{ padding: 12, borderColor: 'var(--green)', background: 'var(--green-100)' }} data-testid="import-done">
          <div className="row"><Icon name="check-circle" size={16} style={{ color: 'var(--green)' }} /><b>Imported {fmtInt(b?.counts.motifs ?? 410)} motifs · {b?.counts.spikeTrains ?? 16} spike trains · grouping g-01</b></div>
          <div className="row" style={{ marginTop: 8 }}>
            <span className="lib-cap">{sendToReview ? 'queue “Library · import drop_motifs5” created for Review' : 'not sent to Review'}</span>
            <Button variant="primary" iconRight="arrow-right" style={{ marginLeft: 'auto' }} testid="open-library" onClick={() => { run.reset(); push({ text: 'demo: showing the canon catalogue (g-07, 1,402 motifs) — the imported g-01 catalogue has no fixture' }); navigate('library/recurrence') }}>Open the library</Button>
          </div>
        </div>
      )}
      <div className="row" style={{ gap: 10 }} data-testid="import-footer">
        {run.busy ? (
          <>
            <span className="mono small muted">job l-0032 · {run.status === 'queued' ? 'queued' : `${run.step + 1}/${run.steps.length} ${run.steps[run.step]}`}</span>
            <ProgressBar value={run.fraction} width={200} testid="import-progress" />
            <span style={{ marginLeft: 'auto' }} />
            <Button testid="import-cancel" disabled={!cancellable} disabledReason="entries are being written — cancelling now would leave a partial import" onClick={() => { run.cancel(); run.reset(); setStateQ(null); forced.current = false; push({ text: 'Import cancelled · nothing was written' }) }}>Cancel import</Button>
          </>
        ) : status === 'done' ? null : (
          <>
            <Checkbox checked={sendToReview} onChange={setSendToReview} testid="send-to-review" label={`then send ${fmtInt(b?.counts.motifs ?? 410)} to Review as a queue`} disabled={!!blocked} disabledReason={blocked ?? undefined} />
            <span style={{ marginLeft: 'auto' }} />
            <Button className="lib-ui-btn" testid="import-cancel" onClick={leave}>Cancel</Button>
            <Button variant="primary" icon="download" testid="import-run" className="lib-ui-btn" disabled={!b || !!blocked || dry.loading || status === 'failed'} disabledReason={!b || dry.loading ? 'the dry run is still checking' : status === 'failed' ? 'retry the failed import above' : blocked ?? ''}
              onClick={() => { forced.current = false; doneOnce.current = false; run.start({ steps: IMPORT_STEPS, stepMs: 900 }) }}>Import {fmtInt(b?.counts.motifs ?? 410)} motifs</Button>
          </>
        )}
      </div>
    </div>
  )
}

export type { ImportBundle }
