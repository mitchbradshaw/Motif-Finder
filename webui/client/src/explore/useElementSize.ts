/* Element size through a callback ref, so the observer follows the element when it is swapped or mounted
   later (charts/useSize binds once on mount; the Signal tiers mount and unmount as the drawer opens). */
import { useCallback, useEffect, useState } from 'react'

export function useElementSize<T extends HTMLElement>(): [(el: T | null) => void, { width: number; height: number }] {
  const [el, setEl] = useState<T | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const ref = useCallback((node: T | null) => setEl(node), [])
  useEffect(() => {
    if (!el) return
    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        const { width, height } = e.contentRect
        setSize(s => (Math.abs(s.width - width) > 0.5 || Math.abs(s.height - height) > 0.5 ? { width, height } : s))
      }
    })
    ro.observe(el)
    setSize(s => (Math.abs(s.width - el.clientWidth) > 0.5 ? { width: el.clientWidth, height: el.clientHeight } : s))
    return () => ro.disconnect()
  }, [el])
  return [ref, size]
}
