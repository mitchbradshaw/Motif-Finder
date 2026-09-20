/* Shared chrome for the three Analyse › Interrogation pages (frames interrogation-1 … 3c).
 * The Training builder owns a look-alike toolbar in src/training/ — the two cannot share a file, so this
 * one lives here (brief: build your toolbar/ribbon in your own directory). */
import { useRef, useState, type ReactNode } from 'react'
import {
  Badge, Button, ChainRibbon, EmptyState, Icon, InfoTip, KeyValue, Modal, Popover, ProgressBar, TextField,
  recordDemoWrite, type BadgeStatus,
} from '../kit'
import { navigate } from '../state'
import { useToast } from '../shell/Toast'
import { ESTIMATE, NULL_SPEC, type ChainBlock } from '../fixtures/interrogation'
import './interrogation.css'

/* ----------------------------------------------------------- loading / failure ----------------------------------------------------------- */
export function Loading({ what = 'this block' }: { what?: string }) {
  return <div className="ig-loading" data-testid="loading"><ProgressBar indeterminate width={200} label={`loading ${what}…`} /></div>
}

/** Loud failure (brief): a failed read is a red card with the error, never a blank. */
export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry: () => void }) {
  return (
    <div className="ig-failed" role="alert" data-testid="load-failed">
      <div className="t"><Icon name="alert-triangle" size={15} />could not load {what}</div>
      <pre>{error.message}</pre>
      <Button size="sm" icon="refresh" onClick={onRetry} testid="load-retry">Retry</Button>
    </div>
  )
}

/* ----------------------------------------------------------- null chip (P10) ----------------------------------------------------------- */
/** `method` follows 02 Aggregate's null parameter, so the chip never names a null the page is not
 *  drawing (critique r1: switching to shuffled onsets left the chip reading matched windows). */
export function NullChip({ method = 'matched' }: { method?: string }) {
  const label = method === 'shuffled' ? 'shuffled onsets' : method === 'none' ? 'switched off' : NULL_SPEC.label
  const off = method === 'none'
  return (
    <span className="ig-chip null" data-testid="null-chip" title="every interrogation result carries a null (P10)">
      <span className="ig-dot" style={{ background: off ? 'var(--amber)' : 'var(--green)' }} />
      <span className="mono">null {label}{off ? '' : ` · ${NULL_SPEC.repeats}`}</span>
      <InfoTip title="The null on this chain">
        {NULL_SPEC.detail}
        <div style={{ marginTop: 8 }}><Button size="sm" variant="link" icon="external" onClick={() => navigate('settings/nulls')}>Settings › Nulls →</Button></div>
      </InfoTip>
    </span>
  )
}

/* ----------------------------------------------------------- toolbar ----------------------------------------------------------- */
export interface ToolbarProps {
  /** null on the source page: it *is* the full chain. */
  backDisabledReason?: string
  sourceLabel: ReactNode
  sourceOpen: boolean
  onSourceToggle: () => void
  sourceRef: React.RefObject<HTMLButtonElement | null>
  arrived?: boolean
  stale?: boolean
  primary: ReactNode
  children?: ReactNode          // the source picker popover
  /** the null method the page is drawing, for the chip (02 Aggregate's `null` parameter) */
  nullMethod?: string
  onSaveTemplate: () => void
}

export function InterrogationToolbar(p: ToolbarProps) {
  return (
    <div className="ig-toolbar" data-testid="interrogation-toolbar">
      <Button variant="ghost" icon="chevron-left" onClick={() => navigate('analyse/interrogation')}
        disabled={!!p.backDisabledReason} disabledReason={p.backDisabledReason} testid="full-chain">full chain</Button>
      <button ref={p.sourceRef} type="button" className="ig-chip source btn" onClick={p.onSourceToggle} aria-expanded={p.sourceOpen} data-testid="source-chip"
        title="change the SpanSet this chain runs over">
        <span className="ig-muted">source</span><Icon name="library" size={13} /><span className="mono">{p.sourceLabel}</span><Icon name="chevron-down" size={12} />
      </button>
      {p.children}
      {p.arrived && <span className="ig-muted ig-small" data-testid="arrived-note">arrived via Analyse events</span>}
      <span className="k-spacer" />
      <NullChip method={p.nullMethod} />
      <span className={`ig-estimate mono ${p.stale ? 'amber' : ''}`} data-testid="estimate">
        {p.stale ? `${ESTIMATE.stale} · ${ESTIMATE.staleNote}` : `${ESTIMATE.cached} · ${ESTIMATE.cachedNote}`}
      </span>
      <Button onClick={p.onSaveTemplate} testid="save-template">Save as template</Button>
      {p.primary}
    </div>
  )
}

