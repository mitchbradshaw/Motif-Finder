/* Explore demo reads (brief: every read goes through a typed async function returning Sourced<T>).
 * Corpus and Signal stay live against the bridge (src/api.ts); these reads only supply what the bridge does
 * not serve — tags, reviewed coverage, run methods and colours, adjudications, families, the drawer's filter
 * vocabularies — plus the two fixture pages (Cross-channel, Span edit). Each resolves `source: 'demo'`, so the
 * page that renders it passes `demo` to <Header>. A later ticket swaps a body for a bridge call. */
import { demo, type Sourced } from './seam'
import {
  CANON_CHANNELS, corpusDemo, crossDemo, HELD_OUT_REASON, SHORTCUTS, signalDemo, spanEditDemo,
  type CanonChannelRef, type CorpusDemo, type CrossDemo, type SignalDemo, type SpanEditDemo,
} from '../fixtures/explore'

export type {
  AnnotationRow, CorpusDemo, CrossDemo, DemoRun, DetectionRow, Revision, SignalDemo, SnapRule, SpanEditDemo, Verdict, XBin, XRow,
} from '../fixtures/explore'
export { FILTER_VOCAB, METHODS, RAIL_TAGS, VERDICT_KEYS } from '../fixtures/explore'
import { VERDICTS } from '../fixtures/canon'
/** Verdict colours from the shared canon (seed and interesting are both human → green, §3). */
export const VERDICT_COLOURS: Record<string, string> = Object.fromEntries(VERDICTS.map(v => [v.key, v.colour]))

/** Tags, reviewed coverage and the recording-wide run / method lists for the Corpus rail (no bridge endpoint: fog F2). */
export const getCorpusDemo = (file: string, channelNames: string[], bins: number): Promise<Sourced<CorpusDemo>> =>
  demo(corpusDemo(file, channelNames, bins))

/** Runs with methods and colours, adjudications, families, the drawer rows for the canon channel. `null` elsewhere. */
export const getSignalDemo = (channelId: number): Promise<Sourced<SignalDemo | null>> => demo(signalDemo(channelId), 30)

/** The keyboard map the Shortcuts tab renders (Settings › Keyboard owns editing it). */
export const getShortcuts = () => demo(SHORTCUTS, 10)

/** Canon channel lookup for the fixture pages: which recording a channel id belongs to, and whether it is held out. */
export interface ChannelLookup { channel: CanonChannelRef | null; heldOut: boolean; reason: string | null }
export const lookupChannel = (id: number): Promise<Sourced<ChannelLookup>> => {
  const channel = CANON_CHANNELS.find(c => c.id === id) ?? null
  const heldOut = channel?.recordingKey === 'M4_aug'
  return demo({ channel, heldOut, reason: heldOut ? HELD_OUT_REASON : null }, 20)
}

/** Lag, r and traces for one reference channel's window (fog F16: nothing computes these yet). */
export const getCrossChannel = (referenceId: number, padS = 20): Promise<Sourced<CrossDemo | null>> => demo(crossDemo(referenceId, padS))

/** The motif member being edited, its revisions and the trace around it (§4.2). */
export const getSpanEdit = (memberId: string): Promise<Sourced<SpanEditDemo | null>> => demo(spanEditDemo(memberId))
