/* Settings reads (spec §9, §12 P23). Settings is not wired to the bridge: every read resolves the
 * fixture canon through the seam and says `source: 'demo'`. A later ticket can swap a body for a
 * bridge call (GET /api/recordings, GET /api/adapters) without touching a page.
 *
 * Pages never import fixtures/settings.ts directly — they read through here (Sourced<T> + useSourced)
 * and take the value layers (DEFAULTS / SAVED / SEEDS) through the re-exports below, which the
 * in-memory settings store uses.
 */
import { demo, type Sourced } from './seam'
import {
  ABOUT, AUDIT_ENTRIES, AUDIT_KINDS, BACKUP_HISTORY, BASIS_BY_UNIT, BEHAVIOUR_ROWS, BLOCK_ROWS, BUNDLE_CONTENTS, CLASS_ROWS,
  CLUSTERS, DIAGNOSTICS, DISK_FREE_GB, EVENTS, EVENT_EFFECTS, EVENT_KINDS, EXPORT_ALWAYS, FAMILY_PALETTES, FEATURE_BASES,
  GATE_CHECKS, GROUPING_UNITS, IMPORT_DRY_RUN, IMPORT_PATHS, JOB_PROFILES, KEY_BINDINGS, LOCAL_LIMITS, MACHINE, MOTIF_FORMATS,
  MOTIF_INCLUDE, NAMING_EXTRA_TOKENS, NAMING_TOKENS, NULL_KINDS, PREVIEW_TRACE, QUEUE_DEFAULTS, QUEUE_ORDERS, RECOMMEND_RULES,
  RECORDING_COUNT_CAPTION, RECORDING_ROWS, ROLE_COLOURS, RULE_CONTEXTS, RULE_EXAMPLES, SEARCH_INDEX, SEED_OPTIONS,
  SIGNATURE_TYPES, STEP_CACHE_GB, STORAGE_ROOTS, TAG_ROWS, TIME_ZONES, VERDICT_KEY_SETS, VERDICT_ROWS, WINDOW_SET_INCLUDE,
  channelsFor, tagExample,
} from '../fixtures/settings'

/* value layers + helpers the store needs (config, not a data read) */
export {
  CONSEQUENCE, DEFAULTS, NAV_GROUPS, PAGE_META, SAVED, SEEDS, SEED_SENTENCE, SLUGS, genericConsequence,
  blockKey, classImpliesKey, classInformativeKey, effectKey, floorKey, gainKey, keyKey, metaKey, ruleKey,
  namingPreview, slurmScript, verdictKeyKey, verdictNameKey,
} from '../fixtures/settings'
export type {
  AuditEntry, AuditKind, BlockRow, ChannelRow, ClassRow, EventEffect, FeatureBasis, GateCheck, ImportDryRun, JobProfile,
  KeyBinding, LocalLimit, MetaField, NullKind, PageMeta, QueueDefault, RecommendRule, RecordingRow, Scope, SearchHit,
  StorageRoot, TagRow, TimedEvent, Values, VerdictRow,
} from '../fixtures/settings'
export { SEARCH_INDEX, tagExample, channelsFor, EVENT_KINDS, IMPORT_PATHS, RECORDING_ROWS }

/* ------------------------------------------------------------------ per-page reads */

export interface DatasetsData { recordings: typeof RECORDING_ROWS; caption: string; timeZones: string[]; dryRun: typeof IMPORT_DRY_RUN }
export const getDatasets = (): Promise<Sourced<DatasetsData>> =>
  demo({ recordings: RECORDING_ROWS, caption: RECORDING_COUNT_CAPTION, timeZones: TIME_ZONES, dryRun: IMPORT_DRY_RUN })

export interface ChannelsData { channels: ReturnType<typeof channelsFor>; events: typeof EVENTS; kinds: typeof EVENT_KINDS; effects: typeof EVENT_EFFECTS; duration_h: number }
/** Channels and the event log of one recording. M4_aug reads back locked (held out, D6). */
export function getChannels(recording: string): Promise<Sourced<ChannelsData>> {
  const rec = RECORDING_ROWS.find(r => r.id === recording)
  if (!rec) return new Promise((_, reject) => window.setTimeout(() => reject(new Error(`no recording called ${recording} · known: ${RECORDING_ROWS.map(r => r.id).join(', ')}`)), 60))
  return demo({ channels: channelsFor(recording), events: EVENTS.filter(e => e.recording === recording), kinds: EVENT_KINDS, effects: EVENT_EFFECTS, duration_h: rec.duration_h })
}

