/* Shared chrome for the six Analyse › Training pages (frames training-0 … training-4).
 * The Interrogation builder owns a look-alike toolbar in src/interrogation/ — the two cannot share a
 * file (brief: build your toolbar/ribbon in your own directory), so this is the training copy. */
import { useRef, useState, type ReactNode } from 'react'
import {
  Badge, Button, ChainRibbon, Dropdown, Heatmap, Icon, InfoTip, KeyValue, Modal, NumberField, Popover, ProgressBar,
  TextField, fmtInt, recordDemoWrite, type BadgeStatus,
} from '../kit'
import { navigate } from '../state'
import { useToast } from '../shell/Toast'
import { CANON_TEMPLATES, CHANNEL, HISTORY_RUNS, IMPORT_TEMPLATES, NULL_SPEC, RECORDING, SOURCE_CHOICES, SPAN_H, WINDOWS, type TrainingBlock } from '../fixtures/training'
import type { SourceKind } from '../api/training'
import './training.css'

/* ----------------------------------------------------------- loading / failure ----------------------------------------------------------- */
export function Loading({ what = 'this block' }: { what?: string }) {
  return <div className="tr-loading" data-testid="loading"><ProgressBar indeterminate width={200} label={`loading ${what}…`} /></div>
}

/** Loud failure (brief): a failed read is a red card with the error, never a blank. */
export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry: () => void }) {
  return (
    <div className="tr-failed" role="alert" data-testid="load-failed">
      <div className="t"><Icon name="alert-triangle" size={15} />could not load {what}</div>
      <pre>{error.message}</pre>
      <Button size="sm" icon="refresh" onClick={onRetry} testid="load-retry">Retry</Button>
    </div>
  )
}

/* ----------------------------------------------------------- heatmap helpers ----------------------------------------------------------- */
/** Distinct-but-invisible axis labels: the kit heatmap keys its rows and columns by their label, so a
 * column of empty strings would collide (React duplicate keys are a console error, and this build fails
 * loudly on those). Widening runs of spaces read as blank and stay unique. */
export const blanks = (n: number) => Array.from({ length: n }, (_, i) => ' '.repeat(i + 1))

/** The window matrix's heatmap shape: z-scores clipped at ±3σ, one column per time bin, no printed values. */
export function Heat({ rows, values, cellHeight = 11, selectedCols, onCellClick, testid, cols, rowLabelWidth = 118 }: {
  rows: string[]; values: number[][]; cellHeight?: number; selectedCols?: number[]
  onCellClick?: (r: number, c: number) => void; testid?: string; cols?: string[]; rowLabelWidth?: number
}) {
  const columns = cols ?? blanks(values[0]?.length ?? 0)
  return (
    <Heatmap rows={rows} cols={columns} values={values} domain={[-3, 3]} ramp="diverging" showValues={false}
      cellHeight={cellHeight} gap={1} rowLabelWidth={rowLabelWidth} colLabelHeight={0} legend={false}
      selectedCols={selectedCols} onCellClick={onCellClick} testid={testid} />
  )
}

/* ----------------------------------------------------------- null chip (P10) ----------------------------------------------------------- */
export function NullChip() {
  return (
    <span className="tr-chip null" data-testid="null-chip" title="every training result carries a null (P10)">
      <span className="tr-dot" style={{ background: 'var(--green)' }} />
      <span className="mono">null {NULL_SPEC.label}</span>
      <InfoTip title="The null on this chain">
        {NULL_SPEC.detail}
        <div style={{ marginTop: 8 }}><Button size="sm" variant="link" icon="external" onClick={() => navigate('settings/nulls')}>Settings › Nulls →</Button></div>
      </InfoTip>
    </span>
  )
}

/* ----------------------------------------------------------- name chip ----------------------------------------------------------- */
const NAME_RE = /^[a-z0-9_]+$/
export function nameError(v: string): string | null {
  if (!v.trim()) return 'a template name is required'
  if (!NAME_RE.test(v)) return 'lowercase letters, digits and _ only'
  if (v.length > 40) return '40 characters at most'
  return null
}

