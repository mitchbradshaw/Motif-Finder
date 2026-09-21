/* The bridge → store seam for project settings (Prompt 02).
 *
 * A page read (api/settings.ts) fetches GET /api/settings/<page> and calls `hydrateSaved` with the values
 * the table holds and, for the pages whose defaults depend on real data (which recordings and channels
 * exist, which blocks are registered, which storage roots there are), the live defaults. The store's SAVED
 * layer for that page becomes defaults ⊕ saved values; the DEFAULTS layer is replaced so "differs from
 * default" and "Reset page to defaults" mean the spec default for this installation, not the canon's.
 *
 * Lives outside store.ts so api/settings.ts can import it without a cycle (store.ts imports api/settings.ts).
 */
import { getDemo, setDemo } from '../kit'
import { DEFAULTS, type Values } from '../fixtures/settings'

export const STORE_KEY = 'settings.store'
export interface StoreShape {
  saved: Record<string, Values>
  draft: Record<string, Values>
  touched: Record<string, string>
  seeded: Record<string, boolean>
  invalid: Record<string, Record<string, string>>
  hydrated: Record<string, boolean>
}
export const clone = <T,>(v: T): T => { try { return structuredClone(v) } catch { return v } }
export const initStore = (): StoreShape => ({ saved: clone(DEFAULTS), draft: {}, touched: {}, seeded: {}, invalid: {}, hydrated: {} })

/** Replace a page's defaults and set its SAVED layer to defaults ⊕ `values`. Returns the effective saved values. */
export function hydrateSaved(slug: string, values: Values, defaults?: Values): Values {
  if (defaults) DEFAULTS[slug] = clone(defaults)
  const saved: Values = { ...(DEFAULTS[slug] ?? {}), ...values }
  setDemo<StoreShape>(STORE_KEY, s => {
    const cur = s ?? initStore()
    return { ...cur, saved: { ...cur.saved, [slug]: saved }, hydrated: { ...cur.hydrated, [slug]: true } }
  })
  return saved
}

export function savedValues(slug: string): Values {
  return getDemo<StoreShape>(STORE_KEY, initStore).saved[slug] ?? {}
}