/* ----------------------------------------------------------- chain ribbon card ----------------------------------------------------------- */
export function ChainCard({ chain, current, status, onSelect, onAddStage }: {
  chain: ChainBlock[]; current: string; status: Record<string, BadgeStatus>; onSelect: (id: string) => void; onAddStage: () => void
}) {
  return (
    <div className="k-card ig-ribbon-card" data-testid="chain-ribbon-card">
      <span className="ig-muted ig-small ig-ribbon-label">chain</span>
      <ChainRibbon
        variant="chips" current={current} onSelect={onSelect} testid="chain-ribbon"
        blocks={chain.map(b => ({
          id: b.id, index: b.index ?? undefined, label: b.id === 'source' ? <span>● {b.label}</span> : b.label,
          signature: b.signature, status: status[b.id],
        }))}
        trailing={<Button variant="subtle" icon="plus" onClick={onAddStage} testid="add-stage">stage</Button>}
      />
      <span className="k-spacer" />
      <span className="ig-terminal mono" data-testid="terminal-type">
        <span>terminal type <b>Features</b> <InfoTip title="Modes are not modes (§6.1)">
          A chain is a detector, an interrogation or a training chain because of what its last block emits — `SpanSet` makes a detector, features over a `SpanSet` an interrogation, `Model` a training chain. The three names survive only as filters over saved templates.
        </InfoTip></span>
        <span className="ig-muted">this chain is an interrogation</span>
      </span>
    </div>
  )
}

/* ----------------------------------------------------------- save-as-template modal ----------------------------------------------------------- */
const NAME_RE = /^[a-z0-9_]+$/
const CANON_TEMPLATES = ['drop_motifs9', 'sharkfin_v2', 'mp_discord_v3', 'spike_shape_v1', 'cnn_detect_cluster_v1', 'drop_cnn_v1', 'sharkfin_cnn_v2']

export function SaveTemplateModal({ open, onClose, defaultName, stages }: { open: boolean; onClose: () => void; defaultName: string; stages: string[] }) {
  const { push } = useToast()
  const [name, setName] = useState(defaultName)
  const err = !name.trim() ? 'a template name is required' : !NAME_RE.test(name) ? 'lowercase letters, digits and _ only' : null
  const exists = !err && CANON_TEMPLATES.includes(name)
  const save = () => {
    recordDemoWrite('analyse', 'save-template', { name, kind: 'interrogation', terminal: 'Features', stages })
    recordDemoWrite('library', 'save-template', { name, from: 'Analyse › Interrogation' })
    onClose()
    push({ text: `saved ${name} · in memory (demo) · Library › Templates`, action: { label: 'Open in Library', onClick: () => navigate('library/templates') } })
  }
  return (
    <Modal open={open} onClose={onClose} title="Save as template" subtitle="interrogation template · terminal Features" size="md" testid="save-template-modal"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="save" disabled={!!err} disabledReason={err ?? undefined} onClick={save} testid="save-template-confirm">Save</Button></>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <TextField value={name} onChange={setName} block autoFocus invalid={!!err} variant="outline" ariaLabel="template name" testid="template-name" onEnter={() => { if (!err) save() }} />
        {err && <span className="k-field-error" role="alert" data-testid="template-name-error"><Icon name="alert-circle" size={11} />{err}</span>}
        {exists && <span className="ig-muted ig-small" data-testid="template-name-exists">saves a new version of {name}</span>}
      </div>
      <div style={{ marginTop: 12 }}>
        <KeyValue dense items={[
          { k: 'kind', v: 'interrogation template · terminal Features' },
          { k: 'stages', v: stages.join(' › ') },
          { k: 'scope', v: 'the recipe only · member exclusions stay on the run' },
        ]} />
      </div>
    </Modal>
  )
}

/* ----------------------------------------------------------- "+ stage" popover ----------------------------------------------------------- */
export function AddStagePopover({ open, onClose, anchorRef, onPick }: {
  open: boolean; onClose: () => void; anchorRef: React.RefObject<HTMLElement | null>; onPick: (kind: 'slope' | 'spike-shape') => void
}) {
  return (
    <Popover open={open} onClose={onClose} anchorRef={anchorRef} placement="bottom-start" width={380} title="Insert a feature block"
      subtitle="one block per analysis type (P7) · Aggregate is wired from whatever it emits" testid="add-stage-popover">
      <div className="k-menu" role="menu">
        {[
          { key: 'slope' as const, label: '01 Resolve spans — slope analysis', d: 'SpanSet → Features · depth, duration, max slope, peakedness' },
          { key: 'spike-shape' as const, label: '01 Spike shape', d: 'SpanSet → Features · amplitude, half-width, rise, decay' },
        ].map(o => (
          <button key={o.key} type="button" role="menuitem" className="k-menu-item" data-testid={`add-stage-${o.key}`} onClick={() => { onPick(o.key); onClose() }}>
            <span className="body"><span>{o.label}</span><span className="desc">{o.d}</span></span>
          </button>
        ))}
        <button type="button" role="menuitem" className="k-menu-item" aria-disabled title="FitzHugh–Nagumo is not registered in this installation" data-testid="add-stage-fhn">
          <span className="body"><span>01 FitzHugh–Nagumo fit</span><span className="desc">SpanSet → Features</span><span className="reason">⊘ not registered in this installation</span></span>
        </button>
      </div>
    </Popover>
  )
}

/* ----------------------------------------------------------- run states ----------------------------------------------------------- */
export function RunVeil({ label, fraction }: { label: string; fraction: number }) {
  return (
    <div className="ig-veil" data-testid="run-veil">
      <ProgressBar value={fraction} width={220} label={label} />
    </div>
  )
}

export function EmptyScope({ onSelectAll }: { onSelectAll: () => void }) {
  return (
    <EmptyState testid="empty-scope" icon="filter" title="no members in scope"
      caption="every member is excluded, so 01 and 02 have nothing to measure"
      action={<Button variant="primary" onClick={onSelectAll} testid="empty-select-all">Select all</Button>} />
  )
}

export function StaleBadge() { return <Badge status="stale" /> }
