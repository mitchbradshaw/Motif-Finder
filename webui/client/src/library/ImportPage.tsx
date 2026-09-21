/* library.import — frame library-5 (spec §8.7): the empty Motifs section (two ways in) beside the motif import
 * dry run, now on the bridge.
 *
 * What changed when this went live:
 *   - the bundle list is a READ (`getImportBundles()` → `GET /api/library/import/bundles`, the registry, not a
 *     disk rescan). The old three-value `?bundle=` enum addressed three fixture paths that name no real file;
 *     `?bundle=` now carries the bundle's own path.
 *   - the dry run is `POST /api/library/import/dry-run`, which drives the real importer under `dry_run=True`.
 *     Its checks, creates, counts and sample are the importer's, not the page's: nothing here rewrites a check
 *     or invents a "0 new entries" line any more.
 *   - Import is a REAL JOB. `POST /api/library/import` returns `{job_id}`; this page polls `GET /api/jobs/{id}`
 *     and cancels through `POST /api/jobs/{id}/cancel`. The simulated job `library.import.l-0032`, its four
 *     invented step labels and the `?state=running|failed|done` deep links are gone — a page that can show a
 *     finished import without one having run is a page that lies.
 *   - "Library now" reads its families and grouping from the resolved grouping instead of printing `10` and
 *     `g-07` as fact.
 *
 * Still synthesised, and it is the one thing left: the sample thumbnails are drawn by `motifShape(shape, amp,
 * seed)`. The bridge returns `shape: 'drop'` for every sample (the store carries no shape vocabulary), so these
 * are shape-of-a-drop glyphs at the sample's real amplitude — not decimated signal. They are labelled as a
 * sample, never as evidence.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Checkbox, Chip, Icon, KeyValue, MiniTrace, Page, ProgressBar, SelectField, StatRow, StatTile, fmtInt, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { dryRunImport, getImportBundles, getLibraryCounts, motifShape, type ImportBundle, type ImportBundleRef } from '../api/library'
import { cancelJob, getJob, startLibraryImport, type JobRow } from '../api'
import { LoadFailed, SectionBar, useEmptyLibrary, useExternalNavKey, useGroupingState, useQueueToast } from './chrome'
import { EmptyLibraryCard } from './EmptyLibrary'

export function ImportPage() {
  const [empty] = useEmptyLibrary()
  const counts = useSourced(getLibraryCounts, [])
  const grouping = useGroupingState('motifs')
  const navKey = useExternalNavKey()
  const selectRef = useRef<HTMLDivElement>(null)
  const focusBundle = () => selectRef.current?.querySelector('select')?.focus()
  /* families and the grouping id are the resolved grouping's own, and say so when there is none: an unGrouped
     library is a real state, not a missing number. */
  const families = grouping.loading ? '…' : grouping.grouping ? fmtInt(grouping.grouping.families) : '— no grouping yet'
  const groupingId = grouping.loading ? '…' : grouping.grouping?.id ?? '— none saved'
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
                <KeyValue align="right" items={[
                  { k: 'motifs', v: counts.data ? fmtInt(counts.data.motifs) : '…' },
                  { k: 'families', v: families },
                  { k: 'grouping', v: groupingId },
                  { k: 'spike trains', v: counts.data ? fmtInt(counts.data.spikeTrains) : '…' },
                ]} />
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

/** The live job this page is driving, flattened out of `JobRow`. `null` until one is started. */
interface ImportJob { id: number; status: JobRow['status']; message: string; fraction: number | null; error: string | null; result: unknown }

function jobOf(r: JobRow): ImportJob {
  const p = (r.progress ?? {}) as { done?: number; total?: number | null; message?: string }
  const total = typeof p.total === 'number' && p.total > 0 ? p.total : null
  return {
    id: r.job_id, status: r.status,
    message: String(p.message ?? ''),
    fraction: total != null && typeof p.done === 'number' ? Math.max(0, Math.min(1, p.done / total)) : null,
    error: r.error ? (typeof r.error === 'string' ? r.error : (r.error as { message?: string }).message ?? JSON.stringify(r.error)) : null,
    result: r.result ?? null,
  }
}

/** `{ created: 410, duplicate: 12 }` out of the import job's report, for the done card. The report is the
 *  importer's own `as_dict()`; a key it does not carry is simply not printed. */
function reportLine(result: unknown): string | null {
  const r = (result as { report?: Record<string, unknown> } | null)?.report
  if (!r || typeof r !== 'object') return null
  const parts: string[] = []
  const n = (k: string) => (typeof r[k] === 'number' ? (r[k] as number) : null)
  const created = n('n_created'), dup = n('n_duplicate'), rows = n('n_rows')
  if (created != null) parts.push(`${fmtInt(created)} new entries`)
  if (dup != null) parts.push(`${fmtInt(dup)} already held`)
  if (!parts.length && rows != null) parts.push(`${fmtInt(rows)} rows read`)
  return parts.length ? parts.join(' · ') : null
}

