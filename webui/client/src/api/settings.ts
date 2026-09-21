/* Settings reads (spec §9, §12 P23) — LIVE since stage-3 Prompt 02. Every read resolves against the
 * bridge (`server/registration.py`) through the seam and says `source: 'live'`:
 *
 *   - project values come from the `settings` table (GET /api/settings/<page>) and are hydrated into the
 *     settings store's SAVED layer by the read itself, so the page draws what was saved;
 *   - real facts (registered recordings and their channels, verdict counts, the machine, the step cache,
 *     the block registry, storage roots and backups, the audit table, the installation) come from the
 *     bridge; what remains static below is UI vocabulary (which nulls exist, what the gate checks are, the
 *     export options) — configuration of the interface, not data about the project.
 *
 * Pages never import fixtures/settings.ts directly — they read through here and take the value layers
 * (DEFAULTS / SEEDS) through the re-exports below, which the settings store uses.
 */
import { live, type Sourced } from './seam'
import {
  getAbout as apiAbout, getAdapters, getAudit as apiAudit, getRegistry, getSettingsPage, getStorage as apiStorage, getTemplates,
  type About, type AuditRow, type BackupRow, type Candidate, type RegisteredArtifact, type RegisteredRecording, type StorageRootRow,
} from '../api'
import {
  AUDIT_KINDS, BASIS_BY_UNIT, BEHAVIOUR_ROWS, BUNDLE_CONTENTS, CLASS_ROWS, CLUSTERS, DEFAULTS, EVENT_EFFECTS, EVENT_KINDS, EXPORT_ALWAYS,
  FAMILY_PALETTES, FEATURE_BASES, GATE_CHECKS, GROUPING_UNITS, JOB_PROFILES, KEY_BINDINGS, LOCAL_LIMITS, MOTIF_FORMATS, MOTIF_INCLUDE,
  NAMING_EXTRA_TOKENS, NAMING_TOKENS, NULL_KINDS, PREVIEW_TRACE, QUEUE_DEFAULTS, QUEUE_ORDERS, RECOMMEND_RULES, ROLE_COLOURS, RULE_CONTEXTS,
  RULE_EXAMPLES, SEARCH_INDEX, SEED_OPTIONS, SIGNATURE_TYPES, TAG_ROWS, TIME_ZONES, VERDICT_KEY_SETS, VERDICT_ROWS, WINDOW_SET_INCLUDE,
  blockKey, channelDefaults, metaDefaults, metaKey, type BlockRow, type ChannelRow, type RecordingRow, type TagRow, type TimedEvent, type Values,
  type AuditEntry, type StorageRoot,
} from '../fixtures/settings'
import { hydrateSaved } from '../settings/hydrate'

/* value layers + helpers the store needs (config, not a data read) */
export {
  CONSEQUENCE, DEFAULTS, NAV_GROUPS, PAGE_META, SAVED, SEEDS, SEED_SENTENCE, SLUGS, genericConsequence,
  blockKey, classImpliesKey, classInformativeKey, effectKey, eventEffectSentence, eventsAddedKey, eventsRemovedKey,
  floorKey, gainKey, groundKey, keyKey, metaKey, removedRefs, ruleKey, spanLabel, staleRuns, statusKey, badFromHours,
  EVENT_KINDS_KEY, HELD_OUT_STEM,
  namingPreview, slurmScript, verdictKeyKey, verdictNameKey, tagExample,
} from '../fixtures/settings'
export type {
  AuditEntry, AuditKind, BlockRow, ChannelRow, ClassRow, EventEffect, FeatureBasis, GateCheck, ImportDryRun, JobProfile,
  KeyBinding, LocalLimit, MetaField, NullKind, PageMeta, QueueDefault, RecommendRule, RecordingRow, Scope, SearchHit,
  RemovedRef, StorageRoot, TagRow, TimedEvent, Values, VerdictRow,
} from '../fixtures/settings'
export { SEARCH_INDEX, EVENT_KINDS }
export type { Candidate, RegisteredArtifact, RegisteredRecording }

