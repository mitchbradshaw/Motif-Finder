/* Four collapsed ribbon cards along the bottom (frame explore-2): Filters & search · Annotations N ·
   Detections N · Keyboard shortcuts. Each opens the drawer (frames 2b–2d) on its tab; Filters & search
   opens Annotations with the filters expanded and the first filter focused (backlog D1). */
import { fmtInt, Icon } from '../kit'

export type DrawerTab = 'annotations' | 'detections' | 'shortcuts'
type Key = 'filters' | DrawerTab

export function Ribbons({ totals, onOpen, demo }: { totals: { annotations: number; detections: number }; onOpen: (tab: DrawerTab, focusFilters?: boolean) => void; demo: boolean }) {
  const Row = ({ k, label, n, title }: { k: Key; label: string; n?: number; title: string }) => (
    <button type="button" className="card ex-ribbon" onClick={() => (k === 'filters' ? onOpen('annotations', true) : onOpen(k))} data-testid={`ribbon-${k}`} title={title}>
      <Icon name="chevron-right" size={13} className="chev" /><span>{label}</span>{n !== undefined && <span className="n">{fmtInt(n)}</span>}
    </button>
  )
  return (
    <div className="ex-ribbons" data-testid="ribbons">
      <Row k="filters" label="Filters & search" title="open the drawer on Annotations with its filters focused (/)" />
      <Row k="annotations" label="Annotations" n={totals.annotations} title={`every annotation on this channel${demo ? ' (demo canon)' : ''} (1)`} />
      <Row k="detections" label="Detections" n={totals.detections} title={`every detection on this channel${demo ? ' (demo canon)' : ''} (2)`} />
      <Row k="shortcuts" label="Keyboard shortcuts" title="the keyboard map (3 or ?)" />
    </div>
  )
}