export function NameChip({ name, saved, onRename }: { name: string; saved: boolean; onRename: (v: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(name)
  const err = nameError(draft)
  if (!editing) {
    return (
      <button type="button" className="tr-chip name btn" data-testid="name-chip" title="rename this training chain"
        onClick={() => { setDraft(name); setEditing(true) }}>
        {name}<Icon name="pencil" size={12} /><span className="st">{saved ? 'saved' : 'unsaved'}</span>
      </button>
    )
  }
  const commit = () => { if (!err) { onRename(draft); setEditing(false) } }
  return (
    <span className="tr-chip name" data-testid="name-chip-edit" style={{ gap: 4 }}>
      <TextField value={draft} onChange={setDraft} width={190} variant="outline" autoFocus invalid={!!err} ariaLabel="chain name"
        testid="name-field" onEnter={commit} />
      <Button size="sm" icon="check" onClick={commit} disabled={!!err} disabledReason={err ?? undefined} testid="name-commit" aria-label="rename" />
      {err && <span className="k-field-error" role="alert" data-testid="name-error"><Icon name="alert-circle" size={11} />{err}</span>}
    </span>
  )
}

/* ----------------------------------------------------------- source chip + popover ----------------------------------------------------------- */
export function SourceChip({ source, open, onToggle, chipRef }: {
  source: SourceKind; open: boolean; onToggle: () => void; chipRef: React.RefObject<HTMLButtonElement | null>
}) {
  const human = source === 'human-windows'
  return (
    <button ref={chipRef} type="button" className={`tr-chip source btn${human ? ' human' : ''}`} onClick={onToggle}
      aria-expanded={open} data-testid="source-chip" title="change the source this training chain runs over">
      <Icon name={human ? 'checklist' : 'wave'} size={13} />
      <span className="mono">{human ? `Window set · 412 human-labelled windows` : `Signal · ${CHANNEL} · span 0–${SPAN_H} h`}</span>
      <Icon name="chevron-down" size={12} />
    </button>
  )
}

export function SourcePopover({ open, onClose, anchorRef, source, onPick }: {
  open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLElement | null>; source: SourceKind; onPick: (s: SourceKind) => void
}) {
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-start" width={430} title="Source for this training chain"
      subtitle="§6.2 · what the source emits decides which stages exist (P15)" testid="source-popover">
      <div className="k-menu" role="menu">
        {SOURCE_CHOICES.map(s => (
          <button key={s.value} type="button" role="menuitem" className="k-menu-item" data-testid={`source-${s.value}`}
            aria-current={source === s.value} onClick={() => { onPick(s.value as SourceKind); onClose() }}>
            <span className="body">
              <span>{s.label}{(s as { illustrative?: boolean }).illustrative && <Badge tone="amber" size="sm">illustrative</Badge>}</span>
              <span className="desc">{s.description}</span>
              <span className="hint mono">emits {s.kind}</span>
            </span>
          </button>
        ))}
      </div>
    </Popover>
  )
}

/* ----------------------------------------------------------- history / import popovers ----------------------------------------------------------- */
export function HistoryPopover({ open, onClose, anchorRef }: { open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLElement | null> }) {
  const { push } = useToast()
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-end" width={430} title="History"
      subtitle="runs in this installation · a run applies its recipe to the source in hand (P2)" testid="history-popover">
      <div className="k-menu" role="menu">
        {HISTORY_RUNS.map(r => (
          <button key={r.id} type="button" role="menuitem" className="k-menu-item" data-testid={`history-${r.id}`}
            aria-disabled={r.disabled || undefined} title={r.disabled ? r.reason : 'apply this run to the source in hand'}
            onClick={() => { if (r.disabled) return; onClose(); push({ text: `applied #${r.id} ${r.template} to the source in hand` }); navigate('analyse/interrogation') }}>
            <span className="body">
              <span>{r.label}</span><span className="desc mono">{r.template} · terminal {r.terminal}</span>
              {r.disabled && <span className="reason">⊘ {r.reason}</span>}
            </span>
          </button>
        ))}
      </div>
    </Popover>
  )
}

