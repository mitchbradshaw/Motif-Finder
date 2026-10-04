/* Every plot is an index (fixup-ae; Q-L6 / Q-E6): a click on an Atlas card or a Recurrence cell opens that family's
 * members — or that cell's — IN PLACE, in H's slideshow (`kit/Slideshow.tsx`: real samples at their own times, a y
 * measured per card with a scale bar, the `[2 falls]` flag), with *Open family page →*. Nothing navigates away.
 *
 * The members are the family read's own (`GET /api/library/family/{id}`), so they are the members the Library's view
 * shows (the noise floor, fall duration, purity) with the hand edits applied, and each carries the verdict the one
 * resolver gave it and the rule that gave it. Each card's samples come from `/api/channels/{id}/window` — the
 * member's span with context either side, its own extent shaded. The slideshow writes nothing. */
import { useEffect, useMemo, useRef } from 'react'
import { Button, EmptyState, EventSlideshow, type SlideEvent, type SlideSort, type SlideTrace } from '../kit'
import { getWindow, type LibMember } from '../api'
import { getFamily, type Member } from '../api/library'
import { live, useSourced } from '../api/seam'
import { navigate } from '../state'
import { LoadFailed, Loading, fmtMv, useLibraryView } from './chrome'

type LiveMember = Member & LibMember

const SORTS: SlideSort[] = [
  { value: 'd', label: 'distance to medoid' },
  { value: 'depth', label: 'depth (largest first)', descending: true },
  { value: 'time', label: 'time' },
]

/** Context either side of a member: half its own width, and never under 5 s, so a 1-sample fall is not drawn
 *  edge to edge with nothing to read it against. */
const contextS = (startS: number, endS: number) => Math.max(5, 0.5 * Math.max(0, endS - startS))

export function memberSlides(members: LiveMember[]): SlideEvent[] {
  return members.filter(m => m.recordingId != null && m.startS != null && m.endS != null).map(m => {
    const pad = contextS(m.startS!, m.endS!)
    const verdict = m.verdict === 'unjudged' ? null : m.verdict
    const depth = m.depthMv == null ? 'depth not measured' : `${fmtMv(m.depthMv)} mV${m.depthSource && m.depthSource !== 'detector' ? ' (event shape)' : ''}`
    const fall = m.fallS == null ? '' : ` · fall ${m.fallS < 10 ? m.fallS.toFixed(1) : Math.round(m.fallS)} s`
    const floor = m.floorStatus === 'sub_floor' ? ' · under the floor' : m.floorStatus === 'unmeasured' ? ' · unmeasured' : ''
    return {
      id: m.id, title: `${m.id} · ${m.channel}`,
      band: [m.startS!, m.endS!], window: [Math.max(0, m.startS! - pad), m.endS! + pad],
      count: m.fallsInWindow ?? null, countOf: 'falls',
      facts: `${depth}${fall}${floor}${m.scaleBandLabel ? ` · band ${m.scaleBand} ${m.scaleBandLabel}` : ''}`,
      state: verdict ? { text: `${verdict} · by ${m.verdictBy ?? '—'}`, tone: verdict === 'interesting' || verdict === 'seed' ? 'green' : 'amber' } : { text: 'unjudged', tone: 'muted' },
      sort: { d: m.d, depth: m.depthMv ?? null, time: m.onsetH },
    } satisfies SlideEvent
  })
}

const load = (recordingId: number) => (e: SlideEvent): Promise<SlideTrace> => {
  const [t0, t1] = e.window!
  return getWindow(recordingId, t0, t1, 420).then(w => ({ t: w.envelope.t, v: w.envelope.v, decimated: w.envelope.decimated, nSource: w.envelope.n_source }))
}

/** One family's members (or one cell's: `cell = "recKey:channel"`), in place. */
export function FamilyMembersInPlace({ familyId, grouping, colour, cell, cellLabel, onClose, testid = 'members-in-place' }: {
  familyId: string; grouping?: string; colour?: string; cell?: string | null; cellLabel?: string; onClose?: () => void; testid?: string
}) {
  const [view] = useLibraryView()
  const fam = useSourced(() => (familyId ? getFamily(familyId, grouping, 'motifs', view) : live(Promise.resolve(null))), [familyId, grouping, view.floor, view.fallMin, view.fallMax, view.pure])
  const d = fam.data && fam.data.kind === 'motif' ? fam.data.detail : null
  const members = useMemo(() => {
    const all = (d?.members ?? []) as LiveMember[]
    if (!cell) return all
    const [rk, ch] = cell.split(':')
    return all.filter(m => m.recordingKey === rk && m.channel === ch)
  }, [d, cell])
  const slides = useMemo(() => memberSlides(members), [members])
  const byId = useMemo(() => new Map(members.map(m => [m.id, m])), [members])
  const loader = (e: SlideEvent) => { const m = byId.get(e.id); return m?.recordingId != null ? load(m.recordingId)(e) : Promise.reject(new Error('no recording for this member')) }
  const hidden = (d as (typeof d & { view?: { hiddenByView?: boolean; family?: { hidden: number } } }) | null)?.view
  const where = cell ? ` in ${cellLabel ?? cell}` : ''
  // the click is answered where it can be seen: a card far down the grid opens a panel the page scrolls to
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => { box.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' }) }, [familyId, cell])
  return (
    <div ref={box} className="k-card" style={{ padding: '12px 14px', scrollMarginTop: 12 }} data-testid={testid} data-family={familyId} data-cell={cell ?? ''}>
      <div className="row" style={{ marginBottom: 8, gap: 8 }}>
        <b style={{ fontSize: 13, color: colour }}>{familyId}</b>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{d ? `${members.length} member${members.length === 1 ? '' : 's'}${where}` : `members${where}`}</span>
        {!!hidden?.family?.hidden && <span className="lib-cap" data-testid={`${testid}-hidden`}>{hidden.family.hidden} hidden by the view</span>}
        <span style={{ marginLeft: 'auto' }} />
        <Button variant="primary" size="sm" iconRight="arrow-right" testid="open-family-page" onClick={() => navigate(`library/family/${familyId}`)}>Open family page</Button>
        {onClose && <Button variant="link" size="sm" testid={`${testid}-close`} onClick={onClose}>close</Button>}
      </div>
      {fam.error && <LoadFailed what={`the members of ${familyId}`} error={fam.error} onRetry={fam.reload} />}
      {fam.loading && <Loading height={180} testid={`${testid}-loading`} />}
      {fam.data && fam.data.kind !== 'motif' && <EmptyState title={`No family ${familyId}`} caption="not in this grouping" bordered size="sm" />}
      {d && hidden?.hiddenByView && <EmptyState title={`Every member of ${familyId} is hidden by the view`} caption="under the noise floor or outside the filters — turn the floor off (show sub-floor) to see them" bordered size="sm" testid={`${testid}-all-hidden`} />}
      {d && !hidden?.hiddenByView && !slides.length && <EmptyState title="No members to show" caption={cell ? 'this cell holds no member the view shows' : 'the view shows no member of this family'} bordered size="sm" testid={`${testid}-empty`} />}
      {d && slides.length > 0 && (
        <EventSlideshow testid={`${testid}-slideshow`} events={slides} load={loader} sorts={SORTS} selected={null} onSelect={() => undefined}
          cap={10} columns={5} colour={colour} unit="mV" title={`Each member${where}`} frameNote="the member's stored span (shaded) with context either side" />
      )}
    </div>
  )
}
