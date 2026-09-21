/* Settings fixtures (frames prototyping/imgs/settings/*.pdf, spec §9, §0 canon, §12 P23).
 *
 * Every settings page is an empty shell over these values. Three layers per page:
 *   DEFAULTS  — what "Reset page to defaults" stages (spec §9 defaults)
 *   SAVED     — what the frames draw as the current project value (may differ → amber "differs" dot)
 *   SEEDS     — the scripted edit `?state=unsaved` stages, so a screenshot reproduces the frame's save bar
 * Shared entities (recordings, channels, classes, verdicts, models, templates, jobs) come from
 * fixtures/canon.ts — never retyped here.
 */
import { CLASSES, HELD_OUT_KEY, MODELS, RECORDINGS, TEMPLATES, TOTAL_CHANNELS, seeded, syntheticTrace } from './canon'

export type Scope = 'project' | 'personal'
export type Values = Record<string, unknown>

export interface PageMeta { slug: string; title: string; group: string; scope: Scope; lede: string }

/* ------------------------------------------------------------------ the rail */
export const NAV_GROUPS: { section: string; tone: 'blue' | 'muted'; icon: 'folder' | 'monitor'; groups: { label: string; slugs: string[] }[] }[] = [
  {
    section: 'PROJECT · recorded with runs', tone: 'blue', icon: 'folder',
    groups: [
      { label: 'Data', slugs: ['datasets', 'channels-events', 'vocabulary'] },
      { label: 'Analysis', slugs: ['nulls', 'analysis-defaults', 'compute-hpc', 'blocks'] },
      { label: 'Workspaces', slugs: ['review-queues', 'models-registration', 'library-groupings'] },
      { label: 'Files', slugs: ['storage-backups', 'export'] },
      { label: 'Record', slugs: ['audit-log', 'about'] },
    ],
  },
  { section: 'PERSONAL · this browser', tone: 'muted', icon: 'monitor', groups: [{ label: 'Interface', slugs: ['display', 'keyboard'] }] },
]

export const PAGE_META: Record<string, PageMeta> = {
  datasets: { slug: 'datasets', title: 'Datasets', group: 'Data', scope: 'project', lede: 'The recording registry. Metadata travels with every export.' },
  'channels-events': { slug: 'channels-events', title: 'Channels & events', group: 'Data', scope: 'project', lede: 'Per-channel metadata and timed events. Excluded spans are skipped by every new run.' },
  vocabulary: { slug: 'vocabulary', title: 'Vocabulary', group: 'Data', scope: 'project', lede: 'One vocabulary across annotations and adjudications — no translation table, so none can drift.' },
  nulls: { slug: 'nulls', title: 'Nulls', group: 'Analysis', scope: 'project', lede: 'Every result carries a null. Method, count and seed travel into the recipe hash; whether a null runs is not a setting.' },
  'analysis-defaults': { slug: 'analysis-defaults', title: 'Analysis defaults', group: 'Analysis', scope: 'project', lede: 'These travel into every recipe hash.' },
  'compute-hpc': { slug: 'compute-hpc', title: 'Compute & HPC', group: 'Analysis', scope: 'project', lede: 'Where work runs. Estimates include null draws.' },
  blocks: { slug: 'blocks', title: 'Blocks', group: 'Analysis', scope: 'project', lede: 'Read from Adapters/ at start · code a7f3c1e. Each block follows the contract in §6.8.' },
  'review-queues': { slug: 'review-queues', title: 'Review queues', group: 'Workspaces', scope: 'project', lede: 'Defaults for new queues. The blind state is stored with every verdict.' },
  'models-registration': { slug: 'models-registration', title: 'Models & registration', group: 'Workspaces', scope: 'project', lede: 'Defaults for new training jobs and the checks a model must pass to be registered.' },
  'library-groupings': { slug: 'library-groupings', title: 'Library groupings', group: 'Workspaces', scope: 'project', lede: 'Defaults for new groupings. Every grouping is saved with its settings.' },
  'storage-backups': { slug: 'storage-backups', title: 'Storage & backups', group: 'Files', scope: 'project', lede: 'Where things are read from and written to. Bulk arrays live on disk; the database holds paths.' },
  export: { slug: 'export', title: 'Export', group: 'Files', scope: 'project', lede: 'What leaves the tool. An export that cannot be traced to a repository state is not evidence.' },
  'audit-log': { slug: 'audit-log', title: 'Audit log', group: 'Record', scope: 'project', lede: 'Every act that changes what a result means, in order. Kept for the life of the project.' },
  about: { slug: 'about', title: 'About', group: 'Record', scope: 'project', lede: 'What this installation is running. Included in every export.' },
  display: { slug: 'display', title: 'Display', group: 'Interface', scope: 'personal', lede: 'How the site looks to you. Report figures use their own profile below.' },
  keyboard: { slug: 'keyboard', title: 'Keyboard & behaviour', group: 'Interface', scope: 'personal', lede: 'Verdict and class keys are part of the vocabulary and are set there.' },
}
export const SLUGS = Object.keys(PAGE_META)

/* ================================================================= 01 Datasets */
export interface RecordingRow {
  id: string; name: string; file: string; fs_hz: number; fs_source: 'read' | 'inferred'; n_channels: number
  duration_h: number; start: string | null; species: string | null; linked: string[]
  status: 'in use' | 'provisional' | 'available' | 'held out · locked'
}
export const RECORDING_ROWS: RecordingRow[] = [
  { id: 'M2_aug_fs1', name: 'M2_aug fs1', file: 'M2_aug_concat_fs1.mat', fs_hz: 1, fs_source: 'read', n_channels: 16, duration_h: 721, start: '2025-08-02 14:00', species: 'P. ostreatus', linked: ['M2_aug_fs2'], status: 'in use' },
  { id: 'M2_aug_fs2', name: 'M2_aug fs2', file: 'M2_aug_concat_fs2.mat', fs_hz: 2, fs_source: 'read', n_channels: 16, duration_h: 721, start: '2025-08-02 14:00', species: 'P. ostreatus', linked: ['M2_aug_fs1'], status: 'in use' },
  { id: 'M3_jul', name: 'M3_jul', file: 'M3_jul_concat.mat', fs_hz: 1, fs_source: 'read', n_channels: 8, duration_h: 280, start: '2025-07-10 09:30', species: 'P. ostreatus', linked: [], status: 'in use' },
  { id: 'L_LM_Jul26_J', name: 'L_LM_Jul26_J', file: 'L_LM_Jul26_J.csv', fs_hz: 10, fs_source: 'inferred', n_channels: 5, duration_h: 22.4, start: '2026-07-26 —', species: null, linked: [], status: 'provisional' },
  { id: 'M4_aug', name: 'M4_aug', file: 'M4_aug_concat.mat', fs_hz: 1, fs_source: 'read', n_channels: 16, duration_h: 300, start: '2025-08-20 11:00', species: 'P. ostreatus', linked: [], status: 'held out · locked' },
]
export const RECORDING_COUNT_CAPTION = `${RECORDING_ROWS.length} recordings · ${TOTAL_CHANNELS} channels`

/** Metadata card values per recording (frame 01 draws M2_aug fs1; the others follow the canon). */
const META_FIELDS = ['display_name', 'species', 'substrate', 'electrode_config', 'start', 'time_zone', 'noise_floor', 'temperature', 'humidity', 'notes'] as const
export type MetaField = (typeof META_FIELDS)[number]
const metaFor = (r: RecordingRow): Record<MetaField, string> => ({
  display_name: r.name,
  species: r.species ? 'Pleurotus ostreatus' : '',
  substrate: r.species ? 'hardwood sawdust block' : '',
  electrode_config: r.species ? 'sub-dermal pairs · 12 mm' : '',
  start: r.start ?? '',
  time_zone: 'Europe/London',
  noise_floor: '0.10',
  temperature: r.species ? '21.4 ± 0.8' : '',
  humidity: r.species ? '88 – 94' : '',
  notes: '',
})
export const metaKey = (rec: string, f: MetaField) => `meta.${rec}.${f}`
export const TIME_ZONES = ['Europe/London', 'UTC', 'Europe/Berlin', 'America/New_York']

/** Live (Prompt 02): the per-recording metadata defaults come from GET /api/settings/datasets (one set per
 *  registered recording); only the lock keys are static. The held-out id is the real stem, not the canon key. */
export const HELD_OUT_STEM = 'M4_aug_concat_fs1'
export const META_FIELD_LIST = META_FIELDS
export const metaDefaults = (rec: string, name: string): Record<MetaField, string> => ({
  display_name: name, species: '', substrate: '', electrode_config: '', start: '', time_zone: 'Europe/London', noise_floor: '', temperature: '', humidity: '', notes: '',
})
const datasetsValues = (): Values => ({ 'heldout.on': true, 'heldout.recording': HELD_OUT_STEM })
void metaFor; void HELD_OUT_KEY

