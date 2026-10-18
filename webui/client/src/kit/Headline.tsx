/* ig-pages: three figures lead, the rest fold (the researcher, 2026-10-15 / 2026-10-18).
 *
 * `Headline` draws the lead figures full-width in the order given, then ONE "more (N)" toggle over everything
 * else. Folded by default; whether it is open is remembered per page in localStorage, so a researcher who opens
 * the rest once keeps it open there. Storage is a convenience: a private window or blocked storage still folds
 * and opens, it just forgets. Near-sibling: `SectionCard collapsible` folds ONE card and remembers nothing; a
 * native `<details>` per item is what the pages had, and that is N toggles, not one. */
import { useState, type ReactNode } from 'react'

export interface HeadlineFold {
  /** a stable key (React's, and the folded item's `data-fold` attribute) */
  key: string
  node: ReactNode
}
export interface HeadlineProps {
  /** the page this layout belongs to: the localStorage key is `ub-headline:<page>` */
  page: string
  /** the lead figures, drawn full-width in order */
  leads: ReactNode
  /** everything else, behind one toggle; falsy nodes are dropped and not counted */
  folded: (HeadlineFold | null | false | undefined)[]
  /** the toggle's words before the count (default "more") */
  label?: string
  testid?: string
}

const KEY = (page: string) => `ub-headline:${page}`
function readOpen(page: string): boolean {
  try { return localStorage.getItem(KEY(page)) === '1' } catch { return false }
}
function writeOpen(page: string, open: boolean) {
  try { localStorage.setItem(KEY(page), open ? '1' : '0') } catch { /* not remembered; still toggles */ }
}

export function Headline({ page, leads, folded, label = 'more', testid = 'headline' }: HeadlineProps) {
  const items = folded.filter((f): f is HeadlineFold => !!f && f.node !== null && f.node !== undefined && f.node !== false)
  const [open, setOpen] = useState(() => readOpen(page))
  const toggle = () => setOpen(o => { writeOpen(page, !o); return !o })
  return (
    <div className="k-headline" data-testid={testid} data-page={page}>
      <div className="k-headline-leads" data-testid={`${testid}-leads`}>{leads}</div>
      {items.length > 0 && (
        <div className="k-headline-more" data-testid={`${testid}-more`} data-open={open ? '1' : '0'}>
          <button type="button" className="k-headline-toggle" onClick={toggle} aria-expanded={open} data-testid={`${testid}-toggle`}>
            <span aria-hidden>{open ? '▾' : '▸'}</span> {label} ({items.length})
          </button>
          {open && <div className="k-headline-folded" data-testid={`${testid}-folded`}>
            {items.map(f => <div key={f.key} data-fold={f.key}>{f.node}</div>)}
          </div>}
        </div>
      )}
    </div>
  )
}
