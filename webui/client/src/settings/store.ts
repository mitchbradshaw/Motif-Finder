/* The settings store (spec §9 "Shape", §12 P23) — LIVE since Prompt 02.
 *
 * Project pages hold edits as a DRAFT: nothing changes until Save, which PUTs the draft to
 * /api/settings/<page> (the `settings` table; the bridge appends the audit entry), merges the server's
 * answer into the saved layer and raises a toast with the consequence sentence. A failed save keeps the
 * draft and shows the error. Personal pages have no draft — every change applies immediately to this
 * browser and persists in localStorage.
 *
 * Layers per page (settings/hydrate.ts fills them from the page read):
 *   DEFAULTS — what "Reset page to defaults" stages (spec §9 defaults, live-shaped where they depend on data)
 *   SAVED    — defaults ⊕ the settings table (hydrated by the page's read in api/settings.ts)
 *   SEEDS    — the scripted edit `?state=unsaved` stages so a screenshot reproduces the frame
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { setDemo, useDemoState } from '../kit'
import { ApiError, putSettingsPage } from '../api'
import { useToast } from '../shell/Toast'
import {
  CONSEQUENCE, DEFAULTS, HELD_OUT_STEM, PAGE_META, SEEDS, SEED_SENTENCE, SLUGS, genericConsequence,
  type Scope, type Values,
} from '../api/settings'
import { STORE_KEY, clone, initStore, type StoreShape } from './hydrate'

export interface PendingChange { id: string; from: unknown; to: unknown; consequence: string }

const KEY = STORE_KEY
const init = initStore

/** Values edited on one page that are the same value on another (spec §9.8 / §9.10 sequences). */
const SHARED: Record<string, { slug: string; id: string }[]> = {
  'review-queues:seq_gap': [{ slug: 'library-groupings', id: 'seq_gap' }],
  'review-queues:seq_events': [{ slug: 'library-groupings', id: 'seq_events' }],
  'library-groupings:seq_gap': [{ slug: 'review-queues', id: 'seq_gap' }],
  'library-groupings:seq_events': [{ slug: 'review-queues', id: 'seq_events' }],
}

const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

/* ---- personal pages: this browser, localStorage (try/catch: private windows and blocked storage) ---- */
const personalKey = (slug: string) => `settings.personal.${slug}`
function loadPersonal(slug: string): Values | null {
  try { const raw = localStorage.getItem(personalKey(slug)); return raw ? (JSON.parse(raw) as Values) : null } catch { return null }
}
function storePersonal(slug: string, v: Values) {
  try { localStorage.setItem(personalKey(slug), JSON.stringify(v)) } catch { /* not persisted: still applied to this session */ }
}
/** Read the two personal pages back from localStorage once, at first use of the store. */
let personalLoaded = false
function ensurePersonal() {
  if (personalLoaded) return
  personalLoaded = true
  for (const slug of SLUGS) {
    if (PAGE_META[slug]?.scope !== 'personal') continue
    const v = loadPersonal(slug)
    if (v) setDemo<StoreShape>(KEY, s => { const cur = s ?? init(); return { ...cur, saved: { ...cur.saved, [slug]: { ...(cur.saved[slug] ?? {}), ...v } }, hydrated: { ...cur.hydrated, [slug]: true } } })
  }
}

/** The held-out lock (D6) is read outside Settings — the header chip, every picker. Mirror the SAVED
 *  value (never the draft) into its own demo-store key so other workspaces can bind to it. */
export const HELD_OUT_KEY_STORE = 'settings.heldOut'
export interface HeldOutLock { on: boolean; recording: string }
function syncHeldOut(saved: Values) {
  setDemo<HeldOutLock>(HELD_OUT_KEY_STORE, { on: Boolean(saved['heldout.on'] ?? true), recording: String(saved['heldout.recording'] ?? HELD_OUT_STEM) })
}

/** Personal display preferences are read outside Settings (every readout, every table). Mirror them
 *  into their own demo-store key — the same pattern as the held-out lock — so a workspace can bind to
 *  them without importing the settings store. See webui/pages/requests/settings.md. */
export const DISPLAY_PREFS_KEY = 'settings.display'
export interface DisplayPrefs { density: string; time_axis: string; amplitude: string; sample_indices: boolean }
export function publishDisplayPrefs(p: DisplayPrefs) { setDemo<DisplayPrefs>(DISPLAY_PREFS_KEY, p) }

