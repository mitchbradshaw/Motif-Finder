/* Library reads (frames library-1 … library-7). Every read resolves fixture data through the seam and says
 * `source: 'demo'`; a later ticket swaps each body for a bridge call without touching the pages. */
import { demo, type Sourced } from './seam'
import {
  AMPLITUDE_DISTRIBUTION, BASIS_OPTIONS, CUSTOM_CLUSTERINGS, F03_DETAIL, FREQ_DISTRIBUTION, GROUPINGS, IMPORT_BUNDLES, LIBRARY_COUNTS, MERGE_HEIGHTS,
  MOTIF_FAMILIES, OMITTED_G07, OMITTED_G08_SEQUENCES, OMITTED_G08_SINGLES, RECURRENCE_RECORDINGS, SEQUENCE_FAMILIES, SHARED_GROUND, COVERAGE,
  TEMPLATE_LIST, TIMESCALE_DISTRIBUTION, UNIT_OPTIONS, WINDOW_SETS, genericFamilyMembers,
  type BasisOption, type FamilyDetail, type FeatureBin, type Grouping, type ImportBundle, type MotifFamily, type OmittedEntry, type RecGroup,
  type SequenceFamily, type Template, type UnitOption, type WindowSetRow,
} from '../fixtures/library'

export type { BasisOption, FamilyDetail, FeatureBin, Grouping, ImportBundle, MotifFamily, OmittedEntry, RecGroup, SequenceFamily, Template, UnitOption, WindowSetRow }
export type { Member, RemovedMember, Verdict, Cell, ShapeKind, BasisKind, Unit, TemplateKind, SetCheck, SplitBlock, ImportCheck, ImportSample } from '../fixtures/library'

export interface LibraryCounts { motifs: number; windowSets: number; templates: number; spikeTrains: number; sequences: number }
export const getLibraryCounts = (): Promise<Sourced<LibraryCounts>> => demo(LIBRARY_COUNTS)

export const getGroupings = (): Promise<Sourced<Grouping[]>> => demo(GROUPINGS)

export interface RecurrenceData { recordings: RecGroup[]; families: MotifFamily[]; coverage: Record<string, number>; sharedGround: { pair: [string, string]; family: string }[] }
export const getRecurrence = (): Promise<Sourced<RecurrenceData>> => demo({ recordings: RECURRENCE_RECORDINGS, families: MOTIF_FAMILIES, coverage: COVERAGE, sharedGround: SHARED_GROUND })

export const getMotifFamilies = (): Promise<Sourced<MotifFamily[]>> => demo(MOTIF_FAMILIES)
export const getSequenceFamilies = (): Promise<Sourced<SequenceFamily[]>> => demo(SEQUENCE_FAMILIES)

export interface OmittedData { groupingId: string; singles: OmittedEntry[]; sequences: OmittedEntry[] }
export const getOmitted = (groupingId: string): Promise<Sourced<OmittedData>> =>
  demo(groupingId === 'g-08' ? { groupingId, singles: OMITTED_G08_SINGLES, sequences: OMITTED_G08_SEQUENCES } : { groupingId, singles: OMITTED_G07, sequences: [] })

export type FamilyRead = { kind: 'motif'; detail: FamilyDetail } | { kind: 'sequence'; family: SequenceFamily } | { kind: 'missing'; id: string }
export function getFamily(id: string): Promise<Sourced<FamilyRead>> {
  if (id === 'F-03') return demo<FamilyRead>({ kind: 'motif', detail: F03_DETAIL }, 90)
  const f = MOTIF_FAMILIES.find(x => x.id === id)
  if (f) return demo<FamilyRead>({ kind: 'motif', detail: { family: f, cut: 0.42, members: genericFamilyMembers(f), removed: [], channels: Object.values(f.cells).filter(c => c.count > 0).length, depthLabel: f.depthLabel, handAdded: 0 } }, 90)
  const s = SEQUENCE_FAMILIES.find(x => x.id === id)
  if (s) return demo<FamilyRead>({ kind: 'sequence', family: s })
  return demo<FamilyRead>({ kind: 'missing', id })
}

export interface GroupingEditorData { units: UnitOption[]; bases: BasisOption[]; distributions: Record<string, FeatureBin[]>; clusterings: typeof CUSTOM_CLUSTERINGS }
export const getGroupingEditor = (): Promise<Sourced<GroupingEditorData>> =>
  demo({ units: UNIT_OPTIONS, bases: BASIS_OPTIONS, distributions: { 'frequency-content': FREQ_DISTRIBUTION, amplitude: AMPLITUDE_DISTRIBUTION, timescale: TIMESCALE_DISTRIBUTION, 'shape-distance': MERGE_HEIGHTS, 'sequence-similarity': MERGE_HEIGHTS }, clusterings: CUSTOM_CLUSTERINGS })

export const IMPORT_BUNDLE_PATHS = Object.keys(IMPORT_BUNDLES)
/** The dry run of a bundle (reads the bundle and checks it against the library; writes nothing). */
export function dryRunImport(path: string): Promise<Sourced<ImportBundle>> {
  const b = IMPORT_BUNDLES[path]
  if (!b) return Promise.reject(new Error(`no bundle at ${path}`))
  return demo(b, 600)
}

export const getWindowSets = (): Promise<Sourced<WindowSetRow[]>> => demo(WINDOW_SETS)
export const getTemplates = (): Promise<Sourced<Template[]>> => demo(TEMPLATE_LIST)

/* Presentation helpers and demo constants the pages need alongside the reads (shape synthesis for "resample",
 * the shared mV domain rule, labels). Pages import them from here, never from fixtures directly. */
export {
  AMP_DOMAIN, CANON_SELECTION, CLASS_COLOURS, CLASS_OPTIONS, GROUPING_G09, HAND_EDITS_ORPHANED, IMPORT_FAIL_ERROR, IMPORT_STEPS, RECURRENCE_RECORDINGS as RECORDING_GROUPS,
  REVIEW_QUEUE_CAP, TAG_RULE, TAG_VOCABULARY, UNIT_LABEL, motifShape, niceMvDomain,
} from '../fixtures/library'
export { FAMILY_COLOURS, HELD_OUT_KEY } from '../fixtures/canon'