function ImportPanel({ empty, selectRef }: { empty: boolean; selectRef: React.RefObject<HTMLDivElement | null> }) {
  const bundles = useSourced(getImportBundles, [])
  const [bundleQ, setBundleQ] = useQueryState('bundle', '')
  const list: ImportBundleRef[] = bundles.data ?? []
  /* No default bundle id: the first bundle the registry lists is the default, and when the registry lists none
     there is nothing to import — which the panel says rather than addressing a path that does not exist. */
  const chosen = list.find(b => b.path === bundleQ) ?? list[0] ?? null
  const bundle = chosen?.path ?? ''
  const [sendToReview, setSendToReview] = useState(true)
  const [rotate, setRotate] = useState(0)
  const [open, setOpen] = useState<string | null>(null)
  const [job, setJob] = useState<ImportJob | null>(null)
  const [startError, setStartError] = useState<Error | null>(null)
  const { push } = useToast()
  const queue = useQueueToast()

  const dry = useSourced(
    () => (bundle ? dryRunImport(bundle, chosen?.kind) : Promise.resolve({ data: null as ImportBundle | null, source: 'live' as const })),
    [bundle, chosen?.kind])

  const busy = job != null && (job.status === 'queued' || job.status === 'running')
  /* Poll the real job. `getJob` is the same row the Jobs workspace reads; nothing here invents a step label or
     a duration. Polling stops the moment the job leaves a live status. */
  useEffect(() => {
    if (!job || !busy) return
    let live = true
    const id = window.setInterval(async () => {
      try {
        const row = await getJob(job.id)
        if (live) setJob(jobOf(row))
      } catch (e) {
        if (live) setJob(j => (j ? { ...j, status: 'failed', error: `lost the job stream: ${(e as Error).message}` } : j))
      }
    }, 800)
    return () => { live = false; window.clearInterval(id) }
  }, [job, busy])

  const doneOnce = useRef(false)
  useEffect(() => {
    if (job?.status !== 'completed' || doneOnce.current) return
    doneOnce.current = true
    if (sendToReview && dry.data) queue(`Library · import ${chosen?.name ?? bundle}`, dry.data.counts.motifs)
  }, [job?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const leave = () => { navigate(empty ? 'library/recurrence?library=empty' : 'library/recurrence') }
  const start = async () => {
    setStartError(null); doneOnce.current = false
    try {
      const r = await startLibraryImport(bundle, chosen?.kind)
      setJob({ id: r.job_id, status: (r.status as JobRow['status']) ?? 'queued', message: '', fraction: null, error: null, result: null })
    } catch (e) { setStartError(e as Error) }
  }

  const b = dry.data
  /* The ONLY reason an import is refused is the one the bridge gives. The page used to synthesise
     "nothing new to import" for any populated library and rewrite the importer's own duplicate check to match;
     both were invented. The importer already reports how many rows this library holds, in its own words. */
  const blocked = b?.blockedReason ?? null
  const checks = b?.checks ?? []
  const creates = b?.creates ?? []
  const sample = useMemo(() => {
    if (!b?.sample.length) return []
    const k = rotate % b.sample.length
    return [...b.sample.slice(k), ...b.sample.slice(0, k)].slice(0, 9)
  }, [b, rotate])
  const traces = useMemo(() => sample.map(s => motifShape(s.shape, s.amp, s.seed, { n: 70 })), [sample])
  const yDomain: [number, number] = [-0.35, 0.35]
  const motifs = b?.counts.motifs ?? null
  const done = job?.status === 'completed'
  const failed = job?.status === 'failed'
  const cancelled = job?.status === 'cancelled'

  return (
    <div className="k-card" style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 12, minHeight: 618 }} data-testid="import-panel">
      <div className="row">
        <Icon name="download" size={16} />
        <b style={{ fontSize: 16 }}>Import motifs</b>
        {done ? <Chip tone="green" size="sm" icon="check">imported · job {job!.id}</Chip>
          : busy ? <Chip tone="blue" size="sm">importing · job {job!.id}</Chip>
            : <Chip tone="blue" size="sm">dry run · nothing written yet</Chip>}
        <span style={{ marginLeft: 'auto' }} />
        <Button variant="ghost" icon="x" aria-label="close the import" testid="import-close" onClick={leave} />
      </div>
      <div className="stack" style={{ gap: 4 }}>
        <span className="lib-cap" style={{ fontSize: 11 }}>bundle</span>
        <div className="row" ref={selectRef}>
          <SelectField value={bundle} width={400} testid="bundle-select" ariaLabel="bundle" disabled={busy || !list.length}
            disabledReason={busy ? 'an import is running' : 'the registry lists no importable bundle'}
            onChange={v => { setBundleQ(v === list[0]?.path ? null : v); setJob(null) }}
            options={list.length ? list.map(p => ({ value: p.path, label: `${p.name} · ${p.path}`, disabled: p.heldOut, reason: p.heldOut ? 'held out and locked (D6)' : undefined }))
              : [{ value: '', label: 'no registered bundle' }]} />
          {b && (b.provenanceFound ? <Chip tone="green" size="sm" testid="provenance-chip">provenance recorded</Chip> : <Chip tone="red" size="sm" testid="provenance-chip">no provenance on the bundle</Chip>)}
          {b?.heldOut && <Chip tone="grey" size="sm" icon="lock">held out</Chip>}
        </div>
        {chosen && <span className="lib-cap">{chosen.kind}{chosen.registeredAt ? ` · registered ${chosen.registeredAt}` : ' · registration date not recorded'}</span>}
      </div>
      {bundles.error && <LoadFailed what="the importable bundles" error={bundles.error} onRetry={bundles.reload} />}
      {!bundles.loading && !bundles.error && !list.length && (
        <div className="k-card flat" style={{ padding: 12 }} data-testid="no-bundles">
          <b>No importable bundle is registered</b>
          <div className="lib-cap" style={{ marginTop: 4 }}>the list comes from the artifact registry, not from a disk scan — register a bundle in Settings › Datasets and it appears here</div>
        </div>
      )}
      {dry.error && <LoadFailed what="the bundle" error={dry.error} onRetry={dry.reload} />}
      {(dry.loading || bundles.loading) && <div className="stack" style={{ gap: 8 }} data-testid="dry-run-checking">{[0, 1, 2, 3, 4].map(i => <div key={i} className="skeleton" style={{ height: i === 0 ? 50 : 16 }} />)}<span className="lib-cap">checking…</span></div>}
      {b && !dry.loading && <>
        <StatRow columns={4}>
          <StatTile label="motifs" value={fmtInt(b.counts.motifs)} />
          <StatTile label="spike trains" value={b.counts.spikeTrains} />
          <StatTile label="recordings" value={b.counts.recordings} />
          <StatTile label="channels" value={b.counts.channels} />
        </StatRow>
        <div className="stack" style={{ gap: 6 }} data-testid="import-checks">
          <b style={{ fontSize: 13 }}>Checks</b>
          {checks.length ? (
            <div className="lib-checks">
              {checks.map((c, i) => (
                <div key={`${c.title}-${i}`}>
                  <button type="button" className={`lib-check ${c.status} lib-plain`} style={{ width: '100%', cursor: c.items || c.link ? 'pointer' : 'default' }} aria-expanded={c.items || c.link ? open === c.title : undefined} data-testid={`check-${c.status}`}
                    onClick={() => (c.items || c.link) && setOpen(o => (o === c.title ? null : c.title))}>
                    <Icon name={c.status === 'ok' ? 'check-circle' : c.status === 'warn' ? 'alert-triangle' : 'x-circle'} size={14} className="ic" />
                    <span>{c.title}</span>{(c.items || c.link) && <Icon name={open === c.title ? 'chevron-up' : 'chevron-down'} size={11} />}
                    <span className="detail">{c.detail}</span>
                  </button>
                  {open === c.title && <div className="lib-cap" style={{ margin: '4px 0 4px 22px', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {c.items?.map(i2 => <span key={i2}>{i2}</span>)}
                    {c.link && <Button variant="link" size="sm" onClick={() => navigate(c.link!.to)}>{c.link.label} →</Button>}
                  </div>}
                </div>
              ))}
            </div>
          ) : <span className="lib-cap">the importer reported no checks for this bundle</span>}
        </div>
        <div className="stack" style={{ gap: 6 }} data-testid="import-creates">
          <b style={{ fontSize: 13 }}>What the import creates</b>
          {creates.length ? <div className="lib-creates">{creates.map(c => <span key={c}><span className="plus">+</span>{c}</span>)}</div>
            : <span className="lib-cap">the dry run reports no outcomes for this bundle — nothing would be written</span>}
        </div>
        <div className="stack" style={{ gap: 6 }} data-testid="import-sample">
          <div className="row"><b style={{ fontSize: 13 }}>Sample</b><span className="lib-cap">{b.heldOut ? 'withheld' : sample.length ? `${sample.length} of ${fmtInt(b.counts.motifs)} · shared mV scale · shape glyph at the sample's amplitude, not signal` : 'the dry run returned no sample'}</span>
            <Button variant="link" icon="shuffle" style={{ marginLeft: 'auto' }} testid="import-resample" disabled={!!b.heldOut || b.sample.length <= 9} disabledReason={b.heldOut ? 'nothing from a held-out recording is sampled' : 'the dry run returned no more than nine samples'} onClick={() => setRotate(s => s + 1)}>resample</Button></div>
          {b.heldOut ? <div className="lib-locked" style={{ width: 'auto' }} data-testid="sample-withheld"><span className="row" style={{ gap: 6 }}><Icon name="lock" size={13} />sample withheld — this bundle is held out and locked (D6); nothing from it is shown or imported</span></div> : <div className="row" style={{ gap: 6 }}>
            {sample.map((s, i) => <MiniTrace key={`${s.id}-${i}`} values={traces[i]} yDomain={yDomain} width={62} height={42} ground="grey" zeroLine={false} title={`motif ${s.id} · ${s.recording} · ${s.channel} · ${s.onsetH} h · ${s.durationS} s${s.provisional ? ' (provisional)' : ''}`} style={{ borderRadius: 4 }} />)}
          </div>}
        </div>
      </>}
      <span style={{ marginTop: 'auto' }} />
      {startError && <LoadFailed what="the import job" error={startError} onRetry={start} />}
      {(failed || cancelled) && job && (
        <div className="error-card" role="alert" data-testid="import-failed">
          <b>Import job {job.id} {cancelled ? 'was cancelled' : 'failed'}{job.message ? ` at “${job.message}”` : ''}</b>
          {job.error && <div className="mono small" style={{ color: 'var(--red)', margin: '4px 0' }}>{job.error}</div>}
          <div className="row"><span className="lib-cap">the import commits once, at the end — a job that did not finish wrote nothing</span><Button size="sm" icon="refresh" style={{ marginLeft: 'auto' }} testid="import-retry" onClick={start}>Retry</Button></div>
        </div>
      )}
      {done && job && (
        <div className="k-card flat" style={{ padding: 12, borderColor: 'var(--green)', background: 'var(--green-100)' }} data-testid="import-done">
          <div className="row"><Icon name="check-circle" size={16} style={{ color: 'var(--green)' }} /><b>Imported from {chosen?.name ?? bundle}{reportLine(job.result) ? ` · ${reportLine(job.result)}` : ''}</b></div>
          <div className="lib-cap" style={{ marginTop: 4 }}>imports are not verdicts — every entry arrives unjudged, and no grouping is computed by the import</div>
          <div className="row" style={{ marginTop: 8 }}>
            <span className="lib-cap">{sendToReview ? 'queue created for Review' : 'not sent to Review'}</span>
            <Button variant="primary" iconRight="arrow-right" style={{ marginLeft: 'auto' }} testid="open-library" onClick={() => { setJob(null); navigate('library/recurrence') }}>Open the library</Button>
          </div>
        </div>
      )}
      <div className="row" style={{ gap: 10 }} data-testid="import-footer">
        {busy && job ? (
          <>
            <span className="mono small muted">job {job.id} · {job.status === 'queued' ? 'queued' : job.message || 'running'}</span>
            <ProgressBar value={job.fraction ?? 0} indeterminate={job.fraction == null} width={200} testid="import-progress" />
            <span style={{ marginLeft: 'auto' }} />
            <Button testid="import-cancel" onClick={async () => {
              try { const r = await cancelJob(job.id); push({ text: r.note || 'cancel requested' }) } catch (e) { push({ text: `cancel refused: ${(e as Error).message}` }) }
            }}>Cancel import</Button>
          </>
        ) : done ? null : (
          <>
            <Checkbox checked={sendToReview} onChange={setSendToReview} testid="send-to-review" label={motifs == null ? 'then send the imported entries to Review as a queue' : `then send ${fmtInt(motifs)} to Review as a queue`} disabled={!!blocked} disabledReason={blocked ?? undefined} />
            <span style={{ marginLeft: 'auto' }} />
            <Button className="lib-ui-btn" testid="import-cancel" onClick={leave}>Cancel</Button>
            <Button variant="primary" icon="download" testid="import-run" className="lib-ui-btn" disabled={!b || !!blocked || dry.loading || !motifs}
              disabledReason={!b || dry.loading ? 'the dry run is still checking' : blocked ?? (!motifs ? 'the dry run found nothing to import' : '')}
              onClick={start}>{motifs == null ? 'Import' : `Import ${fmtInt(motifs)} motifs`}</Button>
          </>
        )}
      </div>
    </div>
  )
}

export type { ImportBundle }
