/* polish (2026-10-19): the "about …" expander — the long explanation of a card, a block or a page, closed by default.
 * Near-siblings: `InfoTip` (a popover for a sentence or two — use it when the text fits one breath) and
 * `SectionCard collapsible` (folds a whole card, including its controls). `About` folds only prose: the method, the
 * paper, the caveats, the "how this is measured". Its body stays in the DOM while closed (`hidden`), so a `data-testid`
 * moved into it is still found by the smoke walk's `expect`; but it is not visible, so never move an element a smoke
 * state `wait_for`s. Text moved in here drops its grey class: the body is text-2 on a tinted strip, one click away. */
import { useState, type ReactNode, type CSSProperties } from 'react'
import { Icon } from './icons'
import { cx, tid, type TestIdProps } from './portal'

export interface AboutProps extends TestIdProps {
  /** the summary line, e.g. "about this block", "how this is measured" */
  label?: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  style?: CSSProperties
  className?: string
}

export function About({ label = 'about', children, defaultOpen = false, style, className, ...t }: AboutProps) {
  const [open, setOpen] = useState(defaultOpen)
  const id = tid(t)
  return (
    <div className={cx('k-about', open && 'open', className)} style={style} data-testid={id}>
      <button type="button" className="k-about-toggle" aria-expanded={open} onClick={() => setOpen(o => !o)}
        data-testid={id ? `${id}-toggle` : undefined}>
        <Icon name="info" size={12} />
        <span>{label}</span>
        <Icon name="chevron-down" size={11} className="chev" />
      </button>
      <div className="k-about-body" hidden={!open} data-testid={id ? `${id}-body` : undefined}>{children}</div>
    </div>
  )
}