export interface ImportDryRun {
  path: string; format: string; fs_hz: number | null; fs_source: 'read' | 'inferred'
  samples_per_channel: number; duration_h: number; start: string; time_zone: string; link_to: string
  channel_map: { variable: string; channel: string; electrode: string; shared_ground: string | null; include: boolean }[]
}
const M_CH = RECORDINGS[0].channels
export const IMPORT_DRY_RUN: ImportDryRun = {
  path: 'D:/recordings/M5_sep_concat_fs1.mat', format: 'MATLAB v7.3 · 16 variables', fs_hz: 1, fs_source: 'read',
  samples_per_channel: 1_080_000, duration_h: 300, start: '2025-09-01 10:00', time_zone: 'Europe/London', link_to: 'none',
  channel_map: M_CH.map((ch, i) => ({
    variable: `ch${String(i + 1).padStart(2, '0')}`, channel: ch,
    electrode: `${ch.split('_')[1]} ${i % 2 === 0 ? 'tip · 0 mm' : 'base · 12 mm'}`,
    shared_ground: ch === 'CH3_A2' ? 'CH4_A2' : ch === 'CH4_A2' ? 'CH3_A2' : null,
    include: true,
  })),
}
/** Paths the dry run knows (F5: no core import API — every other path is "file not found"). */
export const IMPORT_PATHS: Record<string, { ok: boolean; note?: string }> = {
  'D:/recordings/M5_sep_concat_fs1.mat': { ok: true },
  'D:/recordings/M3_jul_concat.mat': { ok: false, note: 'already registered as M3_jul' },
  'D:/recordings/M4_aug_concat.mat': { ok: false, note: 'M4_aug is held out · locked' },
}

/* ========================================================= 02 Channels & events */
export interface ChannelRow {
  ch: string; name: string; electrode: string; gain: number; shared_ground: string | null
  status: 'ok' | string; spans: string; noise_floor: string
}
const electrodeName = (ch: string) => { const p = ch.split('_')[1]; return p ? `${p} ${Number(ch.slice(2).split('_')[0]) % 2 === 1 ? 'tip' : 'base'}` : ch }
const electrodePos = (ch: string) => { const p = ch.split('_')[1]; return p ? `${p} · ${Number(ch.slice(2).split('_')[0]) % 2 === 1 ? '0' : '12'} mm` : '—' }
export const channelsFor = (rec: string): ChannelRow[] => {
  const r = RECORDINGS.find(x => x.key === rec) ?? RECORDINGS[0]
  return r.channels.map(ch => ({
    ch, name: electrodeName(ch), electrode: electrodePos(ch),
    gain: 1, shared_ground: rec.startsWith('M2_aug') || rec === 'M4_aug' ? (ch === 'CH3_A2' ? 'CH4_A2' : ch === 'CH4_A2' ? 'CH3_A2' : null) : null,
    status: rec === 'M2_aug_fs1' && ch === 'CH7_B2' ? 'bad from 40.1 h' : 'ok',
    spans: rec === 'M2_aug_fs1' && ch === 'CH2_A1' ? '2 · 28.9–29.1 h + all'
      : rec === 'M2_aug_fs1' && ch === 'CH7_B2' ? '2 · 40.1 h → end + all' : '1 · all channels',
    noise_floor: 'recording',
  }))
}
export type EventEffect = 'show on plots' | 'exclude span' | 'exclude · mark channel bad'
export interface TimedEvent { id: string; recording: string; t0_h: number; t1_h: number | null; open_end?: boolean; kind: string; channels: string; effect: EventEffect; note: string; added: string }
/** No fixture events on a live page: the event log is what was saved (settings values events.added.<rec>). */
export const EVENTS: TimedEvent[] = []
export const EVENT_KINDS: { name: string; colour: string }[] = [
  { name: 'watering', colour: '#2F6FEB' }, { name: 'mechanical', colour: '#E8900C' }, { name: 'unknown', colour: '#9CA3AF' },
  { name: 'electrode', colour: '#E5484D' }, { name: 'light', colour: '#E4C441' }, { name: 'stimulus', colour: '#8B5CF6' }, { name: 'temperature', colour: '#30B0C7' },
]
export const EVENT_EFFECTS: EventEffect[] = ['show on plots', 'exclude span', 'exclude · mark channel bad']
export const gainKey = (rec: string, ch: string) => `gain.${rec}.${ch}`
export const floorKey = (rec: string, ch: string) => `floor.${rec}.${ch}`
export const effectKey = (id: string) => `effect.${id}`
/** Channel status: `''` = ok, otherwise the hour it goes bad from (F8: the event is the source, this is the derived cell). */
export const statusKey = (rec: string, ch: string) => `status.${rec}.${ch}`
/** Shared ground of one channel: `''` = none, otherwise the partner channel. Symmetric (both cells are written). */
export const groundKey = (rec: string, ch: string) => `ground.${rec}.${ch}`
/** Event kinds added on this page — one page-wide draft key, so `+ kind` stages like every other edit. */
export const EVENT_KINDS_KEY = 'event.kinds'
/** Event rows added / staged for removal on one recording — one draft key each, so both stage, save and discard. */
export const eventsAddedKey = (rec: string) => `events.added.${rec}`
export const eventsRemovedKey = (rec: string) => `events.removed.${rec}`
export const badFromHours = (status: string): string => status.match(/bad from ([\d.]+)/)?.[1] ?? ''
/** Live (Prompt 02): the per-channel defaults are built per registered recording by api/settings.ts
 *  (`channelDefaults`); the fixture EVENTS no longer seed a page — the event log is what was saved. */
export const channelDefaults = (rec: string, channels: string[]): Values => {
  const v: Values = {}
  for (const ch of channels) { v[gainKey(rec, ch)] = 1; v[floorKey(rec, ch)] = ''; v[groundKey(rec, ch)] = '' }
  v[eventsAddedKey(rec)] = []
  v[eventsRemovedKey(rec)] = []
  return v
}
const channelsValues = (): Values => ({ [EVENT_KINDS_KEY]: [] })
void RECORDINGS

/* ---- the consequence sentences of Channels & events (P23: never a fixture id, always the effect).
   The run counts are fixture-only (fog F7): a per-channel change touches fewer runs than an all-channel one. */
const RUNS_ON: Record<string, number> = { M2_aug_fs1: 3, M2_aug_fs2: 2, M3_jul: 1, L_LM_Jul26_J: 1, M4_aug: 0 }
const recName = (rec: string) => RECORDING_ROWS.find(r => r.id === rec)?.name ?? rec
/** Runs on `rec` that a change scoped to `channels` ('all' or one channel) marks stale. */
export const staleRuns = (rec: string, channels: string) => {
  const n = RUNS_ON[rec] ?? 1
  return channels === 'all' ? n : Math.max(1, Math.ceil((n * 2) / 3))
}
const stalePhrase = (rec: string, channels: string) => {
  const n = staleRuns(rec, channels)
  return `${n} run${n === 1 ? '' : 's'} on ${recName(rec)} marked stale`
}
/** "marks 3 runs on M2_aug fs1 stale" — the canon shape of the exclusion sentence. */
const marksPhrase = (rec: string, channels: string) => {
  const n = staleRuns(rec, channels)
  return `marks ${n} run${n === 1 ? '' : 's'} on ${recName(rec)} stale`
}
export const spanLabel = (e: { t0_h: number; t1_h: number | null; open_end?: boolean }) =>
  e.open_end ? `${e.t0_h} h → end` : e.t1_h != null ? `${e.t0_h}–${e.t1_h} h` : `${e.t0_h} h`
const chanLabel = (channels: string) => (channels === 'all' ? 'all channels' : channels)
const dp2 = (v: unknown) => (Number.isFinite(Number(v)) ? Number(v).toFixed(2) : String(v))

/** What changing one event's effect does — the sentence the frame draws, for any event, added or canon. */
export function eventEffectSentence(e: TimedEvent, to: unknown): string {
  const span = spanLabel(e), ch = chanLabel(e.channels)
  if (to === 'exclude span') return `excluding ${span} on ${ch} ${marksPhrase(e.recording, e.channels)}`
  if (to === 'exclude · mark channel bad') return `excluding ${span} and marking ${ch} bad from ${e.t0_h} h ${marksPhrase(e.recording, e.channels)}`
  return `removing the exclusion lets new runs read ${span} again · ${stalePhrase(e.recording, e.channels)}`
}
function eventAddedSentence(rec: string, from: unknown, to: unknown): string {
  const a = Array.isArray(from) ? (from as TimedEvent[]) : []
  const b = Array.isArray(to) ? (to as TimedEvent[]) : []
  const e = b.find(x => !a.some(y => y.id === x.id))
  if (!e) {
    const gone = a.find(x => !b.some(y => y.id === x.id))
    return gone ? `the new ${gone.kind} event at ${spanLabel(gone)} is dropped · nothing was written` : `event log of ${recName(rec)} unchanged`
  }
  if (e.effect === 'show on plots') return `${spanLabel(e)} · ${e.kind} is marked on plots of ${recName(rec)} · no run is marked stale`
  return eventEffectSentence(e, e.effect)
}
/** A row staged for removal carries the effect it had when it was removed: what the removal undoes is
 *  the EFFECTIVE effect (which may itself be an unsaved edit), never the fixture's original. */
