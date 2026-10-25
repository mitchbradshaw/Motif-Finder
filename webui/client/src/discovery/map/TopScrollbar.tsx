/* discovery.map.TopScrollbar — level 3's second horizontal scrollbar, above the table. tq-mappage (2026-10-25): moved
 * out of MapPage.tsx unchanged. */
import { useEffect, useRef, useState } from 'react'
import { cx } from '../../kit'

/** night-disc item 4: a thin horizontal scrollbar ABOVE the level-3 table (the researcher: the table's own bar is at the
 *  bottom of a tall block, out of sight), synced both ways with the table's horizontal scroll. Its inner width is chosen
 *  so the two have the same scroll range (the table's vertical scrollbar narrows its client width); a ResizeObserver
 *  keeps it in step when datasets or rows are hidden or the window changes. The row labels stay sticky on the left. */
export function TopScrollbar({ target }: { target: React.RefObject<HTMLDivElement | null> }) {
  const bar = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ inner: 0, overflow: false })
  useEffect(() => {
    const t = target.current, b = bar.current
    if (!t || !b) return
    const measure = () => setSize({ inner: t.scrollWidth - t.clientWidth + b.clientWidth, overflow: t.scrollWidth > t.clientWidth + 1 })
    const fromTable = () => { if (Math.abs(b.scrollLeft - t.scrollLeft) > 1) b.scrollLeft = t.scrollLeft }
    const fromBar = () => { if (Math.abs(t.scrollLeft - b.scrollLeft) > 1) t.scrollLeft = b.scrollLeft }
    t.addEventListener('scroll', fromTable, { passive: true })
    b.addEventListener('scroll', fromBar, { passive: true })
    const ro = new ResizeObserver(measure)
    ro.observe(t)
    if (t.firstElementChild) ro.observe(t.firstElementChild)
    measure()
    return () => { t.removeEventListener('scroll', fromTable); b.removeEventListener('scroll', fromBar); ro.disconnect() }
  }, [target])
  return (
    <div ref={bar} className={cx('dsc-map-topscroll', !size.overflow && 'fits')} data-testid="map-top-scroll" data-overflow={size.overflow ? '1' : '0'} aria-hidden>
      <div style={{ width: size.inner }} />
    </div>
  )
}