/* ------------------------------------------------------------------ helpers */

const fmtBytes = (b: number) => b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b >= 1e6 ? `${Math.round(b / 1e6)} MB` : b >= 1e3 ? `${Math.round(b / 1e3)} kB` : `${b} B`
const fmtWhen = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).replace(',', '')
}

/** The Datasets row of a registered recording (id = the directory stem, never the row id). */
export function recordingRow(r: RegisteredRecording, values: Values): RecordingRow & { warnings: string[]; excerpt_of: RegisteredRecording['excerpt_of']; ids: number[]; npy_exists: boolean } {
  const status: RecordingRow['status'] = r.held_out ? 'held out · locked' : r.warnings.length || r.fs_source === 'inferred' ? 'provisional' : 'in use'
  const species = values[metaKey(r.name, 'species')]
  const start = values[metaKey(r.name, 'start')]
  return {
    id: r.name, name: String(values[metaKey(r.name, 'display_name')] || r.name), file: r.source_file, fs_hz: r.fs, fs_source: r.fs_source,
    n_channels: r.n_channels, duration_h: r.duration_h != null ? Math.round(r.duration_h * 10) / 10 : 0,
    start: start ? String(start) : null, species: species ? String(species) : null,
    linked: r.excerpt_of ? [r.excerpt_of.name] : [], status, warnings: r.warnings, excerpt_of: r.excerpt_of, ids: r.ids, npy_exists: r.npy_exists,
  }
}

/* ------------------------------------------------------------------ per-page reads */

export interface DatasetsData {
  recordings: ReturnType<typeof recordingRow>[]; registered: RegisteredRecording[]; candidates: Candidate[]; rawCandidates: Candidate[]
  caption: string; timeZones: string[]; heldOut: { on: boolean; recording: string; name: string; file: string }; mode: string
}
export const getDatasets = (): Promise<Sourced<DatasetsData>> => live((async () => {
  const p = await getSettingsPage('datasets')
  const regs = p.recordings ?? []
  const defaults: Values = { ...(p.defaults ?? {}) }
  for (const r of regs) { const m = metaDefaults(r.name, r.name); for (const f of Object.keys(m) as (keyof typeof m)[]) defaults[metaKey(r.name, f)] = m[f] }
  const values = hydrateSaved('datasets', p.values, defaults)
  const channels = regs.reduce((n, r) => n + r.n_channels, 0)
  return {
    recordings: regs.map(r => recordingRow(r, values)), registered: regs, candidates: p.candidates ?? [], rawCandidates: p.raw_candidates ?? [],
    caption: `${regs.length} recordings · ${channels} channels · ${(p.candidates ?? []).length + (p.raw_candidates ?? []).length} on disk, not registered`,
    timeZones: TIME_ZONES, heldOut: p.held_out ?? { on: true, recording: 'M4_aug_concat_fs1', name: 'M4_aug_concat_fs1', file: 'M4_aug_concat_fs1.mat' }, mode: p.mode,
  }
})())