export interface RemovedRef { id: string; effect: EventEffect }
export const removedRefs = (v: unknown): RemovedRef[] => (Array.isArray(v) ? v : []).map(x =>
  typeof x === 'string' ? { id: x, effect: EVENTS.find(e => e.id === x)?.effect ?? 'show on plots' } : (x as RemovedRef))
function eventRemovedSentence(rec: string, from: unknown, to: unknown): string {
  const a = removedRefs(from), b = removedRefs(to)
  const r = b.find(x => !a.some(y => y.id === x.id)) ?? a.find(x => !b.some(y => y.id === x.id))
  const e = r && EVENTS.find(x => x.id === r.id)
  if (!r || !e) return `event log of ${recName(rec)} unchanged`
  const back = b.some(x => x.id === r.id)
  if (!back) return `${spanLabel(e)} · ${e.kind} is kept · new runs read it as before`
  if (r.effect === 'show on plots') return `removing the ${e.kind} marker at ${spanLabel(e)} takes it off every plot · no run is marked stale`
  return `removing the exclusion lets new runs read ${spanLabel(e)} again · ${stalePhrase(e.recording, e.channels)}`
}
/** `+ kind` is staged like every other edit (fix round 2): the bar says what the new kind buys. */
function eventKindsSentence(from: unknown, to: unknown): string {
  const a = (Array.isArray(from) ? from : []) as { name: string }[]
  const b = (Array.isArray(to) ? to : []) as { name: string }[]
  const added = b.find(x => !a.some(y => y.name === x.name))
  if (added) return `${added.name} joins the event kinds · it can be picked in Add event · no run is marked stale`
  const gone = a.find(x => !b.some(y => y.name === x.name))
  return gone ? `${gone.name} is dropped · nothing was written` : 'event kinds unchanged'
}
/** Consequences for the keys whose id is built at runtime (per channel, per event) — P23 without a static table. */
function channelsConsequence(id: string, from: unknown, to: unknown): string | null {
  const m = id.match(/^(gain|floor|status)\.(.+)\.(CH[^.]+)$/)
  if (m) {
    const [, what, rec, ch] = m
    if (what === 'gain') return `gain on ${ch} ${dp2(from)} → ${dp2(to)} rescales mV on ${ch} · ${stalePhrase(rec, ch)}`
    if (what === 'floor') return String(to) === ''
      ? `${ch} falls back to the recording noise floor · ${stalePhrase(rec, ch)}`
      : `${ch} overrides the recording floor at ${dp2(to)} mV · ${stalePhrase(rec, ch)}`
    return String(to) === ''
      ? `${ch} reads ok again · new runs read it past ${from} h · ${stalePhrase(rec, ch)}`
      : `${ch} is bad from ${to} h · new runs stop reading it there · ${stalePhrase(rec, ch)}`
  }
  const ev = id.match(/^effect\.(.+)$/)
  if (ev) {
    const e = EVENTS.find(x => x.id === ev[1])
    if (e) return eventEffectSentence(e, to)
  }
  const g = id.match(/^ground\.(.+)\.(CH[^.]+)$/)
  if (g) {
    const [, rec, ch] = g
    return String(to) === ''
      ? `${ch} and ${from} no longer share a ground · both count in Library recurrence on ${recName(rec)}`
      : `${ch} and ${to} count once in Library recurrence on ${recName(rec)}`
  }
  if (id === EVENT_KINDS_KEY) return eventKindsSentence(from, to)
  const add = id.match(/^events\.added\.(.+)$/)
  if (add) return eventAddedSentence(add[1], from, to)
  const rm = id.match(/^events\.removed\.(.+)$/)
  if (rm) return eventRemovedSentence(rm[1], from, to)
  return null
}

/* ============================================================== 03 Vocabulary */
export interface VerdictRow { name: string; key: string; colour: string; role: string; n_annotations: number; n_adjudications: number; core: boolean }
export const VERDICT_ROWS: VerdictRow[] = [
  { name: 'seed', key: 'S', colour: '#2F6FEB', role: 'exemplar · promotes to Library', n_annotations: 412, n_adjudications: 96, core: true },
  { name: 'interesting', key: 'I', colour: '#22A06B', role: 'accept', n_annotations: 1284, n_adjudications: 2140, core: true },
  { name: 'not_interesting', key: 'N', colour: '#9CA3AF', role: 'reject', n_annotations: 3901, n_adjudications: 5772, core: true },
  { name: 'artifact', key: 'A', colour: '#E5484D', role: 'flag · kept out of training', n_annotations: 211, n_adjudications: 318, core: true },
  { name: 'unsure', key: 'U', colour: '#E8900C', role: 'defer', n_annotations: 88, n_adjudications: 144, core: true },
]
export interface ClassRow { key: string; name: string; colour: string; informative: boolean; implies: string; labels: number; used_by: string[] }
export const CLASS_ROWS: ClassRow[] = [
  ...CLASSES.filter(c => c.informative).map((c, i) => ({ key: c.key, name: c.name, colour: c.colour, informative: true, implies: 'interesting', labels: [410, 380, 330, 250][i], used_by: ['cnn_cluster_v1'] })),
  { key: '9', name: 'electrode artifact', colour: '#E5484D', informative: false, implies: 'artifact', labels: 38, used_by: [] },
]
export interface TagRow { name: string; definition: string; families: number; members: number; aliases: string[]; shape: 'spike-train' | 'biphasic' | 'sharkfin' | 'slow-drift' | 'burst' | 'plateau' }
export const TAG_ROWS: TagRow[] = [
  { name: 'spike-train', definition: 'regular train of sharp drops, 3 or more events', families: 3, members: 412, aliases: ['spike-train-short (merged)'], shape: 'spike-train' },
  { name: 'biphasic', definition: 'rise then fall of similar depth within about 2 s', families: 3, members: 210, aliases: [], shape: 'biphasic' },
  { name: 'sharkfin', definition: 'single steep fall then slower recovery, within about 30 s', families: 2, members: 112, aliases: [], shape: 'sharkfin' },
  { name: 'slow-drift', definition: 'baseline movement over more than 10 min, no events', families: 4, members: 188, aliases: [], shape: 'slow-drift' },
  { name: 'burst', definition: '3 or more fast oscillations within 5 s', families: 2, members: 77, aliases: [], shape: 'burst' },
  { name: 'plateau', definition: 'sustained level shift, then return', families: 1, members: 26, aliases: [], shape: 'plateau' },
]
/** Example sparkline per tag, drawn to the definition (mV, not normalised). */
export function tagExample(shape: TagRow['shape']): number[] {
  const n = 60
  switch (shape) {
    case 'spike-train': return syntheticTrace({ n, seed: 3, noise: 0.01, events: [8, 18, 28, 38, 48].map(at => ({ at, depth: 0.3, width: 3, shape: 'spike' as const })) })
    case 'biphasic': { const r = seeded(9); return Array.from({ length: n }, (_, i) => +( (i > 20 && i < 30 ? 0.25 : i >= 30 && i < 40 ? -0.25 : 0) + (r() - 0.5) * 0.02).toFixed(4)) }
    case 'sharkfin': return syntheticTrace({ n, seed: 11, noise: 0.012, events: [{ at: 18, depth: 0.35, width: 30, shape: 'sharkfin' }] })
    case 'slow-drift': { const r = seeded(5); return Array.from({ length: n }, (_, i) => +(-0.2 * Math.sin((i / n) * Math.PI) + (r() - 0.5) * 0.01).toFixed(4)) }
    case 'burst': { const r = seeded(13); return Array.from({ length: n }, (_, i) => +((i > 20 && i < 42 ? Math.sin(i * 1.6) * 0.18 : 0) + (r() - 0.5) * 0.015).toFixed(4)) }
    default: return syntheticTrace({ n, seed: 17, noise: 0.012, events: [{ at: 18, depth: 0.3, width: 24, shape: 'plateau' }] })
  }
}
export const verdictNameKey = (v: string) => `verdict.${v}.name`
export const verdictKeyKey = (v: string) => `verdict.${v}.key`
export const classInformativeKey = (k: string) => `class.${k}.informative`
export const classImpliesKey = (k: string) => `class.${k}.implies`
const vocabularyValues = (): Values => {
  const v: Values = {}
  for (const r of VERDICT_ROWS) { v[verdictNameKey(r.name)] = r.name; v[verdictKeyKey(r.name)] = r.key }
  for (const c of CLASS_ROWS) { v[classInformativeKey(c.key)] = c.informative; v[classImpliesKey(c.key)] = c.implies }
  return v
}

