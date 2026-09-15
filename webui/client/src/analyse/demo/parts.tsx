/* Toolbar pieces shared by the demo chain page and the demo block pages (frames chain-1 … chain-8): name chip with
 * rename, source chip with its popover, surrogate toggle / null chip, estimate text, the shared time axis, the save
 * template modal and the run log modal. */
import { useRef, useState, type ReactNode } from 'react'
import { TimeAxis } from '../../charts/primitives'
import { makeX } from '../../charts/scale'
import { scaleLinear } from 'd3'
import { useSize } from '../../charts/useSize'
import { Button, Chip, CodeBlock, Field, Icon, InfoTip, Modal, Popover, TextField, Toggle, recordDemoWrite, setDemo } from '../../kit'
import { navigate } from '../../state'
import type { DemoScenario, DemoSource } from '../../api/analyse'
import type { DemoChainState } from './chainState'

const NAME_RE = /^[A-Za-z0-9_][A-Za-z0-9_ ·.-]{0,39}$/
export function nameProblem(name: string): string | null {
  if (!name.trim()) return 'a template needs a name'
  if (!NAME_RE.test(name.trim())) return 'letters, digits, _ · . - and spaces only, up to 40 characters'
  return null
}

export function DemoNameChip({ st, onRename }: { st: DemoChainState; onRename: (n: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(st.name)
  const problem = nameProblem(draft)
  const commit = () => { if (!problem) { if (draft.trim() !== st.name) onRename(draft.trim()); setEditing(false) } }
  const tone = st.note.includes('failed') ? 'red' : st.note.includes('paused') ? 'amber' : null
  return (
    <span className="an-name" data-testid="chain-name" title={editing ? problem ?? 'Enter to rename · Escape to cancel' : 'click to rename'} onClick={() => { if (!editing) { setDraft(st.name); setEditing(true) } }}
      style={editing && problem ? { borderColor: 'var(--red)' } : undefined}>
      {editing ? <input autoFocus value={draft} aria-label="chain name" aria-invalid={!!problem} onChange={e => setDraft(e.target.value)} onBlur={() => (problem ? (setDraft(st.name), setEditing(false)) : commit())}
        onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { setDraft(st.name); setEditing(false) } }} data-testid="chain-name-input" />
        : <b style={{ fontWeight: 600 }}>{st.name}</b>}
      <Icon name="pencil" size={11} />
      <span className="state" style={tone ? { color: tone === 'red' ? '#b3262b' : '#a05e00' } : undefined} data-testid="chain-note">{st.note}</span>
      {editing && problem && <span className="state" style={{ color: '#b3262b' }}>{problem}</span>}
    </span>
  )
}

export function DemoSourceChip({ source }: { source: DemoSource }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  return (
    <>
      <button ref={ref} className="an-source" onClick={() => setOpen(o => !o)} data-testid="source-chip" title={`${source.recording} · ${source.channel}`}>
        <Icon name="wave" size={13} /><span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{source.chip}</span><Icon name="chevron-down" size={11} />
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={ref} title="Source" subtitle="single channel · one span (P3)" width={400} testid="source-popover">
        <div className="an-pop-item"><Chip tone="blue" size="sm">current</Chip><span>{source.recording} · {source.chip.replace(/^Signal( span)? · /, '')}</span></div>
        <button className="an-pop-item btnlike" style={{ width: '100%', border: 0, background: 'transparent', textAlign: 'left' }} onClick={() => navigate('explore/signal/4')} data-testid="source-pick-explore"><Icon name="arrow-right" size={12} /> Pick another span in Explore</button>
        <button className="an-pop-item btnlike" style={{ width: '100%', border: 0, background: 'transparent', textAlign: 'left' }} onClick={() => navigate('analyse/chain')} data-testid="source-live-chain"><Icon name="database" size={12} /> Leave the demo · the live chain on the bridge's adapters</button>
        <div className="an-pop-item" style={{ color: 'var(--muted)' }} title="M4_aug_concat_fs1.mat is held out (D6): every workspace refuses it" data-testid="source-held-out">
          <Icon name="lock" size={12} /> M4_aug · CH4_A2 <Chip tone="grey" size="sm">held out · refused (D6)</Chip>
        </div>
      </Popover>
    </>
  )
}

export function NullControl({ sc, st, onToggle }: { sc: DemoScenario; st: DemoChainState; onToggle: () => void }) {
  if (sc.null.kind === 'chip') {
    return <span className="an-toggle-wrap" data-testid="null-chip"><span style={{ width: 7, height: 7, borderRadius: 9, background: 'var(--green)' }} /><span className="mono" style={{ fontSize: 11.5 }}>{sc.null.label.replace(/^null /, '')}</span><span className="mono muted" style={{ fontSize: 11 }}>null</span><InfoTip title="Null">The chain is judged against this surrogate: every stage is re-run on 200 surrogate signals and each result is compared against them.</InfoTip></span>
  }
  return (
    <span className="an-toggle-wrap" data-testid="surrogate-toggle">
      <Toggle checked={st.surrogate} onChange={onToggle} label={<span className="mono" style={{ fontSize: 11.5 }}>surrogate <b>{st.surrogate ? '200×' : 'off'}</b></span>} ariaLabel="surrogate runs" />
      <InfoTip title="Surrogate">On by default (§6.3). Every run is repeated on 200 phase-randomised surrogates so the counts can be read against chance. Off: faster, no chance comparison.</InfoTip>
    </span>
  )
}