export function ImportPopover({ open, onClose, anchorRef }: { open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLElement | null> }) {
  const { push } = useToast()
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-end" width={430} title="Import a template"
      subtitle="§6.1 · detection / interrogation / training are filters over the 14 saved templates" testid="import-popover">
      <div className="k-menu" role="menu">
        {IMPORT_TEMPLATES.map(t => (
          <button key={t.value} type="button" role="menuitem" className="k-menu-item" data-testid={`import-${t.value}`}
            aria-disabled={t.disabled || undefined} title={t.disabled ? t.reason : t.description}
            onClick={() => {
              if (t.disabled) return
              onClose()
              if (t.value === 'drop_motifs9') { push({ text: `imported ${t.value} · detection chain (terminal SpanSet)` }); navigate('analyse/chain') }
              else push({ text: `imported ${t.value} · training chain (terminal Model)` })
            }}>
            <span className="body">
              <span>{t.label}</span><span className="desc">{t.description}</span>
              {t.disabled && <span className="reason">⊘ {t.reason}</span>}
            </span>
          </button>
        ))}
      </div>
    </Popover>
  )
}

/* ----------------------------------------------------------- toolbar ----------------------------------------------------------- */
export interface ToolbarProps {
  /** omitted on the chain page: it *is* the full chain. */
  showBack?: boolean
  backLabel?: string
  onBack?: () => void
  name: string
  saved: boolean
  onRename: (v: string) => void
  source: SourceKind
  onSource: (s: SourceKind) => void
  sourceOpen: boolean
  onSourceToggle: () => void
  estimate: ReactNode
  estimateTone?: 'muted' | 'amber' | 'purple'
  primary: ReactNode
  historyOpen: boolean
  onHistory: () => void
  importOpen: boolean
  onImport: () => void
  onSaveTemplate: () => void
  extra?: ReactNode
  /** block pages draw the back button, the chips, the estimate, Save template and the primary (frames 01 … 4) */
  minimal?: boolean
  /** with `minimal`, still draw Save template (every block frame does) */
  showSave?: boolean
}

export function TrainingToolbar(p: ToolbarProps) {
  const sourceRef = useRef<HTMLButtonElement>(null)
  const histRef = useRef<HTMLButtonElement>(null)
  const impRef = useRef<HTMLButtonElement>(null)
  return (
    <div className="tr-toolbar" data-testid="training-toolbar">
      {p.showBack && (
        <Button variant="ghost" icon="chevron-left" onClick={p.onBack} testid="full-chain">{p.backLabel ?? 'full chain'}</Button>
      )}
      <NameChip name={p.name} saved={p.saved} onRename={p.onRename} />
      <SourceChip source={p.source} open={p.sourceOpen} onToggle={p.onSourceToggle} chipRef={sourceRef} />
      <SourcePopover open={p.sourceOpen} onClose={p.onSourceToggle} anchorRef={sourceRef} source={p.source} onPick={p.onSource} />
      {p.extra}
      <span className="k-spacer" />
      <NullChip />
      <span className={`tr-estimate ${p.estimateTone ?? 'muted'}`} data-testid="estimate">{p.estimate}</span>
      {!p.minimal && <>
        <Button ref={histRef} icon="clock" onClick={p.onHistory} testid="history">History</Button>
        <HistoryPopover open={p.historyOpen} onClose={p.onHistory} anchorRef={histRef} />
        <Button ref={impRef} icon="download" onClick={p.onImport} testid="import">Import</Button>
        <ImportPopover open={p.importOpen} onClose={p.onImport} anchorRef={impRef} />
      </>}
      {(!p.minimal || p.showSave) && <Button icon="save" onClick={p.onSaveTemplate} testid="save-template">Save template</Button>}
      {p.primary}
    </div>
  )
}