/* ================================================================== 04 Nulls */
/** `p_value`: whether this null yields a p-value (then its draws bound the smallest reportable p, and α). */
export interface NullKind { id: string; kind: string; used_in: string; methods: string[]; draws: number; seed: string; shown_as: string; p_value: boolean }
export const NULL_KINDS: NullKind[] = [
  { id: 'detection', kind: 'Detection chains', used_in: 'Analyse · Discovery', methods: ['circular shift', 'phase randomisation', 'block shuffle'], draws: 200, seed: 'per recipe', shown_as: 'null expects · × null', p_value: true },
  { id: 'seed-search', kind: 'Seed search', used_in: 'Discovery', methods: ['circular shift of the channel', 'phase randomisation'], draws: 200, seed: 'per recipe', shown_as: 'distances behind the histogram', p_value: true },
  { id: 'distributions', kind: 'Interrogation · distributions', used_in: 'Analyse', methods: ['matched random windows', 'random windows'], draws: 200, seed: 'per recipe', shown_as: 'null histogram · null β', p_value: true },
  { id: 'intervals', kind: 'Interrogation · intervals', used_in: 'Analyse', methods: ['shuffled onsets', 'Poisson onsets'], draws: 200, seed: 'per recipe', shown_as: 'null interval distribution', p_value: true },
  { id: 'baseline', kind: 'Training · baseline', used_in: 'Models', methods: ['label shuffle · random forest'], draws: 200, seed: 'per job', shown_as: 'null band · p', p_value: true },
  { id: 'full-model', kind: 'Training · full model', used_in: 'Models', methods: ['label shuffle · full retrain'], draws: 5, seed: 'per job', shown_as: 'shuffle dots', p_value: false },
  { id: 'groupings', kind: 'Library groupings', used_in: 'Library', methods: ['bootstrap resample of members', 'jackknife'], draws: 100, seed: 'per grouping', shown_as: 'group stability', p_value: false },
]
export const SEED_OPTIONS = ['per recipe', 'per job', 'per grouping', 'fixed']
const nullsValues = (correction: string): Values => {
  const v: Values = { alpha: 0.01, correction, show_x_null: true, reuse_draws: true }
  for (const k of NULL_KINDS) { v[`null.${k.id}.method`] = k.methods[0]; v[`null.${k.id}.draws`] = k.draws; v[`null.${k.id}.seed`] = k.seed }
  return v
}

/* ======================================================= 05 Analysis defaults */
export interface RecommendRule { block: string; parameter: string; rule: string; locked: boolean; evaluated_on: string; example: string | null; history: { rule: string; when: string }[] }
export const RECOMMEND_RULES: RecommendRule[] = [
  { block: 'Sliding windows', parameter: 'window', rule: '3 × longest expected event', locked: false, evaluated_on: 'the span', example: '600 s', history: [{ rule: '3 × longest expected event', when: 'saved 2 Sep · this installation' }] },
  { block: 'Sliding windows', parameter: 'gap', rule: '≥ window', locked: true, evaluated_on: '—', example: '600 s', history: [] },
  { block: 'Matrix profile', parameter: 'm', rule: 'exemplar native length, else 2 × median event', locked: false, evaluated_on: 'the span', example: '120 s', history: [{ rule: 'exemplar native length, else 2 × median event', when: 'saved 2 Sep · this installation' }] },
  { block: 'Threshold to spans', parameter: 'threshold', rule: 'model calibration, else null 99th percentile', locked: false, evaluated_on: 'null run', example: '0.62', history: [] },
  { block: 'Noise floor', parameter: 'floor', rule: "the recording's noise floor (Datasets)", locked: true, evaluated_on: 'recording', example: '0.10 mV', history: [] },
  { block: 'Bandpass filter', parameter: 'band', rule: '0.01 – 0.1 Hz', locked: false, evaluated_on: 'fixed', example: null, history: [{ rule: '0.01 – 0.1 Hz', when: 'saved 12 Sep · this installation' }, { rule: '0.01 – 0.2 Hz', when: '2 Sep · this installation' }] },
  { block: 'Symbolic encoding', parameter: 'alphabet', rule: '5 symbols · Gaussian breakpoints', locked: false, evaluated_on: 'fixed', example: null, history: [] },
]
export const ruleKey = (block: string, param: string) => `rule.${block}.${param}`
export const RULE_CONTEXTS = ['M2_aug fs1 CH4_A2', 'M3_jul CH2']
export const RULE_EXAMPLES: Record<string, Record<string, string | null>> = {
  'M2_aug fs1 CH4_A2': { 'Sliding windows.window': '600 s', 'Sliding windows.gap': '600 s', 'Matrix profile.m': '120 s', 'Threshold to spans.threshold': '0.62', 'Noise floor.floor': '0.10 mV', 'Bandpass filter.band': null, 'Symbolic encoding.alphabet': null },
  'M3_jul CH2': { 'Sliding windows.window': '600 s', 'Sliding windows.gap': '600 s', 'Matrix profile.m': '90 s', 'Threshold to spans.threshold': '0.58', 'Noise floor.floor': '0.10 mV', 'Bandpass filter.band': null, 'Symbolic encoding.alphabet': null },
}
const analysisValues = (band: string): Values => {
  const v: Values = {
    iou: 0.5, onset: 0.25, exclusion: 'm / 2',
    coherence: 0.5, clipping: 98, step_x: 5, step_within: 1, band_low: 0.3, band_medium: 0.6,
    cache_min_s: 2, cache_keep_days: 14, cache_location: './artifacts/steps',
  }
  for (const r of RECOMMEND_RULES) v[ruleKey(r.block, r.parameter)] = r.block === 'Bandpass filter' ? band : r.rule
  return v
}
export const STEP_CACHE_GB = 14.2

/* =========================================================== 06 Compute & HPC */
export const MACHINE = { detected: '16 cores · RTX 4070 12 GB · 64 GB RAM', cores: 16, calibrated: '12 Sep 2026' }
export interface LocalLimit { workspace: string; estimated: string; unit: 'min' | 'h'; above: string }
export const LOCAL_LIMITS: LocalLimit[] = [
  { workspace: 'Analyse', estimated: 'one stage on one channel', unit: 'min', above: 'the stage offers Create SLURM script · downstream stages wait' },
  { workspace: 'Discovery', estimated: 'one run across its channels', unit: 'min', above: 'Add and run disabled · Create SLURM script is primary' },
  { workspace: 'Models', estimated: 'one training job · all arms and nulls', unit: 'h', above: 'Train locally disabled · Create SLURM script is primary' },
  { workspace: 'Library', estimated: 'one grouping computation', unit: 'min', above: 'runs in the background with progress' },
  { workspace: 'Review', estimated: 'building a queue', unit: 'min', above: 'runs in the background with progress' },
]
export const CLUSTERS = [{ name: 'hpc-1', login_host: 'login.hpc-1.example', scheduler: 'SLURM', account: 'a_myco', status: 'in use · 3 profiles' }]
export interface JobProfile { name: string; partition: string; nodes: number; gres: string; cpus: number; memory: string; time: string; array: string; used_for: string; flag?: string }
export const JOB_PROFILES: JobProfile[] = [
  { name: 'gpu-single', partition: 'gpu_short', nodes: 1, gres: 'gpu:1', cpus: 8, memory: '32 G', time: '04:00:00', array: '—', used_for: 'Models training · image encoding' },
  { name: 'gpu-multinode', partition: 'gpu_long', nodes: 2, gres: 'gpu:1 per node', cpus: 8, memory: '32 G', time: '12:00:00', array: '—', used_for: '', flag: 'check the job can use 2 nodes' },
  { name: 'cpu-array', partition: 'cpu', nodes: 1, gres: '—', cpus: 4, memory: '16 G', time: '08:00:00', array: '16', used_for: 'matrix profiles · per-channel stages' },
]
const computeValues = (analyseLimit: number): Values => ({
  local_jobs: 2,
  'limit.Analyse': analyseLimit, 'limit.Discovery': 20, 'limit.Models': 2, 'limit.Library': 10, 'limit.Review': 5,
  env_setup: 'module load cuda/12.1 && conda activate cnn', workdir: '/scratch/$USER/cnn',
  return_remote: '/scratch/$USER/cnn/out', return_local: './cluster_out', email_on_finish: true,
  remind_x: 3, watch_min: 5,
})
export function slurmScript(p: JobProfile, v: { account: string; env: string; workdir: string; remote: string; email: boolean }): string {
  return [
    '#!/bin/bash',
    `#SBATCH --account=${v.account} --partition=${p.partition} --nodes=${p.nodes}`,
    `#SBATCH --gres=${p.gres === '—' ? 'none' : p.gres.split(' ')[0]} --cpus-per-task=${p.cpus} --mem=${p.memory.replace(' ', '')} --time=${p.time}`,
    ...(v.email ? ['#SBATCH --mail-type=END'] : []),
    v.env,
    `cd ${v.workdir}`,
    `python -m pipeline.run --recipe {{recipe}} --out ${v.remote}/{{job}}`,
  ].join('\n')
}

