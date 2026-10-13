/* The path strip (2026-10-13): where this page sits on the typical route through the tool —
   Explore (find a span) → Analyse (run a chain over it) → Review (judge what it found) — with the
   current workspace lit green, the same green as a page's one "next step" button. Discovery and
   Library feed Analyse and Models reads it; in those workspaces a side pill says so. Every pill
   navigates. It answers a new user's "where am I supposed to go next?" without a paragraph of grey
   text. Jobs and Settings sit off the path and show the strip unlit. */
import { Chip, Stepper, type StepItem } from '../kit'
import { navigate, useApp } from '../state'

const MAIN: { key: string; label: string; detail: string; to: string }[] = [
  { key: 'explore', label: 'Explore', detail: 'find a span', to: 'explore/corpus' },
  { key: 'analyse', label: 'Analyse', detail: 'run a chain over it', to: 'analyse/chain' },
  { key: 'review', label: 'Review', detail: 'judge what it found', to: 'review' },
]
const SIDE: Record<string, { label: string; detail: string }> = {
  discovery: { label: 'Discovery', detail: 'feeds Analyse · one template, many channels' },
  library: { label: 'Library', detail: 'feeds Analyse · saved shapes and window sets' },
  models: { label: 'Models', detail: 'reads Analyse · trains on what it produced' },
}

export function PathStrip() {
  const { route } = useApp()
  const ws = route.workspace
  const side = SIDE[ws]
  const steps: StepItem[] = MAIN.map(m => ({
    id: m.key, label: m.label, detail: m.key === ws ? m.detail : undefined, state: m.key === ws ? 'current' : 'todo',
  }))
  return (
    <div className="hdr-path" data-testid="path-strip" data-workspace={ws} aria-label="the typical path through the tool">
      <Stepper steps={steps} variant="numbered" orientation="horizontal" onSelect={i => navigate(MAIN[i].to)} testid="path-steps" />
      {side && <Chip tone="green" size="sm" title={side.detail} testid="path-side">{side.label} · {side.detail.split(' · ')[0]}</Chip>}
      <style>{`
        .hdr-path { display: flex; align-items: center; gap: 10px; flex: none; margin: 0 14px; }
        .hdr-path .k-stepper { gap: 4px; flex-wrap: nowrap; }
        .hdr-path .k-stepper.numbered .k-step { font-size: 11px; gap: 6px; }
        .hdr-path .k-stepper.numbered .circ { width: 19px; height: 19px; font-size: 10px; }
        .hdr-path .k-stepper.numbered .line { width: 16px; }
        .hdr-path .k-stepper.numbered .current .circ { background: var(--green); border-color: var(--green); }
        .hdr-path .k-stepper.numbered .current { color: var(--k-green-text); }
        .hdr-path .k-stepper.numbered .k-step .d { display: none; }
        .hdr-path .k-step-btn { cursor: pointer; border-radius: 6px; padding: 0 3px; }
        .hdr-path .k-step-btn:hover { background: var(--grey-100); }
        .hdr-path .k-step-btn:hover .d { display: inline; }
        @media (max-width: 1240px) { .hdr-path .k-chip { display: none; } }
      `}</style>
    </div>
  )
}