/* ----------------------------------------------------------- chain ribbon card ----------------------------------------------------------- */
export function ChainCard({ chain, current, status, onSelect, onAddStage }: {
  chain: TrainingBlock[]; current: string; status: Record<string, BadgeStatus>; onSelect: (b: TrainingBlock) => void; onAddStage: () => void
}) {
  return (
    <div className="k-card tr-ribbon-card" data-testid="chain-ribbon-card">
      <span className="tr-muted tr-small" style={{ flex: 'none' }}>chain</span>
      <ChainRibbon
        variant="chips" current={current} testid="chain-ribbon"
        onSelect={id => { const b = chain.find(x => x.id === id); if (b) onSelect(b) }}
        blocks={chain.map(b => ({
          id: b.id, index: b.index ?? undefined,
          label: b.id === 'source' ? <span>● {b.label}</span> : b.label,
          signature: b.signature, status: status[b.id],
        }))}
        trailing={
          <span className="tr-ribbon-end">
            <Button variant="subtle" icon="plus" onClick={onAddStage} testid="add-stage" aria-label="insert a stage" />
            <InfoTip title="Why this is a training chain (§6.1)">
              A chain is a detector, an interrogation or a training chain because of what its last block emits — a `SpanSet` makes a detector, features over a `SpanSet` an interrogation, a `Model` a training chain. The three names survive only as filters over saved templates.
            </InfoTip>
          </span>
        }
      />
    </div>
  )
}

/* ----------------------------------------------------------- unapplied-changes bar ----------------------------------------------------------- */
export function UnappliedBar({ pending, why, staleLabel, onRevert, onApply, revertReason, stage, busy, onCancel }: {
  pending: boolean; why: string; staleLabel?: string | null; onRevert: () => void; onApply: () => void
  revertReason?: string; stage: string; busy?: boolean; onCancel?: () => void
}) {
  const primaryLabel = pending ? `Apply & re-run from ${stage}` : staleLabel ? `Re-run from ${staleLabel}` : `Apply & re-run from ${stage}`
  return (
    <div className="k-card tr-unapplied" data-testid="unapplied-bar">
      <span className="tr-dot" style={{ background: pending ? 'var(--amber)' : 'var(--muted-2)' }} data-testid="unapplied-dot" />
      <span className="state" data-testid="unapplied-state">{pending ? '1 unapplied change' : 'No unapplied changes'}</span>
      <span className="why" data-testid="unapplied-why">{why}</span>
      <span className="k-spacer" />
      <Button icon="undo" onClick={onRevert} disabled={!!revertReason} disabledReason={revertReason} testid="revert">Revert to recommended</Button>
      {busy
        ? <Button variant="danger" icon="stop" onClick={onCancel} testid="cancel-run">Cancel</Button>
        : <Button variant="primary" icon="refresh" onClick={onApply} testid="apply-rerun"
            disabled={!pending && !staleLabel} disabledReason={!pending && !staleLabel ? 'no unapplied changes' : undefined}>{primaryLabel}</Button>}
    </div>
  )
}

/* ----------------------------------------------------------- run veil ----------------------------------------------------------- */
export function RunVeil({ label, fraction }: { label: string; fraction: number }) {
  return <div className="tr-veil" data-testid="run-veil"><ProgressBar value={fraction} width={220} label={label} /></div>
}