export interface SettingsPageStore {
  slug: string
  scope: Scope
  /** effective value: draft if edited, else saved */
  value: (id: string) => unknown
  str: (id: string) => string
  num: (id: string) => number
  bool: (id: string) => boolean
  list: (id: string) => string[]
  set: (id: string, v: unknown) => void
  /** edited but not saved */
  dirty: (id: string) => boolean
  /** effective value differs from the spec default */
  differs: (id: string) => boolean
  changes: PendingChange[]
  sentence: string
  invalid: Record<string, string>
  markInvalid: (id: string, reason: string | null) => void
  /** write straight to the saved layer AND the server, skipping the draft (the held-out unlock is the
   *  commit, FE1). `confirmName` is the typed name the unlock needs; rejects with the server's message. */
  applyNow: (id: string, v: unknown, confirmName?: string) => Promise<void>
  save: () => Promise<void>
  saving: boolean
  discard: () => void
  resetToDefaults: () => void
  differingCount: number
  /** the page's SAVED layer has been filled from the server (or localStorage for a personal page) */
  hydrated: boolean
}

/** Amber "differs from default" dots for the nav rail — computed per page (B29), never following the open page. */
export function useNavDots(): Record<string, boolean> {
  const [store] = useDemoState<StoreShape>(KEY, init)
  return useMemo(() => {
    const out: Record<string, boolean> = {}
    for (const slug of SLUGS) {
      const eff = { ...(store.saved[slug] ?? {}), ...(store.draft[slug] ?? {}) }
      out[slug] = Object.keys(DEFAULTS[slug] ?? {}).some(k => !same(eff[k], DEFAULTS[slug][k]))
    }
    return out
  }, [store])
}

/** True when any project page holds unsaved edits (the leave guard asks before navigating away). */
export function useAnyDraft(): { slug: string; n: number } | null {
  const [store] = useDemoState<StoreShape>(KEY, init)
  for (const slug of Object.keys(store.draft)) {
    const d = store.draft[slug] ?? {}
    const n = Object.keys(d).filter(k => !same(d[k], store.saved[slug]?.[k])).length
    if (n) return { slug, n }
  }
  return null
}

