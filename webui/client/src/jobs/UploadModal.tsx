/* jobs.upload — `#/jobs/run/<runId>/upload` (frame jobs-3, spec §7c.3, P24). Choose the file, see
 * where it will be placed (locked, from the naming convention) and the checks. Nothing is placed
 * until every check passes; a file made with other parameters — or computed on the held-out M4_aug —
 * is refused with the reason. Renders over jobs.paused. */
import { useEffect, useRef } from 'react'
import { Button, Icon, InfoTip, Modal, Popover, useDemoState, useNotWired, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { getUploadFiles, type PausedRun, type ResultCheck, type UploadFile } from '../api/jobs'
import { navigate } from '../state'
import { Checks, LoadFailed, Loading, LockedPath, rangeLabel } from './chrome'
import { continueRun, nowHM, patchRun } from './store'
import { recordDemoWrite } from '../kit'

const isPass = (c: ResultCheck) => c.state === 'pass' || c.state === 'warn'

export function UploadModal({ open, run, onClose }: { open: boolean; run: PausedRun; onClose: () => void }) {
  const data = useSourced(getUploadFiles, [])
  const [fileQ, setFileQ] = useQueryState('file', 'mismatch')
  const [checking, setChecking] = useDemoState<number>(`jobs.upload.${run.id}.checking`, () => 0)
  const anchor = useRef<HTMLButtonElement>(null)
  const [menu, setMenu] = useQueryState('pop', '')
  const notWired = useNotWired()

  // choosing a file re-runs the checks: they tick in one at a time (state `checking`)
  useEffect(() => {
    if (!open || fileQ === 'none') return
    setChecking(0)
    let i = 0
    const t = window.setInterval(() => { i += 1; setChecking(i); if (i >= 6) window.clearInterval(t) }, 140)
    return () => window.clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, fileQ])

  if (!open) return null
  const files = data.data?.files ?? []
  const file: UploadFile | null = fileQ === 'none' ? null : (files.find(f => f.key === fileQ) ?? files[0] ?? null)
  const shown = file ? file.checks.map((c, i) => (i < checking ? c : { ...c, state: 'pending' as const, detail: 'checking…' })) : []
  const settled = checking >= (file?.checks.length ?? 0)
  const passes = !!file && settled && file.checks.every(isPass)
  const noNulls = !!file && file.checks.some(c => c.key === 'nulls' && c.state === 'warn')

  const place = () => {
    if (!file) return
    recordDemoWrite('jobs', 'place-result', { run: run.id, stage: run.pausedAt, file: file.name, at: run.result.path, nulls: !noNulls })
    patchRun(run.id, { result: 'arrived', placedFile: file.name, at: nowHM() })
    continueRun(run)
    if (noNulls) patchRun(run.id, { nullJob: 'null draws sent to the cluster' })
    navigate(`jobs/run/${run.id}`)
  }

  return (
    <Modal open onClose={onClose} size="lg" testid="upload-modal"
      title={<><Icon name="upload" size={15} /> Upload results and continue</>}
      subtitle={`${run.id} · ${run.kindLabel} ${run.template} · stage ${run.pausedAt} of ${run.stageCount} · ${run.stageName} on ${run.recording} ${run.channelsLabel}`}
      footerNote="nothing is placed until every check passes"
      footer={<>
        <Button onClick={onClose} testid="upload-cancel">Cancel</Button>
        <Button variant="primary" icon="play" testid="upload-place" disabled={!passes}
          disabledReason={!file ? 'choose a file first' : !settled ? 'the checks are still running' : 'a check failed — this file cannot continue the run'}
          onClick={place}>Place file and continue</Button>
      </>}>
      {data.error && <LoadFailed what="the upload candidates" error={data.error} onRetry={data.reload} />}
      {data.loading && <Loading height={200} testid="upload-loading" />}
      {data.data && (
        <>
          {file ? (
            <div className="jb-file" data-testid="upload-file">
              <Icon name="file" size={22} className="jb-muted" />
              <div style={{ minWidth: 0 }}>
                <div className="nm">{file.name}</div>
                <div className="sub">{file.size} · {file.from}</div>
              </div>
              <span className="jb-spacer" />
              <Button ref={anchor} variant="link" testid="choose-file" onClick={() => setMenu(menu === 'file' ? null : 'file')}>Choose another file</Button>
            </div>
          ) : (
            <div className="jb-file empty" data-testid="upload-file-empty">
              <Icon name="upload" size={20} className="jb-muted" />
              <div className="jb-mono jb-small jb-muted">no file chosen — the run stays paused</div>
              <Button ref={anchor} size="sm" icon="folder" testid="choose-file" onClick={() => setMenu('file')}>Choose a file…</Button>
            </div>
          )}

          <Popover open={menu === 'file'} onClose={() => setMenu(null)} anchorRef={anchor} width={360} flush testid="file-menu"
            title="Files this browser can offer" subtitle="the demo stands in for the file picker">
            <div className="jb-file-menu">
              {files.map(f => (
                <button key={f.key} type="button" className={`jb-file-opt ${f.key === fileQ ? 'on' : ''}`} data-testid={`file-opt-${f.key}`}
                  onClick={() => { setFileQ(f.key); setMenu(null) }}>
                  <span>{f.name}</span>
                  <span className="s">{f.size} · {f.refusal ? 'refused by the checks' : f.checks.some(c => c.state === 'warn') ? 'passes · no null draws' : 'passes every check'}</span>
                </button>
              ))}
              <button type="button" className={`jb-file-opt ${fileQ === 'none' ? 'on' : ''}`} data-testid="file-opt-none"
                onClick={() => { setFileQ('none'); setMenu(null) }}><span>no file</span><span className="s">clear the choice</span></button>
              <button type="button" className="jb-file-opt" data-testid="file-opt-browse" onClick={() => { setMenu(null); notWired('the operating system file picker') }}>
                <span>Browse this machine…</span><span className="s">needs the bridge</span>
              </button>
            </div>
          </Popover>

          <div className="jb-placed">
            <span className="jb-label">will be placed at</span>
            <LockedPath path={run.result.path} testid="upload-path" />
            <span className="jb-label">named by Storage <InfoTip title="Named by Storage">The path is built from the naming convention in Settings › Storage (§9.11) — it is not yours to choose, so a run always finds its own artifact.</InfoTip></span>
          </div>

          <div className="jb-label">checks</div>
          <Checks testid="upload-checks" checks={shown} />

          {settled && file?.refusal && (
            <div className="jb-refusal" data-testid="upload-refusal" role="alert">
              <div className="t"><Icon name="x-circle" size={14} />{file.refusal.title}</div>
              <div className="d">{file.refusal.body}</div>
              <div className="jb-row" style={{ marginTop: 6 }}>
                <Button size="sm" icon="file" testid="refusal-choose" onClick={() => setMenu('file')}>Choose another file</Button>
                {file.refusal.newRun && (
                  <Button size="sm" icon="branch" testid="refusal-new-run"
                    onClick={() => notWired(`start a new ${run.kindLabel.toLowerCase()} with ${file.refusal!.newRun}`)}>Start a new run with {file.refusal.newRun}</Button>
                )}
              </div>
            </div>
          )}

          {settled && passes && (
            <div className="jb-pass" data-testid="upload-pass"><Icon name="check-circle" size={14} />
              {noNulls
                ? <>The file passes; only its null draws are missing (they run next, below). Place stores it as stage {run.pausedAt}'s artifact and runs {rangeLabel(run.pausedAt + 1, run.stageCount)} locally ({run.remaining}).</>
                : <>Every check passes. Place stores it as stage {run.pausedAt}'s artifact and runs {rangeLabel(run.pausedAt + 1, run.stageCount)} locally ({run.remaining}).</>}
            </div>
          )}

          <div className={`jb-note-amber ${noNulls && settled ? 'on' : ''}`} data-testid="upload-null-note">
            <div className="t">{data.data.nullNote.title}</div>
            {data.data.nullNote.body}
          </div>
        </>
      )}
    </Modal>
  )
}