/* ----------------------------------------------------------- save-as-template modal ----------------------------------------------------------- */
export function SaveTemplateModal({ open, onClose, defaultName, stages, onSaved }: {
  open: boolean; onClose: () => void; defaultName: string; stages: string[]; onSaved: (name: string) => void
}) {
  const { push } = useToast()
  const [name, setName] = useState(defaultName)
  const err = nameError(name)
  const exists = !err && CANON_TEMPLATES.includes(name)
  const save = () => {
    recordDemoWrite('analyse', 'save-template', { name, kind: 'training', terminal: 'Model', stages })
    recordDemoWrite('library', 'save-template', { name, from: 'Analyse › Training' })
    onSaved(name)
    onClose()
    push({ text: `saved ${name} · in memory (demo) · Library › Templates`, action: { label: 'Open in Library', onClick: () => navigate('library/templates') } })
  }
  return (
    <Modal open={open} onClose={onClose} title="Save template" subtitle="training template · terminal Model" size="md" testid="save-template-modal"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="save" disabled={!!err} disabledReason={err ?? undefined} onClick={save} testid="save-template-confirm">Save</Button></>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <TextField value={name} onChange={setName} block autoFocus invalid={!!err} variant="outline" ariaLabel="template name" testid="template-name" onEnter={() => { if (!err) save() }} />
        {err && <span className="k-field-error" role="alert" data-testid="template-name-error"><Icon name="alert-circle" size={11} />{err}</span>}
        {exists && <span className="tr-muted tr-small" data-testid="template-name-exists">saves a new version of {name}</span>}
      </div>
      <div style={{ marginTop: 12 }}>
        <KeyValue dense items={[
          { k: 'kind', v: 'training template · terminal Model' },
          { k: 'stages', v: stages.join(' › ') },
          { k: 'scope', v: 'the recipe only · the channel and span stay on the run' },
        ]} />
      </div>
    </Modal>
  )
}

/* ----------------------------------------------------------- send-to-Review modal (P13) ----------------------------------------------------------- */
export function SendToReviewModal({ open, onClose, onSent, from = 'training windows' }: {
  open: boolean; onClose: () => void; onSent: (n: number) => void; from?: string
}) {
  const { push } = useToast()
  const [n, setN] = useState(WINDOWS.unreviewed)
  const [blind, setBlind] = useState('blind')
  const over = n > WINDOWS.queueCap
  const err = n < 1 ? 'send at least one window' : over ? `the Review queue holds up to ${fmtInt(WINDOWS.queueCap)} windows` : null
  const send = () => {
    const id = `q-${20 + Math.floor(Math.random() * 60)}`
    recordDemoWrite('review', 'add-queue', { id, source: from, kind: 'training windows', count: n, blind: blind === 'blind' })
    onSent(n)
    onClose()
    push({ text: `queued ${fmtInt(n)} windows to Review · in memory (demo)`, action: { label: 'Open in Review', onClick: () => navigate('review') } })
  }
  return (
    <Modal open={open} onClose={onClose} size="md" title={`Send ${fmtInt(WINDOWS.unreviewed)} unseen windows to Review`}
      subtitle="P13 · windows with no human verdict · the manual-label arm needs them" testid="send-review-modal"
      footerNote={`Review queue holds up to ${fmtInt(WINDOWS.queueCap)} windows`}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="inbox" disabled={!!err} disabledReason={err ?? undefined} onClick={send} testid="send-review-confirm">Send to Review</Button></>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <label className="tr-row-flex">
          <span className="tr-muted tr-small" style={{ width: 110 }}>how many</span>
          <NumberField value={n} onValid={setN} min={1} max={WINDOWS.queueCap} integer unit="windows" width={170} testid="send-review-count" />
        </label>
        <label className="tr-row-flex">
          <span className="tr-muted tr-small" style={{ width: 110 }}>presentation</span>
          <Dropdown value={blind} onChange={setBlind} width={220} options={[
            { value: 'blind', label: 'blind', description: 'no cluster class shown beside the window' },
            { value: 'labelled', label: 'show cluster class', description: 'faster, but anchors the verdict' },
          ]} />
        </label>
        {err && <span className="k-field-error" role="alert" data-testid="send-review-error"><Icon name="alert-circle" size={11} />{err}</span>}
        <KeyValue dense items={[
          { k: 'from', v: `${RECORDING} · ${CHANNEL} · 0–${SPAN_H} h` },
          { k: 'verdicts', v: 'human-only · they never overwrite a cluster class' },
          { k: 'lands in', v: 'Review › queue rail · marked new · this session' },
        ]} />
      </div>
    </Modal>
  )
}

