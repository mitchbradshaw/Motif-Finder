/* Library reads (frames library-1 … library-7), wired to the bridge (`server/library.py`, 20 routes under
 * `/api/library`).
 *
 * Every exported name, signature and return type is what it was when these resolved fixtures: the pages call
 * the same functions and render the same shapes. What changed is the body — each read now wraps a bridge call
 * in `live(...)`, so the header chip says "live" and a failure surfaces as an error card with the server's
 * message rather than a silent fall back to the canon. Nothing here catches a read into a blank.
 *
 * NO READ IS STILL ON `demo()`: all 11 have a live source (`api/explore.ts` is the precedent for saying so
 * when some do not). What remains fixture-shaped is the *synchronous* scaffolding, and each piece of it now
 * has a live read beside it that supersedes it:
 *   - `IMPORT_BUNDLE_PATHS` is now an empty array; `getImportBundles()` is the read (`GET /import/bundles`).
 *   - `RECORDING_GROUPS` is the fixture corpus; `getRecordingGroups()` is the read.
 *   - `GROUPING_G09`, `HAND_EDITS_ORPHANED`, `IMPORT_STEPS`, `IMPORT_FAIL_ERROR`, `CANON_SELECTION` and
 *     `REVIEW_QUEUE_CAP` are demo scaffolding for pages that still simulate a job; they are NOT live data and
 *     a page that renders one is showing a fixture.
 *
 * `motifShape` stays exported (the omitted-entry thumbnails still synthesise from `shape/amp/seed`, which is
 * all the omitted rows carry) but it MUST NOT be used to draw a family, a member or a sequence any more: the
 * bridge returns real decimated mV in `exemplarTrace` / `medoidTrace`, read off the memmap. A synthesised
 * trace drawn next to a real one is a finding that is not there. `niceMvDomain`, `AMP_DOMAIN`, `CLASS_COLOURS`,
 * `TAG_RULE`, `UNIT_LABEL` and friends are presentation, and stay.
 */
import { live, type Sourced } from './seam'
import {
  getLibraryCounts as apiCounts, getLibraryGroupings as apiGroupings, getLibraryRecurrence as apiRecurrence,
  getLibraryFamilies as apiFamilies, getLibrarySequenceFamilies as apiSequenceFamilies, getLibraryFamily as apiFamily,
  getLibraryOmitted as apiOmitted, getLibraryGroupingEditor as apiGroupingEditor, getLibraryWindowSets as apiWindowSets,
  getLibraryTemplates as apiTemplates, getLibraryImportBundles as apiImportBundles, dryRunLibraryImport as apiDryRun,
  type LibBundleRef, type LibFamily, type LibSequenceFamily, type LibWindowSet,
} from '../api'
import { CUSTOM_CLUSTERINGS } from '../fixtures/library'
import type {
  BasisOption, FamilyDetail, FeatureBin, Grouping, ImportBundle, MotifFamily, OmittedEntry, RecGroup,
  SequenceFamily, ShapeKind, SplitBlock, Template, UnitOption, WindowSetRow,
} from '../fixtures/library'

export type { BasisOption, FamilyDetail, FeatureBin, Grouping, ImportBundle, MotifFamily, OmittedEntry, RecGroup, SequenceFamily, Template, UnitOption, WindowSetRow }
export type { Member, RemovedMember, Verdict, Cell, ShapeKind, BasisKind, Unit, TemplateKind, SetCheck, SplitBlock, ImportCheck, ImportSample } from '../fixtures/library'

/* ---------------------------------------------------------------- small mappers ---------------------------------------------------------------- */

const SHAPES: ShapeKind[] = ['drop', 'burst', 'sharkfin', 'spiketrain', 'ripple', 'plateau', 'drift', 'fall', 'peak', 'notch']
/** A shape the pages can draw. The bridge reads it off the entry's tags and falls back to `drop`; anything
 *  outside the vocabulary would render as a blank glyph, so it lands on `drop` here too rather than silently. */
