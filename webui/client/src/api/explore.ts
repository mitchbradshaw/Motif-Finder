/* Explore reads (brief: every read goes through a typed async function returning Sourced<T>).
 * Corpus and Signal were always live against the bridge (src/api.ts). Since stage-3 prompt 01 the
 * regions that used to be fixtures are live too, through the same shapes the pages already consume:
 *   - getCorpusLive: the run / method lists from GET /api/corpus/{file}/runs, per-channel tag counts and
 *     reviewed coverage from GET /api/channels/{id}/tags (annotation_tags, reviewed_spans);
 *   - getSignalLive: the runs on the channel (methods, colours, counts) and the annotation / detection
 *     rows for the drawer, from /runs, /tags and /spans;
 *   - getCrossChannel: every sibling channel's window with lag / r / classification from GET /api/cross/{id}
 *     (Working.cross_channel), anchored on the channel's first human span or its first ten minutes;
 *   - lookupChannel: GET /api/channels/{id} (423 = held out).
 * Only the two things nothing computes yet stay demo and say so: the Span-edit page and the keyboard map. */
import {
  getChannel, getCross, getRecordings, getRunsForFile, getSpans, getTags, type Annotation, type Detection, type FileRun, type Spans,
} from '../api'
import { demo, live, type Sourced } from './seam'
import {
  SHORTCUTS, spanEditDemo, type AnnotationRow, type CanonChannelRef, type CorpusDemo, type CrossDemo, type DemoRun, type DetectionRow,
  type SignalDemo, type SpanEditDemo, type Verdict, type XRow,
} from '../fixtures/explore'

export type {
  AnnotationRow, CorpusDemo, CrossDemo, DemoRun, DetectionRow, Revision, SignalDemo, SnapRule, SpanEditDemo, Verdict, XBin, XRow,
} from '../fixtures/explore'
export { FILTER_VOCAB, METHODS, RAIL_TAGS, VERDICT_KEYS } from '../fixtures/explore'
import { VERDICTS } from '../fixtures/canon'
/** Verdict colours from the shared canon (seed and interesting are both human → green, §3). */
export const VERDICT_COLOURS: Record<string, string> = Object.fromEntries(VERDICTS.map(v => [v.key, v.colour]))

/** Run colours by index (family palette avoids pure red/green/blue, §3). */
const RUN_COLOURS = ['#0A84FF', '#FF9F0A', '#BF5AF2', '#64D2FF', '#30D158', '#FF375F', '#AC8E68', '#5E5CE6', '#8E8E93']
const runId = (r: FileRun) => `#${r.id}`
const runName = (r: FileRun) => r.name ?? (r.algorithms.length ? r.algorithms.join(' → ') : `run ${r.id}`)
const isSurrogate = (r: FileRun) => r.algorithms.includes('surrogate') || /surrogate/i.test(r.name ?? '')

/** Where a channel id lives, from the recordings list: 'held_out' | 'missing' | the channel's file — so a page
 *  can show its locked / unknown card without a request the browser would log as an error (423 / 404). */
async function locate(id: number): Promise<{ state: 'held_out' | 'missing' | 'ok'; file: string | null; name: string | null; reason: string | null }> {
  const recs = await getRecordings()
  for (const f of recs) {
    const c = f.channels.find(ch => ch.id === id)
    if (c) return f.held_out ? { state: 'held_out', file: f.source_file, name: c.name, reason: f.held_out_reason ?? `${f.source_file} is held out` } : { state: 'ok', file: f.source_file, name: c.name, reason: null }
  }
  return { state: 'missing', file: null, name: null, reason: `no channel with id ${id}` }
}

/* ------------------------------------------------------------------ corpus ---- */
/** Tags, reviewed coverage and the recording-wide run / method lists for the Corpus rail — live. */
export async function getCorpusLive(file: string, channels: { id: number; name: string }[], bins: number): Promise<Sourced<CorpusDemo>> {
  if (!file || !channels.length) return live(Promise.resolve({ runs: [], methods: [], tags: [], channels: [] }))
  const runs = await getRunsForFile(file)
  const tagsByChannel = await Promise.all(channels.map(c => getTags(c.id)))
  const vocab = new Set<string>()
  for (const t of tagsByChannel) for (const v of t.vocabulary) vocab.add(v.value)
  for (const t of tagsByChannel) for (const k of Object.keys(t.tag_counts)) vocab.add(k.split(':').slice(1).join(':'))
  const rows = channels.map((c, i) => {
    const t = tagsByChannel[i]
    const dur = t.t1_s || 1
    const tagCounts: Record<string, number> = {}
    for (const [k, n] of Object.entries(t.tag_counts)) { const v = k.split(':').slice(1).join(':'); tagCounts[v] = (tagCounts[v] ?? 0) + n }
    // a bin counts as reviewed when at least half of its samples lie under a reviewed span — a single
    // 600-sample window inside a twelve-hour bin must not paint the whole bin as looked-at
    const reviewed = Array.from({ length: bins }, (_, b) => {
      const b0 = (b / bins) * dur, b1 = ((b + 1) / bins) * dur
      let covered = 0
      for (const r of t.reviewed) { const lo = Math.max(b0, r.start_s), hi = Math.min(b1, r.end_s); if (hi > lo) covered += hi - lo }
      return covered >= 0.5 * (b1 - b0)
    })
    return { name: c.name, tagCounts, reviewed, reviewedPct: Math.round(t.reviewed_pct) }
  })
  return { data: { runs: runs.runs.map(r => ({ id: runId(r), name: runName(r), method: r.method })), methods: runs.methods, tags: [...vocab].sort(), channels: rows }, source: 'live' }
}