/* ----------------------------------------------------------- save-window-set modal (P18) ----------------------------------------------------------- */
export function SaveWindowSetModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: (id: string) => void }) {
  const { push } = useToast()
  const [id, setId] = useState('ws_M2aug_CH4_600s')
  const err = nameError(id)
  const save = () => {
    recordDemoWrite('library', 'save-window-set', { id, version: 1, channels: [CHANNEL], windows: WINDOWS.total })
    onSaved(id)
    onClose()
    push({ text: `saved ${id} v1 · in memory (demo) · Library › Window sets`, action: { label: 'Open in Library', onClick: () => navigate('library/window-sets') } })
  }
  return (
    <Modal open={open} onClose={onClose} size="md" title="Save window set" subtitle="P18 · the windows and the split, reusable in Models" testid="save-window-set-modal"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="save" disabled={!!err} disabledReason={err ?? undefined} onClick={save} testid="save-window-set-confirm">Save window set</Button></>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <TextField value={id} onChange={setId} block autoFocus invalid={!!err} variant="outline" ariaLabel="window set id" testid="window-set-id" onEnter={() => { if (!err) save() }} />
        {err && <span className="k-field-error" role="alert" data-testid="window-set-error"><Icon name="alert-circle" size={11} />{err}</span>}
      </div>
      <div style={{ marginTop: 12 }}>
        <KeyValue dense items={[
          { k: 'windows', v: `${fmtInt(WINDOWS.total)} · ${WINDOWS.params.length_min} min · stride ${WINDOWS.params.stride_min} min` },
          { k: 'split', v: `blocked by time · ${WINDOWS.params.split} · gap ${WINDOWS.params.gap_min} min` },
          { k: 'channels', v: `${CHANNEL} · ${RECORDING}` },
          { k: 'version', v: 'v1 · a later save with the same id makes v2' },
        ]} />
      </div>
    </Modal>
  )
}

/* ----------------------------------------------------------- block-page frame ----------------------------------------------------------- */
/** The chrome every training block page repeats: toolbar (minimal), chain ribbon, body, unapplied bar. */
export function BlockFrame(p: {
  chain: TrainingBlock[]
  current: string
  status: Record<string, BadgeStatus>
  source: SourceKind
  onSource: (s: SourceKind) => void
  name: string
  saved: boolean
  onRename: (v: string) => void
  estimate: ReactNode
  estimateTone?: 'muted' | 'amber' | 'purple'
  primary: ReactNode
  backLabel?: string
  onBack?: () => void
  onNavigate: (b: TrainingBlock) => void
  onAddStage: () => void
  /** draws Save template in the block toolbar (every block frame has one) */
  onSaveTemplate?: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  const [sourceOpen, setSourceOpen] = useState(false)
  return (
    <>
      <TrainingToolbar
        minimal showBack backLabel={p.backLabel} onBack={p.onBack}
        name={p.name} saved={p.saved} onRename={p.onRename}
        source={p.source} onSource={p.onSource}
        sourceOpen={sourceOpen} onSourceToggle={() => setSourceOpen(o => !o)}
        estimate={p.estimate} estimateTone={p.estimateTone}
        historyOpen={false} onHistory={() => {}} importOpen={false} onImport={() => {}}
        showSave={!!p.onSaveTemplate} onSaveTemplate={p.onSaveTemplate ?? (() => {})}
        primary={p.primary}
      />
      <ChainCard chain={p.chain} current={p.current} status={p.status} onSelect={p.onNavigate} onAddStage={p.onAddStage} />
      {p.children}
      {p.footer}
    </>
  )
}