export interface ChannelsData {
  channels: ChannelRow[]; events: TimedEvent[]; kinds: typeof EVENT_KINDS; effects: typeof EVENT_EFFECTS; duration_h: number
  /** The display name of the recording, never its id — every caption reads this. */
  label: string
  /** Every registered recording, for the picker. */
  options: { value: string; label: string; held_out: boolean }[]
  ids: number[]
}
/** Channels of one registered recording (by directory stem). The held-out one reads back locked (D6). */
export function getChannels(recording: string): Promise<Sourced<ChannelsData>> {
  return live((async () => {
    const [reg, p] = await Promise.all([getRegistry<RegisteredRecording>('recording'), getSettingsPage('channels-events')])
    const options = reg.registered.map(r => ({ value: r.name, label: r.name, held_out: r.held_out }))
    const rec = reg.registered.find(r => r.name === recording)
    if (!rec) throw new Error(`no registered recording called ${recording} · known: ${reg.registered.map(r => r.name).join(', ')}`)
    const names = rec.channels.map(c => c.name)
    const defaults: Values = { ...DEFAULTS['channels-events'] }
    for (const r of reg.registered) Object.assign(defaults, channelDefaults(r.name, r.channels.map(c => c.name)))
    hydrateSaved('channels-events', p.values, defaults)
    return {
      channels: names.map((ch, i) => ({ ch, name: ch, electrode: `CH${rec.channels[i].channel} · ${rec.channels[i].npy_path.split('/').pop()}`, gain: 1, shared_ground: null,
        status: 'ok', spans: '—', noise_floor: 'recording' })),
      events: [], kinds: EVENT_KINDS, effects: EVENT_EFFECTS, duration_h: Math.round((rec.duration_h ?? 0) * 10) / 10, label: rec.name, options, ids: rec.ids,
    }
  })())
}

export interface VocabularyData { verdicts: typeof VERDICT_ROWS; classes: typeof CLASS_ROWS; tags: TagRow[]; source_note: string }
export const getVocabulary = (): Promise<Sourced<VocabularyData>> => live((async () => {
  const p = await getSettingsPage('vocabulary')
  hydrateSaved('vocabulary', p.values)
  const counts = new Map((p.verdicts ?? []).map(v => [v.name, v]))
  const verdicts = VERDICT_ROWS.map(v => ({ ...v, n_annotations: counts.get(v.name)?.n_annotations ?? 0, n_adjudications: counts.get(v.name)?.n_adjudications ?? 0 }))
  const dbTags: TagRow[] = (p.tags ?? []).map(t => ({
    name: String(t.name ?? t.tag ?? ''), definition: String(t.definition ?? t.description ?? ''), families: 0, members: 0, aliases: [], shape: 'spike-train' as const,
  })).filter(t => t.name)
  return { verdicts, classes: CLASS_ROWS, tags: dbTags.length ? dbTags : TAG_ROWS.map(t => ({ ...t, families: 0, members: 0 })),
    source_note: dbTags.length ? `${dbTags.length} tags from tag_vocabulary` : 'tag_vocabulary is empty · the six shape tags below are the proposed vocabulary, with no members yet' }
})())

export interface NullsData { kinds: typeof NULL_KINDS; seedOptions: string[] }
export const getNulls = (): Promise<Sourced<NullsData>> => live((async () => {
  const p = await getSettingsPage('nulls'); hydrateSaved('nulls', p.values)
  return { kinds: NULL_KINDS, seedOptions: SEED_OPTIONS }
})())

export interface AnalysisDefaultsData { rules: typeof RECOMMEND_RULES; contexts: string[]; examples: typeof RULE_EXAMPLES; cacheGb: number; cacheRoot: string | null }
export const getAnalysisDefaults = (): Promise<Sourced<AnalysisDefaultsData>> => live((async () => {
  const p = await getSettingsPage('analysis-defaults'); hydrateSaved('analysis-defaults', p.values)
  return { rules: RECOMMEND_RULES, contexts: RULE_CONTEXTS, examples: RULE_EXAMPLES, cacheGb: Math.round((p.cache_gb ?? 0) * 100) / 100, cacheRoot: p.cache_root ?? null }
})())

export interface ComputeData { machine: { detected: string; cores: number; calibrated: string }; limits: typeof LOCAL_LIMITS; clusters: typeof CLUSTERS; profiles: typeof JOB_PROFILES }
export const getCompute = (): Promise<Sourced<ComputeData>> => live((async () => {
  const p = await getSettingsPage('compute-hpc'); hydrateSaved('compute-hpc', p.values)
  const m = p.machine
  return { machine: { detected: m?.detected || 'not detected', cores: m?.cores ?? 1, calibrated: 'not calibrated' }, limits: LOCAL_LIMITS, clusters: CLUSTERS, profiles: JOB_PROFILES }
})())