/* ------------------------------------------------------------------ signal ---- */
function annotationRow(a: Annotation & { tags?: { category: string; value: string }[] }, fs: number): AnnotationRow {
  const by = (cat: string) => a.tags?.find(t => t.category === cat)?.value ?? ''
  return {
    id: a.id, start: Math.round(a.start_s * fs), end: Math.round(a.end_s * fs), verdict: a.verdict as Verdict,
    tags: (a.tags ?? []).map(t => t.value), source: (a.source === 'imported_10min' ? 'imported_10min' : 'manual_ui'), note: a.note ?? '',
    element: by('element') || a.tag || '', quality: by('quality'), structure: by('structure'), status: by('status'), spikeTrainLength: '',
  }
}
function detectionRow(d: Detection, fs: number, runs: Map<number, DemoRun>): DetectionRow {
  const r = runs.get(d.run_id)
  return { id: d.id, runId: `#${d.run_id}`, runName: r?.name ?? `run ${d.run_id}`, method: r?.method ?? '?', start: Math.round(d.start_s * fs), end: Math.round(d.end_s * fs),
           score: d.score ?? 0, adjudication: 'unadjudicated', family: null }
}

/** Runs with methods and colours, plus the annotation / detection rows of the channel — live.
 *  Adjudications, families and the medoid have no live source yet (Prompts 03 and 05) and are empty. */
export async function getSignalLive(channelId: number): Promise<Sourced<SignalDemo | null>> {
  if ((await locate(channelId)).state !== 'ok') return { data: null, source: 'live' }
  const ch = await getChannel(channelId)
  const [runsRes, tags, spans] = await Promise.all([getRunsForFile(ch.source_file), getTags(channelId), getSpans(channelId, 0, ch.duration_s)])
  const mine = runsRes.runs.filter(r => r.recording_id === channelId)
  const runs: DemoRun[] = mine.map((r, i) => ({ id: runId(r), name: runName(r), method: r.method, template: r.algorithms[r.algorithms.length - 1] ?? '', surrogate: isSurrogate(r), colour: RUN_COLOURS[i % RUN_COLOURS.length], count: r.n_detections }))
  const byId = new Map(mine.map((r, i) => [r.id, runs[i]]))
  const annotations = tags.annotations.map(a => annotationRow(a, ch.fs))
  const detections = spans.detections.map(d => detectionRow(d, ch.fs, byId))
  return {
    data: {
      channelId, channelName: ch.name, file: ch.source_file, fs: ch.fs, viewport: [0, Math.min(ch.duration_s, 7200)],
      runs, defaultRuns: runs.filter(r => !r.surrogate).slice(0, 3).map(r => r.id), annotations, detections,
      motifDetectionId: detections[0]?.id ?? -1, spanTags: [], spanNote: '', medoid: [],
      defaultSelectedAnnotations: annotations.slice(0, 2).map(a => a.id), defaultSelectedDetections: detections.slice(0, 2).map(d => d.id),
    },
    source: 'live',
  }
}
/** Kept name for the pages: now the live read. */
export const getSignalDemo = getSignalLive

/** The keyboard map the Shortcuts tab renders (Settings › Keyboard owns editing it) — a static table, demo. */
export const getShortcuts = () => demo(SHORTCUTS, 10)

/** Which recording a channel id belongs to, and whether it is held out — live (423 = held out). */
export interface ChannelLookup { channel: CanonChannelRef | null; heldOut: boolean; reason: string | null }
export async function lookupChannel(id: number): Promise<Sourced<ChannelLookup>> {
  const where = await locate(id)
  if (where.state === 'ok') return { data: { channel: { id, name: where.name!, recordingKey: where.file!.replace(/_concat.*|\.mat$/g, ''), file: where.file! }, heldOut: false, reason: null }, source: 'live' }
  return { data: { channel: null, heldOut: where.state === 'held_out', reason: where.reason }, source: 'live' }
}

/* ------------------------------------------------------------- cross-channel ---- */
/** Verdicts worth opening a cross-channel comparison on, best first. Taking `annotations[0]` instead
 *  landed the page on whichever span started earliest, which on every M2_aug channel is a bulk
 *  `imported_10min` block with verdict `not_interesting` — a deliberately boring window.
 *  This is a *preference* order for anchoring, not the shared verdict vocabulary (`VERDICTS`, which runs
 *  seed · interesting · not_interesting · artifact · unsure) — `not_interesting` is deliberately absent so
 *  a machine detection beats a bulk import block. */