const shapeOf = (s: string | undefined): ShapeKind => (SHAPES as string[]).includes(s ?? '') ? (s as ShapeKind) : 'drop'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
/** `'2026-09-12T08:14:00'` → `'12 Sep'`. The saved column is read as a day by the sets table (it sorts on the
 *  leading number), so an ISO stamp is rendered into the form that table reads. An unparseable stamp is
 *  returned verbatim — a date nobody can read is better than a date that is wrong. */
function humanDay(value: string | null | undefined): string {
  const text = String(value ?? '').trim()
  if (!text) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(text)
  if (!m) return text
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1] ?? m[2]}`
}

/** A family, with its shape coerced for the sketch glyph but its real one kept beside it.
 *
 *  The bridge now reads `shape` off the entry's `element` tags, so it carries the project's own
 *  vocabulary — `trough` on 121 of the 149 live families, `sharkfin` on 28. `ShapeKind` is a fixed
 *  union of the ten glyphs `motifShape` can draw and `trough` is not one of them, so `shapeOf` lands
 *  those on `drop`. That keeps a glyph drawable, and it would also quietly relabel five families in six
 *  — so `shapeLabel` travels alongside with what the tags actually said, and any surface that names the
 *  shape must use the label, never the coerced value. Same rule as `omitted()` below. */
const family = (f: LibFamily): MotifFamily => {
  const raw = f as unknown as { shape: string | null; shapeLabel?: string; shapeMix?: string }
  return {
    ...f,
    shape: shapeOf(raw.shape ?? undefined),
    shapeKnown: raw.shape != null,
    shapeLabel: raw.shapeLabel ?? (raw.shape ?? 'shape not recorded'),
    shapeMix: raw.shapeMix,
  } as unknown as MotifFamily
}
const sequenceFamily = (s: LibSequenceFamily): SequenceFamily => s as SequenceFamily

/** `splitPlan` is a `Record<channel, SplitBlock[]>` in the sets table's band strip, but the column it comes
 *  from is free JSON: a set saved with `{"test": 400}` and no plan would make the strip iterate a number.
 *  Only entries that really are block lists survive. */
function splitPlan(plan: Record<string, unknown> | null | undefined): Record<string, SplitBlock[]> {
  const out: Record<string, SplitBlock[]> = {}
  for (const [k, v] of Object.entries(plan ?? {})) {
    if (Array.isArray(v) && v.every(b => b && typeof b === 'object' && 'split' in (b as object))) out[k] = v as SplitBlock[]
  }
  return out
}

const windowSet = (w: LibWindowSet): WindowSetRow => ({ ...w, saved: humanDay(w.saved), splitPlan: splitPlan(w.splitPlan) }) as unknown as WindowSetRow

/* ---------------------------------------------------------------- the 11 reads ---------------------------------------------------------------- */

export interface LibraryCounts { motifs: number; windowSets: number; templates: number; spikeTrains: number; sequences: number }
export const getLibraryCounts = (): Promise<Sourced<LibraryCounts>> => live(apiCounts())

/** Every saved grouping, oldest first (the bridge orders by id, so the last of a unit is the newest). */
export const getGroupings = (): Promise<Sourced<Grouping[]>> => live(apiGroupings() as Promise<Grouping[]>)

export interface RecurrenceData { recordings: RecGroup[]; families: MotifFamily[]; coverage: Record<string, number>; sharedGround: { pair: [string, string]; family: string }[] }
/** The recurrence matrix. `groupingId` is optional and omitting it means "the newest grouping of motifs",
 *  which is what the bridge resolves when `?grouping=` is absent. */
export const getRecurrence = (groupingId?: string): Promise<Sourced<RecurrenceData>> => live((async () => {
  const r = await apiRecurrence(groupingId)
  return { recordings: r.recordings as RecGroup[], families: r.families.map(family), coverage: r.coverage, sharedGround: r.sharedGround }
})())

/** The recording rows of the recurrence matrix, on their own — the live replacement for the fixture
 *  `RECORDING_GROUPS` that the atlas and the sets table use to label a `recKey:channel`. It costs what
 *  `getRecurrence` costs (the grouping is resolved and its families built), so a page that already reads
 *  recurrence should take `.recordings` from that read instead of calling this. */
export const getRecordingGroups = (groupingId?: string): Promise<Sourced<RecGroup[]>> =>
  live(apiRecurrence(groupingId).then(r => r.recordings as RecGroup[]))

export const getMotifFamilies = (groupingId?: string): Promise<Sourced<MotifFamily[]>> =>
  live(apiFamilies(groupingId).then(fs => fs.map(family)))
export const getSequenceFamilies = (groupingId?: string): Promise<Sourced<SequenceFamily[]>> =>
  live(apiSequenceFamilies(groupingId).then(fs => fs.map(sequenceFamily)))

export interface OmittedData {
  groupingId: string; singles: OmittedEntry[]; sequences: OmittedEntry[]
  /** The grouping that answered for the `sequences` half — a different saved grouping from `groupingId`,
   *  because no grouping holds both units. `null` when this library has none. */
  sequenceGroupingId: string | null
  /** A CATALOGUE fact, not a grouping one: members that belong to no sequence at all. The sequences atlas used
   *  to print `singles.length` under the sentence "motifs in no sequence", which counts something else
   *  entirely (what THIS grouping omitted). `null` when the bridge does not carry it. */
  motifsInNoSequence: number | null
}
/** What did not fit, and why. The bridge returns the whole list for the grouping; the drawer pages it in the
 *  browser, so a grouping that omitted thousands of entries ships thousands of rows.
 *
 *  `shape` is what the entry's `element` tag recorded and it can be ABSENT — `shapeOf` lands an absent shape
 *  on `drop` so a glyph still draws, so `shapeKnown` travels beside it and a surface that draws the shape must
 *  check it rather than sketching a `drop` nobody measured. */
export const getOmitted = (groupingId: string): Promise<Sourced<OmittedData>> => live((async () => {
  const o = await apiOmitted(groupingId)
  const entry = (e: { shape: string | null }): OmittedEntry => {
    const raw = e as unknown as { shape: string | null; shapeLabel?: string }
    return { ...e, shape: shapeOf(raw.shape ?? undefined), shapeKnown: raw.shape != null, shapeLabel: raw.shapeLabel ?? 'shape not recorded' } as unknown as OmittedEntry
  }
  const extra = o as unknown as { sequenceGroupingId?: string | null; motifsInNoSequence?: number | null }
  return {
    groupingId: o.groupingId ?? groupingId,
    singles: o.singles.map(entry), sequences: o.sequences.map(entry),
    sequenceGroupingId: extra.sequenceGroupingId ?? null,
    motifsInNoSequence: typeof extra.motifsInNoSequence === 'number' ? extra.motifsInNoSequence : null,
  }
})())

export type FamilyRead = { kind: 'motif'; detail: FamilyDetail } | { kind: 'sequence'; family: SequenceFamily } | { kind: 'missing'; id: string }
/** One family. An id the grouping does not hold comes back as `{kind:'missing'}` — a 200 the page draws, not
 *  an error and not a blank. */
/** One family. `unit` decides which of the two catalogues the label is looked up in — see the note on
 *  `getLibraryFamily` in `../api`: the same label names a motif family and a sequence family 19 times
 *  over, so omitting it is how a sequence family quietly opens as a motif one. */
export const getFamily = (id: string, groupingId?: string,
                          unit?: 'motifs' | 'sequences'): Promise<Sourced<FamilyRead>> => live((async () => {
  const r = await apiFamily(id, groupingId, unit)
  if (r.kind === 'motif') return { kind: 'motif', detail: { ...r.detail, family: family(r.detail.family) } } as FamilyRead
  if (r.kind === 'sequence') return { kind: 'sequence', family: sequenceFamily(r.family) } as FamilyRead
  return { kind: 'missing', id: r.id } as FamilyRead
})())

export interface GroupingEditorData { units: UnitOption[]; bases: BasisOption[]; distributions: Record<string, FeatureBin[]>; clusterings: typeof CUSTOM_CLUSTERINGS }
/** The grouping editor's options and its five distributions. The distributions are computed over a capped
 *  sample of the catalogue (the cap travels on the payload as `distributionsSampledFrom`); `unit` selects
 *  which bases apply — one that does not carries the core's own reason. */
export const getGroupingEditor = (unit = 'motifs'): Promise<Sourced<GroupingEditorData>> => live((async () => {
  const e = await apiGroupingEditor(unit)
  return { units: e.units as UnitOption[], bases: e.bases as BasisOption[], distributions: e.distributions, clusterings: e.clusterings }
})())

/** @deprecated The importable bundles are a read now (`getImportBundles`), because the registry is what says
 *  which bundles exist. Kept as an empty array so a page that still renders it renders nothing rather than
 *  three fixture paths that address no file. */
export const IMPORT_BUNDLE_PATHS: string[] = []

export interface ImportBundleRef { path: string; name: string; kind: string; registeredAt: string | null; heldOut: boolean }
/** The bundles the registry knows about (`registered_artifacts`, active, of an importable kind) — not a disk
 *  rescan, so the list is reproducible. */
export const getImportBundles = (): Promise<Sourced<ImportBundleRef[]>> =>
  live(apiImportBundles() as Promise<LibBundleRef[]>)

/** The dry run of a bundle (reads the bundle and checks it against the library; writes nothing — the
 *  importers assert their own row counts are unchanged under `dry_run`). A bundle that cannot be imported
 *  comes back with `blockedReason` and a failing check, which is a payload the page draws. */
export const dryRunImport = (path: string, kind?: string): Promise<Sourced<ImportBundle>> => live((async () => {
  const b = await apiDryRun(path, kind)
  return { ...b, sample: b.sample.map(s => ({ ...s, shape: shapeOf(s.shape) })) } as unknown as ImportBundle
})())

export const getWindowSets = (): Promise<Sourced<WindowSetRow[]>> => live(apiWindowSets().then(ws => ws.map(windowSet)))

/** The Library's presentation `Template[]`, mapped from the real `templates` table. Note this is NOT
 *  `api.ts`'s `getTemplates`: that one is id-keyed and carries `steps`; this one is keyed by name and carries
 *  stages with glyphs. Same rows, two shapes. */
export const getTemplates = (): Promise<Sourced<Template[]>> => live(apiTemplates() as unknown as Promise<Template[]>)

/* Presentation helpers and the demo scaffolding the pages still need alongside the reads (shape synthesis for
 * the omitted thumbnails, the shared mV domain rule, labels). Pages import them from here, never from
 * fixtures directly. `RECORDING_GROUPS`, `CANON_SELECTION`, `GROUPING_G09`, `HAND_EDITS_ORPHANED`,
 * `IMPORT_STEPS` and `IMPORT_FAIL_ERROR` are fixtures, not live data. */
export {
  AMP_DOMAIN, CANON_SELECTION, CLASS_COLOURS, CLASS_OPTIONS, GROUPING_G09, HAND_EDITS_ORPHANED, IMPORT_FAIL_ERROR, IMPORT_STEPS, RECURRENCE_RECORDINGS as RECORDING_GROUPS,
  REVIEW_QUEUE_CAP, TAG_RULE, TAG_VOCABULARY, UNIT_LABEL, motifShape, niceMvDomain,
} from '../fixtures/library'
export { FAMILY_COLOURS, HELD_OUT_KEY } from '../fixtures/canon'