export interface BlocksData { blocks: BlockRow[]; signatureTypes: string }
export const getBlocks = (): Promise<Sourced<BlocksData>> => live((async () => {
  const [p, adapters, templates] = await Promise.all([getSettingsPage('blocks'), getAdapters(), getTemplates().catch(() => [])])
  const blocks: BlockRow[] = adapters.map(a => ({
    id: a.name, name: a.display_name || a.name, signature: a.signature, version: null, adapter: `Adapters/${a.stage}_${a.algorithm}.py`,
    null_kind: a.algorithm === 'surrogate' ? 'surrogate' : '—', built: !a.known_broken,
    templates: templates.filter(t => t.steps.some(s => `${s.stage}.${s.algorithm}` === a.name)).map(t => t.name),
  }))
  const defaults: Values = {}
  for (const b of blocks) defaults[blockKey(b.id)] = b.built
  hydrateSaved('blocks', p.values, defaults)
  return { blocks, signatureTypes: SIGNATURE_TYPES }
})())

export interface QueuesData { queues: typeof QUEUE_DEFAULTS; keySets: string[]; orders: string[] }
export const getReviewQueues = (): Promise<Sourced<QueuesData>> => live((async () => {
  const p = await getSettingsPage('review-queues'); hydrateSaved('review-queues', p.values)
  return { queues: QUEUE_DEFAULTS, keySets: VERDICT_KEY_SETS, orders: QUEUE_ORDERS }
})())

export interface ModelsRegData { gate: typeof GATE_CHECKS; registered: RegisteredArtifact[]; candidates: Candidate[]; roots: string[]; mode: string }
export const getModelsRegistration = (): Promise<Sourced<ModelsRegData>> => live((async () => {
  const [p, reg] = await Promise.all([getSettingsPage('models-registration'), getRegistry<RegisteredArtifact>('model')])
  hydrateSaved('models-registration', p.values)
  return { gate: GATE_CHECKS, registered: reg.registered, candidates: reg.candidates.filter(c => !c.registered), roots: reg.roots, mode: p.mode }
})())

export interface GroupingsData { units: string[]; basisByUnit: typeof BASIS_BY_UNIT; featureBases: typeof FEATURE_BASES }
export const getLibraryGroupings = (): Promise<Sourced<GroupingsData>> => live((async () => {
  const p = await getSettingsPage('library-groupings'); hydrateSaved('library-groupings', p.values)
  return { units: GROUPING_UNITS, basisByUnit: BASIS_BY_UNIT, featureBases: FEATURE_BASES }
})())

export interface BackupHistoryRow { when: string; size: string; state: string; path: string; current: boolean }
export interface StorageData { roots: StorageRoot[]; rows: StorageRootRow[]; tokens: string[]; extraTokens: string[]; history: BackupHistoryRow[]; freeGb: number; mode: string; backupsDir: string }
export const backupRow = (b: BackupRow): BackupHistoryRow => ({ when: fmtWhen(new Date(b.mtime * 1000).toISOString()), size: fmtBytes(b.bytes), state: b.bytes > 0 ? 'ok' : 'empty', path: b.path, current: b.current })
export const getStorage = (): Promise<Sourced<StorageData>> => live((async () => {
  const [p, st] = await Promise.all([getSettingsPage('storage-backups'), apiStorage()])
  const defaults: Values = { ...DEFAULTS['storage-backups'] }
  for (const k of Object.keys(defaults)) if (k.startsWith('root.')) delete defaults[k]
  for (const r of st.roots) defaults[`root.${r.id}`] = r.path
  hydrateSaved('storage-backups', p.values, defaults)
  const roots: StorageRoot[] = st.roots.map(r => ({
    id: r.id, root: r.root, path: r.path, in_use: r.exists ? `${fmtBytes(r.bytes)} · ${r.n_files} file${r.n_files === 1 ? '' : 's'}` : 'absent',
    actions: r.actions, note: r.note, locked: r.locked,
  }))
  return { roots, rows: st.roots, tokens: NAMING_TOKENS, extraTokens: NAMING_EXTRA_TOKENS, history: st.backups.map(backupRow), freeGb: Math.round(st.free_gb ?? 0), mode: st.mode, backupsDir: st.backups_dir }
})())

