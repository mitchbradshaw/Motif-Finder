import { useEffect, useState } from 'react'

/** Observe an element's width/height (ResizeObserver) so SVG surfaces size to their card.
 *
 *  The returned ref is an object ref whose `current` setter records the element, so the observer
 *  re-binds whenever the measured element is swapped — unmounted and re-mounted, or mounted after
 *  the hook's first render (a plot that appears when a drawer closes or an error card clears).
 *  Binding once on mount left such plots at width 0: a silently blank pane (Explore and Analyse
 *  builders' finding, 2026-09-16). Callers keep using `<div ref={ref}>` unchanged. */
export function useSize<T extends HTMLElement>(): [React.RefObject<T | null>, { width: number; height: number }] {
  const [el, setEl] = useState<T | null>(null)
  const [ref] = useState(() => {
    let cur: T | null = null
    return Object.defineProperty({} as React.RefObject<T | null>, 'current', {
      get: () => cur,
      set: (v: T | null) => { if (v !== cur) { cur = v; setEl(v) } },
      enumerable: true,
    })
  })
  const [size, setSize] = useState({ width: 0, height: 0 })
  useEffect(() => {
    if (!el) return
    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        const { width, height } = e.contentRect
        setSize(s => (Math.abs(s.width - width) > 0.5 || Math.abs(s.height - height) > 0.5) ? { width, height } : s)
      }
    })
    ro.observe(el)
    setSize({ width: el.clientWidth, height: el.clientHeight })
    return () => ro.disconnect()
  }, [el])
  return [ref, size]
}