/* ================================================================= 07 Blocks */
export interface BlockRow { id: string; name: string; signature: string; version: string | null; adapter: string | null; null_kind: string; templates: string[]; built: boolean }
const t = TEMPLATES.named
export const BLOCK_ROWS: BlockRow[] = [
  { id: 'baseline', name: 'Baseline removal', signature: 'Signal → Signal', version: '1.2', adapter: 'adapters/baseline.py', null_kind: '—', templates: [t[0], t[1], t[2], t[3], t[5], t[6]], built: true },
  { id: 'bandpass', name: 'Bandpass filter', signature: 'Signal → Signal', version: '1.0', adapter: 'adapters/bandpass.py', null_kind: '—', templates: [t[0], t[1], t[2], t[3], t[5]], built: true },
  { id: 'noise_floor', name: 'Noise floor', signature: 'Signal → Signal + estimate', version: '1.1', adapter: 'adapters/noise_floor.py', null_kind: 'surrogate estimate', templates: [t[0], t[1], t[3]], built: true },
  { id: 'sax', name: 'Symbolic encoding', signature: 'Signal → Encoding', version: '2.1', adapter: 'adapters/sax.py', null_kind: '—', templates: [t[0], t[1]], built: true },
  { id: 'drop_detect', name: 'Drop detection', signature: 'Encoding → SpanSet', version: '1.4', adapter: 'adapters/drop_detect.py', null_kind: 'surrogate count', templates: [t[0], t[1], t[2], t[3], t[5], t[6]], built: true },
  { id: 'matrix_profile', name: 'Matrix profile', signature: 'Signal → Scores', version: '3.0', adapter: 'adapters/matrix_profile.py', null_kind: 'circular shift', templates: [t[2], t[3], t[4], t[6]], built: true },
  { id: 'threshold', name: 'Threshold to spans', signature: 'Scores → SpanSet', version: '1.0', adapter: 'adapters/threshold.py', null_kind: 'inherited', templates: [t[0], t[1], t[2], t[3], t[4], t[5], t[6]], built: true },
  { id: 'mass', name: 'Seeded search', signature: 'Signal + exemplar → Scores', version: '1.4', adapter: 'adapters/mass.py', null_kind: 'circular shift', templates: [t[1], t[6]], built: true },
  { id: 'windows', name: 'Sliding windows', signature: 'Signal → WindowSet', version: '2.0', adapter: 'adapters/windows.py', null_kind: 'split checks', templates: TEMPLATES.training, built: true },
  { id: 'window_matrix', name: 'Window matrix', signature: 'WindowSet → WindowSet', version: '1.3', adapter: 'adapters/window_matrix.py', null_kind: '—', templates: TEMPLATES.training, built: true },
  { id: 'cluster', name: 'Hierarchical cluster', signature: 'WindowSet → Grouping', version: '1.1', adapter: 'adapters/cluster.py', null_kind: 'bootstrap', templates: TEMPLATES.training, built: true },
  { id: 'gramian', name: 'Image encode', signature: 'WindowSet → Encoding', version: '1.0', adapter: 'adapters/gramian.py', null_kind: '—', templates: TEMPLATES.training, built: true },
  { id: 'cnn', name: 'CNN classifier', signature: 'Encoding + labels → Model', version: '0.9', adapter: 'adapters/cnn.py', null_kind: 'label shuffle', templates: [TEMPLATES.training[0]], built: true },
  { id: 'slope', name: 'Resolve spans · slope', signature: 'SpanSet → Features', version: '1.0', adapter: 'adapters/slope.py', null_kind: 'matched windows', templates: [t[3]], built: true },
  { id: 'aggregate', name: 'Aggregate', signature: 'Features → views', version: '1.0', adapter: 'adapters/aggregate.py', null_kind: 'null β', templates: [t[3]], built: true },
  { id: 'model_stage', name: 'Model stage', signature: 'Model + WindowSet → Scores', version: null, adapter: null, null_kind: '—', templates: [t[4], t[5], t[6]], built: false },
]
export const blockKey = (id: string) => `block.${id}.on`
const blocksValues = (): Values => Object.fromEntries(BLOCK_ROWS.map(b => [blockKey(b.id), b.built]))
export const SIGNATURE_TYPES = 'Signal · SpanSet · WindowSet · Encoding · Grouping · Model · Scores · Features — the §6.8 contract types.'

/* ========================================================== 08 Review queues */
export interface QueueDefault { id: string; source: string; icon: string; blind: boolean; keys: string; cap: string; order: string; writes: string }
export const QUEUE_DEFAULTS: QueueDefault[] = [
  { id: 'discovery', source: 'Discovery run', icon: '◎', blind: false, keys: 'full · S I N A U', cap: '—', order: 'score, high first', writes: 'adjudications' },
  { id: 'seed', source: 'Seed search', icon: '⌖', blind: false, keys: 'full · S I N A U', cap: '—', order: 'distance, near first', writes: 'adjudications' },
  { id: 'explore', source: 'Explore spans', icon: '∿', blind: false, keys: 'full · S I N A U', cap: '—', order: 'time', writes: 'annotations' },
  { id: 'family', source: 'Library family', icon: '▥', blind: false, keys: 'full · S I N A U', cap: '—', order: 'distance to medoid', writes: 'adjudications' },
  { id: 'training', source: 'Training windows', icon: '▦', blind: true, keys: 'binary + classes', cap: '20,000', order: 'stratified by channel', writes: 'window verdicts' },
  { id: 'verification', source: 'Model verification', icon: '⬡', blind: true, keys: 'full + classes', cap: '40', order: 'stratified by class', writes: 'window verdicts' },
]
export const VERDICT_KEY_SETS = ['full · S I N A U', 'binary · I N', 'binary + classes', 'full + classes']
export const QUEUE_ORDERS = ['score, high first', 'score, low first', 'distance, near first', 'time', 'distance to medoid', 'stratified by channel', 'stratified by class', 'random (seeded)']
const queuesValues = (trainingCap: string): Values => {
  const v: Values = { cohesion: 0.45, seq_gap: 6, seq_events: 2, largest_batch: 50, suggest_d: 0.3 }
  for (const q of QUEUE_DEFAULTS) { v[`q.${q.id}.blind`] = q.blind; v[`q.${q.id}.keys`] = q.keys; v[`q.${q.id}.cap`] = q.id === 'training' ? trainingCap : q.cap; v[`q.${q.id}.order`] = q.order }
  return v
}

/* ==================================================== 09 Models & registration */
export interface GateCheck { id: string; label: string; prefix: string; value: string | null; suffix?: string; locked: boolean; on_fail: 'blocks registration' | 'warning · needs a reason' | 'required' | '—' }
export const GATE_CHECKS: GateCheck[] = [
  { id: 'null_p', label: 'beats the label-shuffle null', prefix: 'p <', value: '0.01', locked: false, on_fail: 'blocks registration' },
  { id: 'df1', label: 'beats the random-forest baseline', prefix: 'ΔF1 CI excludes', value: '0', locked: false, on_fail: 'blocks registration' },
  { id: 'unseen', label: 'test windows unseen in training', prefix: '', value: null, suffix: 'always', locked: true, on_fail: 'blocks registration' },
  { id: 'ece', label: 'calibration per class', prefix: 'ECE ≤', value: '0.10', locked: false, on_fail: 'warning · needs a reason' },
  { id: 'sample', label: 'human verification sample', prefix: 'stratified by class,', value: String(MODELS.verification.of), locked: false, on_fail: '—' },
  { id: 'agreement', label: 'agreement with the human sample', prefix: '≥', value: '80 %', locked: false, on_fail: 'warning · needs a reason' },
  { id: 'signoff', label: 'sign-off recorded with the model', prefix: '', value: null, suffix: 'always', locked: true, on_fail: 'required' },
]
const modelsValues = (warnBelow: number): Values => ({
  test_pct: 20, validation_pct: 10, gap_extra: 0, warn_below: warnBelow,
  'arm.manual': true, 'arm.cluster': true, intersect_labelled: true, repeats_on: false, repeats_n: 3, patience: 10,
  precision: 0.8, bins: 10,
  ...Object.fromEntries(GATE_CHECKS.filter(g => g.value != null).map(g => [`gate.${g.id}`, g.value as string])),
})

