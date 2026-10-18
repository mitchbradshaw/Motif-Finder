/* Reports workspace (docs/prompts/changes/reports.md). Routes:
 *   #/reports                          — every saved snapshot (run, kind, date, open / open folder);
 *   #/reports/detection-run/<run key>  — a Discovery run's report, rendered live by the server.
 *
 * The report is drawn by the SERVER (matplotlib, `Working/reports`): this page only puts the HTML it returns in a
 * container — no iframe, no script — so what the researcher sees here is the file a snapshot writes and the thesis
 * pastes. Save snapshot writes it to disk; Print opens the same page in a tab and asks the browser to print it. */
import { useState } from 'react'
import { Button, Callout, EmptyState, Icon, InfoTip, Page, ProgressBar, TextField, copyToClipboard } from '../kit'
import { live, useSourced } from '../api/seam'
import {
  detectionRunReportPageUrl, getDetectionRunReport, listReports, openReportFolder, reportFileUrl, saveDetectionRunSnapshot,
  type ReportRow,
} from '../api/reports'
import { Header } from '../shell/Header'
import { useToast } from '../shell/Toast'
import { navigate, useApp } from '../state'

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e))

function Failed({ what, error, onRetry }: { what: string; error: Error; onRetry: () => void }) {
  return <Callout tone="red" icon="alert-triangle" title={`Could not load ${what}`} testid="reports-load-failed"
    action={<Button size="sm" variant="primary" icon="refresh" onClick={onRetry}>Retry</Button>}>{error.message}</Callout>
}

function Rendering({ label }: { label: string }) {
  return <div className="k-card" style={{ padding: 24, display: 'flex', gap: 12, alignItems: 'center' }} data-testid="report-rendering">
    <ProgressBar indeterminate size="sm" width={160} labelPosition="none" /><span className="muted">{label}</span></div>
}

/** Print: the report page itself in a tab, printed there — the browser's print saves it as PDF. */
function printPage(url: string) {
  const w = window.open(url, '_blank')
  if (!w) return false
  w.addEventListener('load', () => w.print(), { once: true })
  return true
}

function DetectionRunReportPage({ runKey }: { runKey: string }) {
  const toast = useToast()
  const rep = useSourced(() => live(getDetectionRunReport(runKey)), [runKey])
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<number | null>(null)
  const save = () => {
    setSaving(true)
    saveDetectionRunSnapshot(runKey, note.trim() || undefined)
      .then(s => { setSaved(s.id); toast.push({ text: `snapshot saved · ${s.files.length} files in ${s.path}`, action: { label: 'Open Reports', onClick: () => navigate('reports') } }) })
      .catch(e => toast.push({ text: `the snapshot was not saved · ${errText(e)}` }))
      .finally(() => setSaving(false))
  }
  return (
    <>
      <Header workspace="Reports" page="Detection run" subtitle={runKey} />
      <Page maxWidth={1100}>
        <div className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }} data-testid="report-toolbar" data-saved={saved ?? undefined}>
          <Button size="sm" variant="primary" icon="arrow-left" onClick={() => navigate(`discovery/runs?run=${encodeURIComponent(runKey)}`)} testid="report-back">Back to the run</Button>
          <span className="muted small">The figures and tables behind this run, drawn by the server from the live database each time you open it.</span>
          <InfoTip title="What this report is">
            <p>Every figure is a PNG drawn with matplotlib from the same numbers Discovery shows; every table is also in the Markdown.</p>
            <p><b>Save snapshot</b> writes report.html, report.md and the figures (fig-01-map.png …) into a dated folder under the results folder, and lists it on the Reports page. <b>Print</b> opens the report in a tab and prints it (choose “Save as PDF”).</p>
          </InfoTip>
          <span className="k-spacer" />
          <TextField size="sm" value={note} onChange={setNote} placeholder="note for the snapshot (optional)" width={240} testid="report-note" />
          <Button size="sm" variant="primary" icon="save" loading={saving} disabled={!rep.data} disabledReason="the report is still rendering" onClick={save} testid="report-save">Save snapshot</Button>
          <Button size="sm" variant="primary" icon="file" disabled={!rep.data} disabledReason="the report is still rendering"
            onClick={() => { if (!printPage(detectionRunReportPageUrl(runKey))) toast.push({ text: 'the browser blocked the print tab · allow pop-ups for this page' }) }} testid="report-print">Print</Button>
        </div>
        {rep.error ? <Failed what={`the report for ${runKey}`} error={rep.error} onRetry={rep.reload} />
          : !rep.data ? <Rendering label="drawing the figures — a few seconds" />
            : <div className="k-card" style={{ padding: 20, overflowX: 'auto' }} data-testid="report-body"
              /* the server's own HTML: no script, its style scoped to .ub-report */
              dangerouslySetInnerHTML={{ __html: rep.data.fragment }} />}
      </Page>
    </>
  )
}

