/* The settings draft store (spec §9 "Shape", §12 P23).
 *
 * Project pages hold edits as a DRAFT: nothing changes until Save, which merges the draft into the
 * in-memory saved values, writes an audit entry and raises a toast with the consequence sentence.
 * Personal pages have no draft — every change applies immediately to this browser.
 *
 * Three layers per page come from the fixtures through api/settings.ts:
 *   DEFAULTS — what "Reset page to defaults" stages
 *   SAVED    — what the frames draw as current (differs from DEFAULTS on the seven dotted pages)
 *   SEEDS    — the scripted edit `?state=unsaved` stages so a screenshot reproduces the frame
 */
import { useCallback, useEffect, useMemo } from 'react'
import { recordDemoWrite, setDemo, useDemoState } from '../kit'
import { useToast } from '../shell/Toast'
import {
  CONSEQUENCE, DEFAULTS, PAGE_META, SAVED, SEEDS, SEED_SENTENCE, SLUGS, genericConsequence,
  type Scope, type Values,
} from '../api/settings'

export interface PendingChange { id: string; from: unknown; to: unknown; consequence: string }

interface StoreShape {
  saved: Record<string, Values>
  draft: Record<string, Values>
  touched: Record<string, string>
  seeded: Record<string, boolean>
  invalid: Record<string, Record<string, string>>
}

const KEY = 'settings.store'
const clone = <T,>(v: T): T => { try { return structuredClone(v) } catch { return v } }
const init = (): StoreShape => ({ saved: clone(SAVED), draft: {}, touched: {}, seeded: {}, invalid: {} })

/** Values edited on one page that are the same value on another (spec §9.8 / §9.10 sequences). */
const SHARED: Record<string, { slug: string; id: string }[]> = {
  'review-queues:seq_gap': [{ slug: 'library-groupings', id: 'seq_gap' }],
  'review-queues:seq_events': [{ slug: 'library-groupings', id: 'seq_events' }],
  'library-groupings:seq_gap': [{ slug: 'review-queues', id: 'seq_gap' }],
  'library-groupings:seq_events': [{ slug: 'review-queues', id: 'seq_events' }],
}

const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

/** The held-out lock (D6) is read outside Settings — the header chip, every picker. Mirror the SAVED
 *  value (never the draft) into its own demo-store key so other workspaces can bind to it. */
export const HELD_OUT_KEY_STORE = 'settings.heldOut'
export interface HeldOutLock { on: boolean; recording: string }
function syncHeldOut(saved: Values) {
  setDemo<HeldOutLock>(HELD_OUT_KEY_STORE, { on: Boolean(saved['heldout.on']), recording: String(saved['heldout.recording'] ?? 'M4_aug') })
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
  /** write straight to the saved layer, skipping the draft (the held-out unlock is the commit, FE1) */
  applyNow: (id: string, v: unknown) => void
  save: () => void
  discard: () => void
  resetToDefaults: () => void
  differingCount: number
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
  const [store, setStore] = useDemoState<StoreShape>(KEY, init)
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
        if (PAGE_META[sl]?.scope === 'personal') next.saved[sl] = { ...(next.saved[sl] ?? {}), [key]: v }
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

  const applyNow = useCallback((id: string, v: unknown) => {
    setStore(s => {
      const saved = { ...(s.saved[slug] ?? {}), [id]: v }
      const draft = { ...(s.draft[slug] ?? {}) }
      delete draft[id]
      if (slug === 'datasets') syncHeldOut(saved)
      return { ...s, saved: { ...s.saved, [slug]: saved }, draft: { ...s.draft, [slug]: draft } }
    })
  }, [setStore, slug])

  const save = useCallback(() => {
    const n = changes.length
    if (!n) return
    setStore(s => {
      const saved = { ...(s.saved[slug] ?? {}), ...(s.draft[slug] ?? {}) }
      if (slug === 'datasets') syncHeldOut(saved)
      return { ...s, saved: { ...s.saved, [slug]: saved }, draft: { ...s.draft, [slug]: {} }, seeded: { ...s.seeded, [slug]: false } }
    })
    const what = changes.map(c => `${c.id} ${String(c.from)} → ${String(c.to)}`).join(' · ')
    recordDemoWrite('settings', 'save', { slug, changes: n, what })
    recordDemoWrite('settings', 'audit', { kind: 'settings', what: `${meta?.title ?? slug}: ${what}`, where: meta?.title ?? slug, route: `settings/${slug}` })
    push({ text: `Saved · ${sentence || `${n} change${n === 1 ? '' : 's'} applied`}` })
  }, [changes, setStore, slug, meta, push, sentence])

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
      if (scope === 'personal') return { ...s, saved: { ...s.saved, [slug]: { ...(s.saved[slug] ?? {}), ...staged } } }
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
    changes, sentence, invalid, markInvalid, save, discard, resetToDefaults, differingCount,
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

/** Audit entries written this session (newest first), shown on the Audit log page above the fixtures. */
export interface SessionAudit { when: string; kind: string; what: string; where: string; route?: string; by: string }
export function sessionAuditFromWrites(writes: { kind: string; at: number; detail: Record<string, unknown> }[]): SessionAudit[] {
  return writes.filter(w => w.kind === 'audit').map(w => ({
    when: new Date(w.at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).replace(',', ''),
    kind: String(w.detail.kind ?? 'settings'),
    what: String(w.detail.what ?? ''),
    where: String(w.detail.where ?? 'Settings'),
    route: w.detail.route as string | undefined,
    by: 'this installation',
  })).reverse()
}