/* ======================================================= 10 Library groupings */
export const GROUPING_UNITS = ['single motifs', 'sequences', 'spike trains']
export const BASIS_BY_UNIT: Record<string, string[]> = {
  'single motifs': ['shape distance · Ward', 'shape distance · average', 'feature bins · amplitude', 'feature bins · timescale', 'feature bins · frequency content', 'feature bins · polarity', 'labels · class', 'labels · provenance'],
  sequences: ['sequence similarity · Ward', 'feature bins · amplitude', 'feature bins · timescale', 'labels · class'],
  'spike trains': ['shape distance · Ward', 'feature bins · amplitude', 'feature bins · timescale', 'labels · class'],
}
export interface FeatureBasis { basis: string; features: string[]; bins: string[]; count: number; range: string }
export const FEATURE_BASES: FeatureBasis[] = [
  { basis: 'amplitude', features: ['peak-to-peak', 'depth below baseline', 'RMS'], bins: ['quantiles', 'log-spaced', 'linear'], count: 5, range: '—' },
  { basis: 'timescale', features: ['duration', 'rise time', 'fall time'], bins: ['log-spaced', 'quantiles', 'linear'], count: 6, range: '0.5 s – 10 min' },
  { basis: 'frequency content', features: ['dominant frequency · Welch PSD', 'spectral centroid'], bins: ['log-spaced', 'quantiles', 'linear'], count: 6, range: '0.002 – 0.5 Hz' },
  { basis: 'polarity', features: ['up / down / biphasic'], bins: ['fixed'], count: 3, range: 'ratio threshold 0.2' },
]
const groupingValues = (omitD: number): Values => {
  const v: Values = {
    unit: 'single motifs', basis: 'shape distance · Ward', cut: 0.42,
    omit_d: omitD, omit_min: 10, seq_gap: 6, seq_events: 2, w_shapes: 0.6, w_gaps: 0.4, orphaned: 'keep as a hand group',
  }
  for (const f of FEATURE_BASES) { v[`fb.${f.basis}.feature`] = f.features[0]; v[`fb.${f.basis}.bins`] = f.bins[0]; v[`fb.${f.basis}.count`] = f.count; v[`fb.${f.basis}.range`] = f.range }
  return v
}

/* ======================================================= 11 Storage & backups */
export interface StorageRoot { id: string; root: string; path: string; in_use: string; actions: string[]; note?: string; locked?: boolean }
export const STORAGE_ROOTS: StorageRoot[] = [
  { id: 'database', root: 'database', path: './DATA/pipeline.sqlite', in_use: '2.1 GB', actions: ['open folder'], note: 'schema v14' },
  { id: 'recordings', root: 'recordings', path: './DATA/recordings', in_use: '38 GB', actions: ['scan'] },
  { id: 'step-cache', root: 'step cache', path: './artifacts/steps', in_use: '14.2 GB', actions: ['clear'], note: 'retention in Analysis defaults' },
  { id: 'matrices', root: 'window matrices', path: './MATRICES', in_use: '21 GB', actions: ['scan', 'pull'] },
  { id: 'profiles', root: 'matrix profiles', path: './PROFILES', in_use: '6.4 GB', actions: ['scan', 'pull'] },
  { id: 'models', root: 'models', path: './MODELS', in_use: '3.8 GB', actions: ['scan', 'pull'] },
  { id: 'window-sets', root: 'window sets', path: './DATA/window_sets', in_use: '1.2 GB', actions: ['scan'], note: '6 saved' },
  { id: 'templates', root: 'templates', path: 'in the database', in_use: '—', actions: ['export all'], note: `${TEMPLATES.total} saved`, locked: true },
  { id: 'exports', root: 'library exports', path: './exports', in_use: '0.4 GB', actions: ['open folder'] },
  { id: 'inbox', root: 'manifest inbox', path: './cluster_out', in_use: '0.2 GB', actions: ['import'], note: 'watched every 5 min' },
]
export const NAMING_TOKENS = ['<recording>', '<channel>', '<fs>', '<window>', '<stride>', '<m>', '<hash8>']
export const NAMING_EXTRA_TOKENS = ['<date>', '<template>', '<run>']
export const namingPreview = (tokens: string[]) => tokens.map(tk => ({
  '<recording>': 'M2_aug_fs1', '<channel>': 'CH4_A2', '<fs>': '1Hz', '<window>': '600s', '<stride>': '300s', '<m>': '120s',
  '<hash8>': 'a7f39c2e', '<date>': '2026-09-16', '<template>': 'drop_motifs9', '<run>': 'a-0101',
}[tk] ?? tk)).join('_') + '.npz'
export const DISK_FREE_GB = 212
const storageValues = (keep: number): Values => {
  const v: Values = {
    backup_on: true, backup_every: 'daily', backup_at: '02:00', backup_to: './backups', keep,
    include_settings: true, warn_gb: 50, tokens: [...NAMING_TOKENS],
  }
  for (const r of STORAGE_ROOTS) v[`root.${r.id}`] = r.path
  return v
}
export const BACKUP_HISTORY = [
  { when: '14 Sep 02:00', size: '2.1 GB', state: 'ok' },
  { when: '13 Sep 02:00', size: '2.1 GB', state: 'ok' },
  { when: '12 Sep 02:00', size: '2.0 GB', state: 'ok' },
]

/* ================================================================= 12 Export */
export const EXPORT_ALWAYS = ['recipe hash', 'code version', 'schema version', 'recording metadata', 'settings snapshot']
export const MOTIF_FORMATS = ['xlsx catalogue', 'CSV', 'JSON manifest', 'atlas PDF', 'atlas SVG']
export const MOTIF_INCLUDE = ['exemplar', 'medoid', 'all members', 'edges', 'scope', 'tags', 'notes', 'hand edits', 'omitted list']
export const WINDOW_SET_INCLUDE = ['split plan', 'labels', 'class map', 'verdict provenance']
export const BUNDLE_CONTENTS = ['recipe', 'environment lock', 'code commit', 'input file hashes', 'null draws']
const exportValues = (motifInclude: string[]): Values => ({
  'motifs.formats': ['xlsx catalogue', 'CSV', 'JSON manifest', 'atlas PDF'],
  'motifs.include': motifInclude,
  'motifs.layout': 'one workbook, a sheet per family',
  'ws.format': 'npz + JSON manifest',
  'ws.include': ['split plan', 'labels', 'class map'],
  'templates.carry_exemplars': true,
  'models.weights': 'PyTorch',
  'models.card': true,
  'reports.layout': 'one document, stages in order',
  'bundle.contents': ['recipe', 'environment lock', 'code commit', 'input file hashes'],
})

/* ============================================================== 13 Audit log */
export type AuditKind = 'settings' | 'sign-off' | 'hand edit' | 'HPC status' | 'vocabulary' | 'events' | 'lock' | 'batch undo'
export interface AuditEntry { when: string; kind: AuditKind; what: string; where: string; route?: string; by: string }
export const AUDIT_KINDS: { value: string; label: string }[] = [
  { value: 'all', label: 'all' }, { value: 'lock', label: 'locks' }, { value: 'sign-off', label: 'sign-offs' }, { value: 'hand edit', label: 'hand edits' },
  { value: 'vocabulary', label: 'vocabulary' }, { value: 'events', label: 'events' }, { value: 'settings', label: 'settings' },
  { value: 'HPC status', label: 'HPC status' }, { value: 'batch undo', label: 'batch undo' },
]
export const AUDIT_ENTRIES: AuditEntry[] = [
  { when: '14 Sep 16:02', kind: 'settings', what: 'Analyse local limit 10 → 20 min', where: 'Compute & HPC', route: 'settings/compute-hpc', by: 'this installation' },
  { when: '14 Sep 15:40', kind: 'sign-off', what: 'Registered cnn_cluster_v1 v1 · accepted warning ECE 0.12 on plateau · reason recorded', where: 'Models › Registry', route: 'models/registry', by: 'this installation' },
  { when: '14 Sep 14:12', kind: 'hand edit', what: 'Added m-1850 to F-03 (d 0.47, past the cut)', where: 'Library › F-03', route: 'library/family/F-03', by: 'this installation' },
  { when: '14 Sep 11:05', kind: 'HPC status', what: 'j-0214 marked running · cluster job 4418093', where: 'Jobs', route: 'jobs', by: 'this installation' },
  { when: '13 Sep 18:30', kind: 'vocabulary', what: 'Merged tag spike-train-short into spike-train · 38 rows · alias kept', where: 'Vocabulary', route: 'settings/vocabulary', by: 'this installation' },
  { when: '13 Sep 09:12', kind: 'events', what: 'Recorded the mechanical event at 31.1–31.5 h on all channels of M2_aug fs1 · no run marked stale', where: 'Channels & events', route: 'settings/channels-events', by: 'this installation' },
  { when: '12 Sep 10:00', kind: 'lock', what: 'Held-out lock turned on · M4_aug held out', where: 'Datasets', route: 'settings/datasets', by: 'this installation' },
  { when: '11 Sep 17:44', kind: 'batch undo', what: 'Cluster 12 · 6 verdicts reversed in one step', where: 'Review', route: 'review/queue/q-12', by: 'this installation' },
]