const ANCHOR_RANK = ['seed', 'interesting', 'artifact', 'unsure']
const anchorSpan = (s: Spans): Annotation | Detection | null => {
  const ranked = s.annotations
    .filter(a => ANCHOR_RANK.includes(a.verdict))
    .sort((p, q) => ANCHOR_RANK.indexOf(p.verdict) - ANCHOR_RANK.indexOf(q.verdict) || p.start_s - q.start_s)
  return ranked[0] ?? s.detections[0] ?? s.annotations[0] ?? null
}

/** Cross-channel compares short windows — the window dropdown says so in as many words. An anchor span
 *  longer than this is opened on its first ten minutes instead: `M2_concat_fs1` CH4 carries a 20-hour
 *  `interesting` annotation, and honouring it asks the route to cross-correlate 72,000 samples against
 *  fifteen siblings, which does not return. */
const CROSS_MAX_SPAN_S = 600
const windowLabel = (first: Annotation | Detection | null, startS: number, clamped: boolean): string =>
  !first ? 'first ten minutes'
    : `${clamped ? 'first 10 min of the ' : ''}${'verdict' in first ? first.verdict : `detection ${first.id}`} span at ${(startS / 3600).toFixed(2)} h`

/** The same window on every channel of the reference's recording, with lag and r — live.
 *  The window is the channel's most notable human span (± `padS`), or its first ten minutes when it has none. */
export async function getCrossChannel(referenceId: number, padS = 20): Promise<Sourced<CrossDemo | null>> {
  if ((await locate(referenceId)).state !== 'ok') return { data: null, source: 'live' }
  const ch = await getChannel(referenceId)
  const spans = await getSpans(referenceId, 0, ch.duration_s)
  const first = anchorSpan(spans)
  const clamped = !!first && first.end_s - first.start_s > CROSS_MAX_SPAN_S
  const motif = first
    ? { s: first.start_s, e: clamped ? first.start_s + CROSS_MAX_SPAN_S : first.end_s }
    : { s: 0, e: Math.min(CROSS_MAX_SPAN_S, ch.duration_s) }
  const t0 = Math.max(0, motif.s - padS), t1 = Math.min(ch.duration_s, motif.e + padS)
  const x = await getCross(referenceId, t0, t1, 600)
  // the envelope verbatim: t stays absolute (and non-uniform once decimated), a null stays a null so the
  // line breaks at a gap instead of writing NaN into the path and truncating the rest of the trace
  const rows: XRow[] = x.channels.map(row => ({
    channelId: row.id, name: row.name, lagS: row.lag_s, r: row.r, classification: row.classification,
    t: row.envelope?.t ?? [], v: row.envelope?.v ?? [], error: row.error,
  }))
  // a loop, not Math.min(...all): a decimated 16-channel window is ~19k samples and spreading that into
  // an argument list is how you get a RangeError on a big recording
  let lo = Infinity, hi = -Infinity
  for (const r of rows) for (const v of r.v) { if (v === null || Number.isNaN(v)) continue; if (v < lo) lo = v; if (v > hi) hi = v }
  if (!(lo < hi)) { lo = -1; hi = 1 }
  return {
    data: {
      recording: ch.source_file.replace(/\.mat$/, ''), file: ch.source_file, referenceId, referenceName: ch.name,
      window: { label: windowLabel(first, motif.s, clamped), startH: t0 / 3600, endH: t1 / 3600, durS: t1 - t0, t0S: t0, fs: x.fs, motifStartS: motif.s, motifEndS: motif.e },
      channels: x.channels.map(c => ({ id: c.id, name: c.name })), rows,
      // |r|, not r: the core classifies r = −0.86 as propagation, so selecting on the signed value hid
      // exactly the channels it thought were most related. Ranked before the cap too — slicing in channel
      // order dropped the strongest correlate whenever more than five siblings passed the cut.
      defaultSelected: [
        referenceId,
        ...rows.filter(r => r.channelId !== referenceId && Math.abs(r.r ?? 0) > 0.5)
          .sort((a, b) => Math.abs(b.r ?? 0) - Math.abs(a.r ?? 0))
          .map(r => r.channelId),
      ].slice(0, 6),
      sharedGround: [], openQuestions: ['lag is the peak of the z-normalised cross-correlation over this window (Working.cross_channel); a shared-ground flag needs the montage, which is not registered yet'],
      yDomain: [lo, hi],
    },
    source: 'live',
  }
}

/** The motif member being edited, its revisions and the trace around it (§4.2) — still demo: span editing lands with Prompt 05. */
export const getSpanEdit = (memberId: string): Promise<Sourced<SpanEditDemo | null>> => demo(spanEditDemo(memberId))