export function EstimateText({ text, tone }: { text: string; tone: 'amber' | 'blue' | 'red' | 'green' | 'grey' }) {
  return <span className={`an-est ${tone === 'grey' ? '' : tone}`} style={tone === 'grey' ? { color: 'var(--muted)' } : undefined} data-testid="estimate-chip">{text}</span>
}

export function DemoAxis({ t0, t1 }: { t0: number; t1: number }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(10, size.width)
  const x = makeX(t0, t1, w)
  const spanH = (t1 - t0) / 3600
  const hourTicks = spanH >= 1 ? scaleLinear().domain([t0 / 3600, t1 / 3600]).ticks(spanH > 100 ? 5 : 6) : null
  return (
    <div className="an-axis" data-testid="footer-axis">
      <span className="lbl">all rows share this time axis</span>
      <div ref={ref} style={{ height: 22, marginLeft: 10 }}>{size.width > 0 && (hourTicks
        ? <svg width={w} height={22} className="time-axis"><line x1={0} x2={w} y1={2} y2={2} stroke="var(--border)" />{hourTicks.map(h => { const px = x(h * 3600); return <g key={h} transform={`translate(${px},2)`}><line y1={0} y2={4} stroke="var(--border-strong)" /><text y={14} textAnchor={px < 24 ? 'start' : w - px < 30 ? 'end' : 'middle'}>{spanH > 100 ? `${Math.round(h)} h` : `${h.toFixed(2)} h`}</text></g> })}</svg>
        : <svg width={w} height={22}><TimeAxis x={x} y={2} t0={t0} t1={t1} n={6} ends /></svg>)}</div>
    </div>
  )
}

/** Save template (spec §6.3): name validated while typing, version bumped, written to the in-memory store. */
export function SaveTemplateModal({ open, onClose, st, onSave, kind }: { open: boolean; onClose: () => void; st: DemoChainState; onSave: (name: string, version: string) => void; kind: string }) {
  const [name, setName] = useState(st.name === 'untitled chain' ? '' : st.name)
  const problem = nameProblem(name)
  const version = st.name === name && st.template === 'drop_motifs9' ? 'v4' : 'v1'
  return (
    <Modal open={open} onClose={onClose} title="Save as template" subtitle={`${st.steps.length} blocks · ${kind}`} size="sm" testid="save-template-modal"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" icon="save" disabled={!!problem || !st.steps.length} disabledReason={!st.steps.length ? 'an empty chain cannot be saved' : problem ?? undefined} onClick={() => { onSave(name.trim(), version); onClose() }} testid="save-template-confirm">Save {version}</Button></>}>
      <Field label="name" error={name ? problem ?? undefined : undefined} hint={!name ? 'required' : undefined}><TextField value={name} onChange={setName} invalid={!!name && !!problem} autoFocus block testid="save-template-name" onEnter={() => { if (!problem) { onSave(name.trim(), version); onClose() } }} /></Field>
      <div className="mono muted" style={{ fontSize: 11, marginTop: 10 }}>version {version}{version === 'v4' ? ' (was v3)' : ''} · kind {kind} · templates store no recording or span — scores stay with runs</div>
    </Modal>
  )
}

export function RunLogModal({ open, onClose, lines, title }: { open: boolean; onClose: () => void; lines: string; title: string }) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="lg" testid="run-log-modal" footer={<Button onClick={onClose}>Close</Button>}>
      <CodeBlock code={lines} title="traceback" filename="run.log" lineNumbers />
    </Modal>
  )
}

export function FooterCard({ terminal, headline, sub, actions }: { terminal: ReactNode; headline: ReactNode; sub: ReactNode; actions: ReactNode }) {
  return (
    <div className="card an-footer" data-testid="chain-footer">
      {terminal}
      <span className="divider-v" style={{ height: 34 }} />
      <div style={{ minWidth: 0 }}>
        <div className="head" data-testid="footer-headline">{headline}</div>
        <div className="sub">{sub}</div>
      </div>
      <div className="acts">{actions}</div>
    </div>
  )
}

export function writeHpcJob(template: string, stage: string) {
  const job = { id: 'j-0218', kind: 'cluster', title: `matrix profile · CH4_A2 whole channel · ${template} stage ${stage}`, status: 'queue', detail: 'SLURM script created · not yet submitted', for: template, created: Date.now() }
  recordDemoWrite('jobs', 'add-job', job)
  setDemo<{ id: string; title: string; for: string }[]>('analyse.hpcJobs', prev => [...(prev ?? []).filter(j => j.id !== job.id), { id: job.id, title: job.title, for: template }])
  recordDemoWrite('analyse', 'create-slurm-script', { template, stage, job: job.id })
  return job
}