/* ================================================================== 14 About */
export const ABOUT = {
  code: 'a7f3c1e · main · clean working tree', matches_export: true,
  schema: 'v14 · ./DATA/pipeline.sqlite',
  blocks: `${BLOCK_ROWS.filter(b => b.built).length} registered · ${BLOCK_ROWS.filter(b => !b.built).length} not built`,
  environment: 'conda env cnn · Python 3.11 · Panel · HoloViews',
  project: 'Underground Brains · fungal bio-electric recordings',
  settings_file: './DATA/settings.json · personal preferences in this browser',
  lock_file: ['# environment.lock (excerpt)', 'python=3.11.9', 'numpy=1.26.4', 'scipy=1.13.1', 'stumpy=1.12.0', 'aeon=0.11.1', 'panel=1.9.0', 'holoviews=1.19.1', 'torch=2.3.1'].join('\n'),
  future: [
    { name: 'user accounts', detail: 'named researchers on verdicts, hand edits, HPC status and sign-offs; per-user blind state; a second sign-off for registration' },
    { name: 'multi-seed search', detail: 'seed searches that take several exemplars (Discovery §7.6)' },
    { name: 'cross-channel analysis', detail: "multivariate chains; Explore's cross-channel mode stays a placeholder" },
  ],
}
export const DIAGNOSTICS = [
  'Underground Brains · fungal bio-electric recordings',
  'code      a7f3c1e · main · clean working tree',
  'schema    v14 · ./DATA/pipeline.sqlite',
  `blocks    ${ABOUT.blocks}`,
  'env       conda env cnn · Python 3.11',
  'settings  ./DATA/settings.json',
].join('\n')

/* ================================================================ 15 Display */
export const FAMILY_PALETTES = ['no semantic hues · 10', 'colourblind-safe · 8', 'high contrast · 6']
export const ROLE_COLOURS = [
  { role: 'run A', colour: '#2F6FEB' }, { role: 'run B', colour: '#8B5CF6' }, { role: 'human', colour: '#22A06B' },
  { role: 'artifact', colour: '#E5484D' }, { role: 'blind', colour: '#4F46E5' }, { role: 'hand edit', colour: '#374151' },
]
const displayValues = (): Values => ({
  theme: 'light', density: 'comfortable', time_axis: 'hours since start', amplitude: 'mV', sample_indices: false,
  family_palette: FAMILY_PALETTES[0], channels_per_page: 3, review_padding: '±120 s', members_per_page: 10, recurrence: 'per hour',
  line_width: 1.2, grid_opacity: 0.15, font: 'Inter', dpi: 300, background: 'white',
})
export const PREVIEW_TRACE = syntheticTrace({ n: 420, seed: 23, noise: 0.03, events: [{ at: 210, depth: 0.45, width: 26, shape: 'sharkfin' }, { at: 250, depth: -0.55, width: 14, shape: 'spike' }] })

/* ==================================================== 16 Keyboard & behaviour */
/* `covers` is for a row drawn as a range ("1 – 9"): the keys it really owns, which the conflict
 * check has to see — a rebind onto 3 collides with a class key exactly as one onto S collides
 * with a verdict key. */
export interface KeyBinding { id: string; action: string; keys: string[]; where: string; locked?: boolean; note?: string; covers?: string[] }
export const KEY_BINDINGS: KeyBinding[] = [
  { id: 'verdicts', action: 'verdicts S · I · N · A · U', keys: ['S', 'I', 'N', 'A', 'U'], where: 'Review', locked: true, note: 'set in Vocabulary →' },
  { id: 'classes', action: 'classes', keys: ['1', '–', '9'], where: 'Review', locked: true, note: 'set in Vocabulary →', covers: ['1', '2', '3', '4', '5', '6', '7', '8', '9'] },
  { id: 'skip', action: 'skip without writing', keys: ['Space'], where: 'Review' },
  { id: 'next', action: 'next · previous candidate', keys: ['→', '←'], where: 'Review' },
  { id: 'undo', action: 'undo · redo', keys: ['Ctrl Z', 'Ctrl Shift Z'], where: 'everywhere' },
  { id: 'promote', action: 'confirm promotion', keys: ['Enter'], where: 'Review' },
  { id: 'explore', action: 'open in Explore', keys: ['E'], where: 'Review · Library' },
  { id: 'reviewed', action: 'mark viewport reviewed', keys: ['R'], where: 'Explore' },
  { id: 'rails', action: 'toggle both rails', keys: ['\\'], where: 'Review' },
  { id: 'search', action: 'search', keys: ['Ctrl K'], where: 'everywhere' },
]
export const BEHAVIOUR_ROWS: { id: string; label: string; locked?: boolean; caption?: string; chip?: string }[] = [
  { id: 'auto_advance', label: 'auto-advance after a verdict' },
  { id: 'batch_wait', label: 'after a batch verdict', chip: 'waits for the whole batch to write', caption: 'a mis-keyed batch must not commit and move on before it can be undone', locked: true },
  { id: 'undo_batch', label: 'undo reverses a whole batch', locked: true },
  { id: 'pause_promotion', label: 'pause after a seed promotion', caption: 'so the family can be chosen' },
  { id: 'confirm_discard', label: 'confirm before discarding a run' },
  { id: 'confirm_leave', label: 'confirm before leaving unsaved settings' },
]
export const keyKey = (id: string) => `key.${id}`
const keyboardValues = (): Values => {
  const v: Values = { auto_advance: true, batch_wait: true, undo_batch: true, pause_promotion: true, confirm_discard: true, confirm_leave: true }
  for (const k of KEY_BINDINGS) if (!k.locked) v[keyKey(k.id)] = k.keys.join(' · ')
  return v
}

/* ============================================ defaults · saved · seeded edits */
export const DEFAULTS: Record<string, Values> = {
  datasets: datasetsValues(),
  'channels-events': channelsValues(),
  vocabulary: vocabularyValues(),
  nulls: nullsValues('none'),
  'analysis-defaults': analysisValues('0.01 – 0.2 Hz'),
  'compute-hpc': computeValues(10),
  blocks: blocksValues(),
  'review-queues': queuesValues('10,000'),
  'models-registration': modelsValues(30),
  'library-groupings': groupingValues(0.4),
  'storage-backups': storageValues(7),
  export: exportValues(['exemplar', 'medoid', 'all members', 'edges', 'scope', 'tags', 'omitted list']),
  'audit-log': {},
  about: {},
  display: displayValues(),
  keyboard: keyboardValues(),
}
/** What the frames draw as the current project value. Differs from DEFAULTS on the seven pages whose rail item carries a dot. */
export const SAVED: Record<string, Values> = {
  ...DEFAULTS,
  nulls: nullsValues('Holm'),
  'analysis-defaults': analysisValues('0.01 – 0.1 Hz'),
  'compute-hpc': computeValues(20),
  'review-queues': queuesValues('20,000'),
  'models-registration': modelsValues(50),
  'library-groupings': groupingValues(0.5),
}

/** `?state=unsaved` stages exactly the frame's edit, so the save bar reads as drawn. */
export const SEEDS: Record<string, Values> = {
  datasets: { [metaKey('M2_aug_concat_fs1', 'species')]: 'Pleurotus ostreatus ', [metaKey('M2_aug_concat_fs1', 'start')]: '2025-08-02 15:00', [metaKey('M2_aug_concat_fs1', 'noise_floor')]: '0.12' },
  'channels-events': { [gainKey('M2_aug_concat_fs1', 'CH6_B1')]: 0.98 },
  vocabulary: { [verdictNameKey('interesting')]: 'noteworthy' },
  nulls: { 'null.baseline.draws': 500 },
  'analysis-defaults': { [ruleKey('Bandpass filter', 'band')]: '0.005 – 0.1 Hz' },
  'compute-hpc': { 'limit.Analyse': 30 },
  blocks: { [blockKey('sax')]: false },
  'review-queues': { 'q.training.cap': '40,000' },
  'models-registration': { warn_below: 80 },
  'library-groupings': { omit_d: 0.6 },
  'storage-backups': { keep: 14 },
  export: { 'motifs.include': ['exemplar', 'medoid', 'all members', 'edges', 'scope', 'tags', 'hand edits', 'omitted list'] },
  'audit-log': {},
  about: {},
  display: {},
  keyboard: {},
}
/** The seeded edits' own save-bar sentence (P23: the consequence, never a restatement of the edit). */
export const SEED_SENTENCE: Record<string, string> = {
  datasets: 'noise floor — → 0.12 mV · every detector on M2_aug_concat_fs1 reads the new floor; earlier runs keep theirs',
  'channels-events': 'gain on CH6_B1 1.00 → 0.98 rescales mV on CH6_B1 · runs on M2_aug_concat_fs1 marked stale',
  vocabulary: 'rename interesting → noteworthy rewrites 3,424 rows in both stores',
  nulls: 'Training · baseline 200 → 500 draws · new recipe hash for cnn_windows_v3, cnn_windowset_v1 · estimates × 2.5',
  'analysis-defaults': 'bandpass rule changed · 6 cached stages will re-run next time their chains run',
  'compute-hpc': 'Analyse local limit 20 → 30 min · 2 stages in saved chains now run locally instead of offering Create SLURM script',
  blocks: 'disabling Symbolic encoding hides it from Insert · 2 templates still use it and stay readable',
  'review-queues': 'training-window queues cap at 40,000 · q-18 keeps its current cap',
  'models-registration': 'classes with fewer than 80 test windows warn at launch · plateau (43 test windows in j-0212) now warns',
  'library-groupings': 'omit motifs past d 0.60 · fewer omitted at the next regroup · existing groupings keep their settings',
  'storage-backups': 'keep 7 → 14 backups · about 15 GB more in ./backups',
}