export interface ExportData { always: string[]; motifFormats: string[]; motifInclude: string[]; windowSetInclude: string[]; bundle: string[] }
export const getExport = (): Promise<Sourced<ExportData>> => live((async () => {
  const p = await getSettingsPage('export'); hydrateSaved('export', p.values)
  return { always: EXPORT_ALWAYS, motifFormats: MOTIF_FORMATS, motifInclude: MOTIF_INCLUDE, windowSetInclude: WINDOW_SET_INCLUDE, bundle: BUNDLE_CONTENTS }
})())

export const auditEntry = (e: AuditRow): AuditEntry & { id: number; iso: string } => ({
  id: e.id, iso: e.when, when: fmtWhen(e.when), kind: e.kind as AuditEntry['kind'], what: e.what, where: e.where, route: e.route ?? undefined, by: e.by,
})
export interface AuditData { entries: ReturnType<typeof auditEntry>[]; kinds: typeof AUDIT_KINDS; mode: string }
export const getAuditLog = (kind?: string): Promise<Sourced<AuditData>> => live((async () => {
  const a = await apiAudit(kind)
  const known = new Set(AUDIT_KINDS.map(k => k.value))
  const kinds = [...AUDIT_KINDS, ...a.kinds.filter(k => !known.has(k)).map(k => ({ value: k, label: k }))]
  return { entries: a.entries.map(auditEntry), kinds, mode: a.mode }
})())

export interface AboutData {
  about: { code: string; matches_export: boolean; schema: string; blocks: string; environment: string; project: string; settings_file: string; lock_file: string; future: About['future']; mode: string; db_path: string; db_backup: string | null; broken: string[] }
  diagnostics: string; raw: About
}
export const getAbout = (): Promise<Sourced<AboutData>> => live((async () => {
  const a = await apiAbout()
  return {
    about: {
      code: a.code.summary, matches_export: !a.code.dirty, schema: `${a.schema.tables} tables · ${a.schema.recordings} recordings · ${a.schema.registered_artifacts} registered artifacts · ${a.schema.path}`,
      blocks: a.blocks.summary, environment: a.environment, project: a.project, settings_file: a.settings_store,
      lock_file: ['# environment (read at start, not a lock file)', `python=${a.python}`, ...Object.entries(a.packages).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`)].join('\n'),
      future: a.future, mode: a.mode, db_path: a.db_path, db_backup: a.db_backup, broken: a.blocks.broken,
    },
    diagnostics: a.diagnostics, raw: a,
  }
})())

export interface DisplayData { palettes: string[]; roleColours: typeof ROLE_COLOURS; preview: number[] }
/** Personal: nothing to read from the server; the values are this browser's (localStorage, settings/store.ts). */
export const getDisplay = (): Promise<Sourced<DisplayData>> => live(Promise.resolve({ palettes: FAMILY_PALETTES, roleColours: ROLE_COLOURS, preview: PREVIEW_TRACE }))

export interface KeyboardData { keys: typeof KEY_BINDINGS; behaviour: typeof BEHAVIOUR_ROWS }
export const getKeyboard = (): Promise<Sourced<KeyboardData>> => live(Promise.resolve({ keys: KEY_BINDINGS, behaviour: BEHAVIOUR_ROWS }))

/** The settings search index (Ctrl K in the header · page › card › field) — a UI-only index over the pages' own fields (F2), not project data. */
export const getSearchIndex = (): Promise<Sourced<typeof SEARCH_INDEX>> => live(Promise.resolve(SEARCH_INDEX))