export interface VocabularyData { verdicts: typeof VERDICT_ROWS; classes: typeof CLASS_ROWS; tags: typeof TAG_ROWS }
export const getVocabulary = (): Promise<Sourced<VocabularyData>> => demo({ verdicts: VERDICT_ROWS, classes: CLASS_ROWS, tags: TAG_ROWS })

export interface NullsData { kinds: typeof NULL_KINDS; seedOptions: string[] }
export const getNulls = (): Promise<Sourced<NullsData>> => demo({ kinds: NULL_KINDS, seedOptions: SEED_OPTIONS })

export interface AnalysisDefaultsData { rules: typeof RECOMMEND_RULES; contexts: string[]; examples: typeof RULE_EXAMPLES; cacheGb: number }
export const getAnalysisDefaults = (): Promise<Sourced<AnalysisDefaultsData>> =>
  demo({ rules: RECOMMEND_RULES, contexts: RULE_CONTEXTS, examples: RULE_EXAMPLES, cacheGb: STEP_CACHE_GB })

export interface ComputeData { machine: typeof MACHINE; limits: typeof LOCAL_LIMITS; clusters: typeof CLUSTERS; profiles: typeof JOB_PROFILES }
export const getCompute = (): Promise<Sourced<ComputeData>> => demo({ machine: MACHINE, limits: LOCAL_LIMITS, clusters: CLUSTERS, profiles: JOB_PROFILES })

export interface BlocksData { blocks: typeof BLOCK_ROWS; signatureTypes: string }
export const getBlocks = (): Promise<Sourced<BlocksData>> => demo({ blocks: BLOCK_ROWS, signatureTypes: SIGNATURE_TYPES })

export interface QueuesData { queues: typeof QUEUE_DEFAULTS; keySets: string[]; orders: string[] }
export const getReviewQueues = (): Promise<Sourced<QueuesData>> => demo({ queues: QUEUE_DEFAULTS, keySets: VERDICT_KEY_SETS, orders: QUEUE_ORDERS })

export interface ModelsRegData { gate: typeof GATE_CHECKS }
export const getModelsRegistration = (): Promise<Sourced<ModelsRegData>> => demo({ gate: GATE_CHECKS })

export interface GroupingsData { units: string[]; basisByUnit: typeof BASIS_BY_UNIT; featureBases: typeof FEATURE_BASES }
export const getLibraryGroupings = (): Promise<Sourced<GroupingsData>> => demo({ units: GROUPING_UNITS, basisByUnit: BASIS_BY_UNIT, featureBases: FEATURE_BASES })

export interface StorageData { roots: typeof STORAGE_ROOTS; tokens: string[]; extraTokens: string[]; history: typeof BACKUP_HISTORY; freeGb: number }
export const getStorage = (): Promise<Sourced<StorageData>> =>
  demo({ roots: STORAGE_ROOTS, tokens: NAMING_TOKENS, extraTokens: NAMING_EXTRA_TOKENS, history: BACKUP_HISTORY, freeGb: DISK_FREE_GB })

export interface ExportData { always: string[]; motifFormats: string[]; motifInclude: string[]; windowSetInclude: string[]; bundle: string[] }
export const getExport = (): Promise<Sourced<ExportData>> =>
  demo({ always: EXPORT_ALWAYS, motifFormats: MOTIF_FORMATS, motifInclude: MOTIF_INCLUDE, windowSetInclude: WINDOW_SET_INCLUDE, bundle: BUNDLE_CONTENTS })

export interface AuditData { entries: typeof AUDIT_ENTRIES; kinds: typeof AUDIT_KINDS }
export const getAuditLog = (): Promise<Sourced<AuditData>> => demo({ entries: AUDIT_ENTRIES, kinds: AUDIT_KINDS })

export interface AboutData { about: typeof ABOUT; diagnostics: string }
export const getAbout = (): Promise<Sourced<AboutData>> => demo({ about: ABOUT, diagnostics: DIAGNOSTICS })

export interface DisplayData { palettes: string[]; roleColours: typeof ROLE_COLOURS; preview: number[] }
export const getDisplay = (): Promise<Sourced<DisplayData>> => demo({ palettes: FAMILY_PALETTES, roleColours: ROLE_COLOURS, preview: PREVIEW_TRACE })

export interface KeyboardData { keys: typeof KEY_BINDINGS; behaviour: typeof BEHAVIOUR_ROWS }
export const getKeyboard = (): Promise<Sourced<KeyboardData>> => demo({ keys: KEY_BINDINGS, behaviour: BEHAVIOUR_ROWS })

/** The settings search index (Ctrl K in the header · page › card › field). */
export const getSearchIndex = (): Promise<Sourced<typeof SEARCH_INDEX>> => demo(SEARCH_INDEX)