const listDelta = (from: unknown, to: unknown) => {
  const a = Array.isArray(from) ? (from as string[]) : []
  const b = Array.isArray(to) ? (to as string[]) : []
  return { added: b.filter(x => !a.includes(x)), removed: a.filter(x => !b.includes(x)) }
}
const andList = (xs: string[]) => xs.length <= 1 ? (xs[0] ?? '') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`
/** "<what> now carry X · <why>" for a list of things that travel with an export. */
const listSentence = (from: unknown, to: unknown, what: string, why: { on: string; off: string; singular?: boolean }) => {
  const { added, removed } = listDelta(from, to)
  const [carry, stop, is] = why.singular ? ['carries', 'stops carrying', 'is'] : ['carry', 'stop carrying', 'are']
  if (added.length && removed.length) return `${what} now ${carry} ${andList(added)} and ${stop} ${andList(removed)}`
  if (added.length) return `${what} now ${carry} ${andList(added)} · ${why.on}`
  if (removed.length) return `${what} ${stop} ${andList(removed)} · ${why.off}`
  return `${what} ${is} unchanged`
}

/** Per-field consequence sentences (P23 "consequence beside the control"). */
export const CONSEQUENCE: Record<string, (from: unknown, to: unknown) => string> = {
  [metaKey('M2_aug_concat_fs1', 'noise_floor')]: (f, t2) => `noise floor ${f || '—'} → ${t2} mV · every detector on M2_aug_concat_fs1 reads the new floor; earlier runs keep theirs`,
  [metaKey('M2_aug_concat_fs1', 'species')]: () => 'species travels with every new export; existing exports keep the old value',
  [metaKey('M2_aug_concat_fs1', 'start')]: () => 'clock-time readouts shift; hours since start are unchanged',
  [verdictNameKey('interesting')]: (f, t2) => `rename ${f} → ${t2} rewrites 3,424 rows in both stores`,
  'null.baseline.draws': (f, t2) => `Training · baseline ${f} → ${t2} draws · new recipe hash for training templates · estimates change`,
  correction: (f, t2) => `${f} → ${t2} · per-channel p values shown corrected; runs are not re-run`,
  alpha: (f, t2) => `α ${f} → ${t2} · every "significant" mark is recomputed at the new level`,
  [ruleKey('Bandpass filter', 'band')]: () => 'bandpass rule changed · 6 cached stages will re-run next time their chains run',
  'limit.Analyse': (f, t2) => `Analyse local limit ${f} → ${t2} min · stages in saved chains change how they run`,
  'limit.Models': (f, t2) => `Models limit ${f} → ${t2} h · Train locally enabled for jobs estimated ≤ ${t2} h`,
  local_jobs: (f, t2) => `local jobs at once ${f} → ${t2} · local runs share ${MACHINE.cores} cores`,
  'q.training.cap': (_f, t2) => `training-window queues cap at ${t2} · q-18 keeps its current cap`,
  cohesion: (f, t2) => `cohesion ${f} → ${t2} · more or fewer members excluded from batches by default`,
  warn_below: (_f, t2) => `classes with fewer than ${t2} test windows warn at launch`,
  test_pct: (f, t2) => `test portion ${f} → ${t2} % · applies to new training jobs · registered models keep their split`,
  omit_d: (_f, t2) => `omit motifs past d ${t2} · fewer omitted at the next regroup · existing groupings keep their settings`,
  keep: (f, t2) => `keep ${f} → ${t2} backups · about ${Math.round((Number(t2) - Number(f)) * 2.1)} GB more in ./backups`,
  /* Export (§9.12): what changes about the files that leave the tool — never a restatement of the list. */
  'motifs.include': (f, t2) => listSentence(f, t2, 'family exports', {
    on: 'exports already written are unchanged',
    off: 'the grouping is harder to read without it; exports already written keep it',
  }),
  'motifs.formats': (f, t2) => {
    const { added, removed } = listDelta(f, t2)
    if (added.length && !removed.length) return `every family export also writes ${andList(added)} · one file per format`
    if (removed.length && !added.length) return `family exports stop writing ${andList(removed)} · the other formats are unchanged`
    return `family exports write ${andList(added)} instead of ${andList(removed)}`
  },
  'motifs.layout': (_f, t2) => t2 === 'a file per family'
    ? 'one file per family · a single family travels on its own, families no longer compare in one sheet'
    : 'one workbook, a sheet per family · families compare side by side, the whole grouping moves as one file',
  'ws.format': (_f, t2) => String(t2).startsWith('parquet')
    ? 'window sets are written as parquet · columnar, readable outside Python; npz readers need converting'
    : 'window sets are written as npz · loads with numpy alone; no columnar readers',
  'ws.include': (f, t2) => listSentence(f, t2, 'window-set exports', {
    on: 'the set stays reusable without this database',
    off: 'a window set without it cannot be rebuilt outside this database',
  }),
  'templates.carry_exemplars': (_f, t2) => t2
    ? 'seed templates carry their exemplar windows · larger files that read without this database'
    : 'seed templates export without their exemplar windows · smaller files that only read back against this database',
  'models.weights': (_f, t2) => t2 === 'ONNX'
    ? 'models export as ONNX · they load outside PyTorch, the training graph does not travel'
    : 'models export as PyTorch weights · the training graph travels, ONNX consumers cannot read them',
  'reports.layout': (_f, t2) => t2 === 'a file per stage'
    ? 'run reports write one file per stage · a stage drops straight into a chapter, no document reads end to end'
    : 'run reports write one document, stages in order · reads end to end, a single stage has to be cut out',
  'bundle.contents': (f, t2) => listSentence(f, t2, 'the reproducibility bundle', {
    singular: true,
    on: 'the zip grows; a rerun has more of what it needs',
    off: 'a rerun from the bundle may not reproduce the run',
  }),
}
export const genericConsequence = (id: string, from: unknown, to: unknown) =>
  channelsConsequence(id, from, to) ?? `${id.split('.').slice(-1)[0].replace(/_/g, ' ')} ${String(from)} → ${String(to)} · applies to new runs`

/* --------------------------------------------------- the settings search index */
export interface SearchHit { slug: string; page: string; card: string; field: string }
export const SEARCH_INDEX: SearchHit[] = [
  { slug: 'datasets', page: 'Datasets', card: 'Recordings', field: 'noise floor' },
  { slug: 'datasets', page: 'Datasets', card: 'Held-out recording', field: 'hold out a recording' },
  { slug: 'channels-events', page: 'Channels & events', card: 'Channels', field: 'gain' },
  { slug: 'channels-events', page: 'Channels & events', card: 'Event log', field: 'effect' },
  { slug: 'vocabulary', page: 'Vocabulary', card: 'Verdicts', field: 'key' },
  { slug: 'nulls', page: 'Nulls', card: 'Significance', field: 'significance level α' },
  { slug: 'nulls', page: 'Nulls', card: 'Null per analysis kind', field: 'draws' },
  { slug: 'analysis-defaults', page: 'Analysis defaults', card: 'Matching rule', field: 'reciprocal overlap (IoU)' },
  { slug: 'analysis-defaults', page: 'Analysis defaults', card: 'Step cache', field: 'keep stale artifacts for' },
  { slug: 'compute-hpc', page: 'Compute & HPC', card: 'Local limits per workspace', field: 'run locally up to' },
  { slug: 'blocks', page: 'Blocks', card: 'Registered blocks', field: 'on' },
  { slug: 'review-queues', page: 'Review queues', card: 'Clusters', field: 'cohesion limit' },
  { slug: 'models-registration', page: 'Models & registration', card: 'Evaluation split', field: 'test portion' },
  { slug: 'library-groupings', page: 'Library groupings', card: 'What does not fit', field: 'omit motifs with nearest family d >' },
  { slug: 'storage-backups', page: 'Storage & backups', card: 'Backups', field: 'keep' },
  { slug: 'export', page: 'Export', card: 'Motifs and families', field: 'include' },
  { slug: 'display', page: 'Display', card: 'Units and time', field: 'time axis' },
  { slug: 'keyboard', page: 'Keyboard & behaviour', card: 'Keys', field: 'skip without writing' },
]