export function useSettingsPage(slug: string): SettingsPageStore {
  ensurePersonal()
  const [store, setStore] = useDemoState<StoreShape>(KEY, init)
  const [saving, setSaving] = useState(false)
  const { push } = useToast()
  const meta = PAGE_META[slug]
  const scope: Scope = meta?.scope ?? 'project'
  const saved = store.saved[slug] ?? {}
  const draft = store.draft[slug] ?? {}
  const defaults = DEFAULTS[slug] ?? {}

  const value = useCallback((id: string) => (id in draft ? draft[id] : saved[id]), [draft, saved])

  const set = useCallback((id: string, v: unknown) => {
    setStore(s => {
      const next = { ...s, draft: { ...s.draft }, saved: { ...s.saved }, touched: { ...s.touched } }
      const apply = (sl: string, key: string) => {
        if (PAGE_META[sl]?.scope === 'personal') { next.saved[sl] = { ...(next.saved[sl] ?? {}), [key]: v }; storePersonal(sl, next.saved[sl]) }
        else next.draft[sl] = { ...(next.draft[sl] ?? {}), [key]: v }
        next.touched[sl] = key
      }
      apply(slug, id)
      for (const t of SHARED[`${slug}:${id}`] ?? []) apply(t.slug, t.id)
      return next
    })
    if (scope === 'personal') push({ text: 'Applied to this browser', ttlMs: 2000 })
  }, [setStore, slug, scope, push])

  const changes = useMemo<PendingChange[]>(() => Object.keys(draft)
    .filter(k => !same(draft[k], saved[k]))
    .map(k => {
      const from = saved[k], to = draft[k]
      const fn = CONSEQUENCE[k]
      return { id: k, from, to, consequence: fn ? fn(from, to) : genericConsequence(k, from, to) }
    }), [draft, saved])

  const sentence = store.seeded[slug] && SEED_SENTENCE[slug]
    ? SEED_SENTENCE[slug]
    : (changes.find(c => c.id === store.touched[slug]) ?? changes[0])?.consequence ?? ''

  const invalid = store.invalid[slug] ?? {}
  const markInvalid = useCallback((id: string, reason: string | null) => {
    setStore(s => {
      const cur = s.invalid[slug] ?? {}
      if ((cur[id] ?? null) === reason) return s
      const next = { ...cur }
      if (reason) next[id] = reason; else delete next[id]
      return { ...s, invalid: { ...s.invalid, [slug]: next } }
    })
  }, [setStore, slug])

  /** Merge the server's answer for `slug` into the saved layer and clear the keys it covered from the draft. */
  const commit = useCallback((values: Values, keys: string[], clearAll = false) => {
    setStore(s => {
      const savedNext = { ...(s.saved[slug] ?? {}), ...values }
      /* after a save the draft is empty: a key edited back to its saved value was not a change, but it
         would keep the draft non-empty and stop the next ?state=unsaved seed */
      const draftNext = clearAll ? {} : { ...(s.draft[slug] ?? {}) }
      for (const k of keys) delete draftNext[k]
      if (slug === 'datasets') syncHeldOut(savedNext)
      return { ...s, saved: { ...s.saved, [slug]: savedNext }, draft: { ...s.draft, [slug]: draftNext }, seeded: { ...s.seeded, [slug]: false }, hydrated: { ...s.hydrated, [slug]: true } }
    })
  }, [setStore, slug])

  const applyNow = useCallback(async (id: string, v: unknown, confirmName?: string) => {
    const r = await putSettingsPage(slug, { [id]: v }, confirmName)
    commit(r.values, [id])
  }, [slug, commit])

  const save = useCallback(async () => {
    const n = changes.length
    if (!n || saving) return
    const payload: Values = {}
    for (const c of changes) payload[c.id] = c.to
    setSaving(true)
    try {
      const r = await putSettingsPage(slug, payload)
      commit(r.values, changes.map(c => c.id), true)
      push({ text: `Saved · ${sentence || `${n} change${n === 1 ? '' : 's'} applied`}` })
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      push({ text: `Not saved · ${msg}`, kind: 'error' })
      throw e
    } finally {
      setSaving(false)
    }
  }, [changes, saving, slug, commit, push, sentence])

  const discard = useCallback(() => {
    const n = changes.length
    setStore(s => ({ ...s, draft: { ...s.draft, [slug]: {} }, seeded: { ...s.seeded, [slug]: false }, invalid: { ...s.invalid, [slug]: {} } }))
    if (n) push({ text: `Discarded ${n} change${n === 1 ? '' : 's'}` })
  }, [changes.length, setStore, slug, push])

  const resetToDefaults = useCallback(() => {
    const diffs = Object.keys(defaults).filter(k => !same(value(k), defaults[k]))
    if (!diffs.length) return
    setStore(s => {
      const staged: Values = {}
      for (const k of diffs) staged[k] = defaults[k]
      if (scope === 'personal') { const sv = { ...(s.saved[slug] ?? {}), ...staged }; storePersonal(slug, sv); return { ...s, saved: { ...s.saved, [slug]: sv } } }
      return { ...s, draft: { ...s.draft, [slug]: { ...(s.draft[slug] ?? {}), ...staged } }, seeded: { ...s.seeded, [slug]: false } }
    })
    push({ text: scope === 'personal' ? `Reset ${diffs.length} value${diffs.length === 1 ? '' : 's'} · applied to this browser` : `${diffs.length} default${diffs.length === 1 ? '' : 's'} staged · nothing is written until you save` })
  }, [defaults, value, setStore, slug, scope, push])

  const differingCount = useMemo(() => Object.keys(defaults).filter(k => !same(value(k), defaults[k])).length, [defaults, value])

  return {
    slug, scope, value,
    str: (id: string) => String(value(id) ?? ''),
    num: (id: string) => Number(value(id) ?? 0),
    bool: (id: string) => Boolean(value(id)),
    list: (id: string) => (value(id) as string[] | undefined) ?? [],
    set, applyNow,
    dirty: (id: string) => id in draft && !same(draft[id], saved[id]),
    differs: (id: string) => !same(value(id), defaults[id]),
    changes, sentence, invalid, markInvalid, save, saving, discard, resetToDefaults, differingCount,
    hydrated: Boolean(store.hydrated[slug]) || scope === 'personal',
  }
}

/** `?state=unsaved` seeds exactly the frame's edit once, so the save bar reads as drawn. */
export function useSeededDraft(slug: string, on: boolean) {
  const [, setStore] = useDemoState<StoreShape>(KEY, init)
  useEffect(() => {
    if (!on) return
    setStore(s => {
      const cur = s.draft[slug] ?? {}
      if (Object.keys(cur).length) return s
      return { ...s, draft: { ...s.draft, [slug]: clone(SEEDS[slug] ?? {}) }, seeded: { ...s.seeded, [slug]: true } }
    })
  }, [slug, on, setStore])
}