function SnapshotRow({ r }: { r: ReportRow }) {
  const toast = useToast()
  // stored in UTC; shown in this machine's time, as the snapshot's folder name is
  const when = r.createdAt ? new Date(r.createdAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—'
  return (
    <tr data-testid={`report-row-${r.id}`}>
      <td>{when}</td>
      <td>{r.kind === 'detection-run' ? 'detection run' : r.kind === 'chain-run' ? 'chain run' : r.kind}</td>
      <td className="mono">{r.runKey ?? (r.runId != null ? `job ${r.runId}` : '—')}</td>
      <td>{r.title ?? '—'}{r.note && <div className="muted small">{r.note}</div>}</td>
      <td className="mono small" style={{ wordBreak: 'break-all' }}>{r.path}{!r.exists && <div className="red small">the folder is no longer on disk</div>}</td>
      <td style={{ whiteSpace: 'nowrap' }}>
        <Button size="sm" variant="primary" icon="external" disabled={!r.exists} disabledReason="the folder is no longer on disk"
          onClick={() => window.open(reportFileUrl(r.id, 'report.html'), '_blank')} testid={`report-open-${r.id}`}>Open</Button>{' '}
        <Button size="sm" variant="primary" icon="folder" disabled={!r.exists} disabledReason="the folder is no longer on disk"
          onClick={() => openReportFolder(r.id).then(() => toast.push({ text: `opened ${r.path}` }))
            .catch(e => { copyToClipboard(r.path); toast.push({ text: `could not open the folder (${errText(e)}) · its path is copied` }) })}
          testid={`report-folder-${r.id}`}>Open folder</Button>{' '}
        <Button size="sm" variant="primary" icon="copy" onClick={() => { copyToClipboard(r.path); toast.push({ text: 'path copied' }) }} testid={`report-copy-${r.id}`}>Copy path</Button>
      </td>
    </tr>
  )
}

function ReportsList() {
  const rows = useSourced(() => live(listReports()), [])
  return (
    <>
      <Header workspace="Reports" page="Saved reports" subtitle="every snapshot, newest first" />
      <Page maxWidth={1300}>
        <div className="row" style={{ gap: 8, alignItems: 'center' }}>
          <span className="muted small">A snapshot is a report frozen on disk: its figures (PNG), its tables (report.md) and the page (report.html), ready to paste into a chapter.</span>
          <InfoTip title="Where reports come from">Open a run in Discovery and press <b>Report</b>, then <b>Save snapshot</b>. The database keeps only each snapshot's folder; the files live there.</InfoTip>
          <span className="k-spacer" />
          <Button size="sm" variant="primary" icon="refresh" onClick={rows.reload} testid="reports-reload">Reload</Button>
        </div>
        {rows.error ? <Failed what="the saved reports" error={rows.error} onRetry={rows.reload} />
          : !rows.data ? <Rendering label="reading the saved reports" />
            : rows.data.length === 0
              ? <EmptyState bordered icon="file" title="No saved reports yet" testid="reports-empty"
                caption="open a run in Discovery, press Report, then Save snapshot"
                action={<Button variant="primary" icon="arrow-right" onClick={() => navigate('discovery/runs')}>Open Discovery</Button>} />
              : (
                <div className="k-card k-table-wrap" style={{ padding: 0 }}>
                  <table className="k-table" data-testid="reports-table" style={{ width: '100%' }}>
                    <thead><tr><th>saved</th><th>kind</th><th>run</th><th>title · note</th><th>folder</th><th /></tr></thead>
                    <tbody>{rows.data.map(r => <SnapshotRow key={r.id} r={r} />)}</tbody>
                  </table>
                </div>
              )}
      </Page>
    </>
  )
}

export function ReportsPage() {
  const { route } = useApp()
  const p = route.parts
  if (!p.length) return <ReportsList />
  if (p[0] === 'detection-run' && p[1]) return <DetectionRunReportPage runKey={decodeURIComponent(p.slice(1).join('/'))} />
  return (
    <>
      <Header workspace="Reports" page="Not found" subtitle={`#/reports/${p.join('/')}`} />
      <Page maxWidth={1100}>
        <EmptyState bordered icon="alert-triangle" testid="reports-unknown-route" title={`No Reports page at “/${p.join('/')}”`}
          caption="Reports has the saved list and one page per detection run (#/reports/detection-run/<run key>)"
          action={<Button variant="primary" onClick={() => navigate('reports')}>Open the saved reports <Icon name="arrow-right" size={12} /></Button>} />
      </Page>
    </>
  )
}
