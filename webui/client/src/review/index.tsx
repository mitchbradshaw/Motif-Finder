/* Review workspace entry (spec §10). Routes:
 *   #/review                              → the last queue's current unit (default q-12, c-0343)
 *   #/review/queue/<q>                    → that queue's current unit (item or cluster); ?state=empty|exhausted renders the queue end
 *   #/review/queue/<q>/<itemId>           → review.inspector (blind queues q-18/q-19 are a state of it)
 *   #/review/queue/<q>/cluster/<n>        → review.cluster
 *   #/review/cluster/<n>                  → alias, redirects under its queue */
import { useEffect } from 'react'
import { Header } from '../shell/Header'
import { useApp } from '../state'
import { EmptyState, Button, useDemoState } from '../kit'
import { useSourced } from '../api/seam'
import { clusterQueue, getQueue, getQueues } from '../api/review'
import { navigate } from '../state'
import { Inspector } from './Inspector'
import { ClusterPage } from './ClusterView'
import { Loading, QueueEndView } from './common'
import { currentUnit, replaceHash, unitHash } from './queue'
import { useRecords, useReviewVersion } from './store'
import './review.css'

const qs = (query: Record<string, string>) => { const s = Object.entries(query).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&'); return s ? `?${s}` : '' }

export function ReviewPage() {
  const { route } = useApp()
  const p = route.parts
  // The remembered queue is a CONVENIENCE, never the source of truth. It used to
  // default to the fixture id `q-12` and was persisted, so on live data the
  // landing 404'd and — because the id is sticky — every later visit 404'd too.
  // It is now validated against the queues the bridge actually serves, and an
  // unknown one is forgotten rather than followed.
  const [lastQueue, setLastQueue] = useDemoState<string | null>('review.lastQueue', () => null)
  const queues = useSourced(getQueues, [])
  const live = queues.data ?? null
  const landing = live && live.length
    ? (live.some(q => q.id === lastQueue) ? (lastQueue as string) : live[0].id)
    : null
  const aliasNo = p[0] === 'cluster' ? Number(p[1]) : null
  const aliasQueue = aliasNo != null ? clusterQueue(aliasNo) : null
  useEffect(() => {
    if (!p[0]) { if (landing) replaceHash(`review/queue/${landing}${qs(route.query)}`) }
    else if (aliasNo != null && aliasQueue) replaceHash(`review/queue/${aliasQueue}/cluster/${aliasNo}${qs(route.query)}`)
  }, [p[0], aliasNo, aliasQueue, landing, route.query])   // eslint-disable-line react-hooks/exhaustive-deps
  const queueId = p[0] === 'queue' ? p[1] : null
  useEffect(() => { if (queueId) setLastQueue(queueId) }, [queueId, setLastQueue])

  if (aliasNo != null && !aliasQueue) return <Unknown text={`No cluster ${p[1]} in any review queue`} live={live} />
  if (queues.error) return <><Header workspace="Review" page="Inspector" /><div className="rv-root"><div className="error-card" data-testid="queues-error"><h3>The review queues failed to load</h3><p className="mono">{queues.error.message}</p></div></div></>
  if (!queueId && !queues.loading && live && live.length === 0) return <Unknown text="There are no review queues yet" caption="A queue is made from a Discovery run, a seeded search, an Explore selection, a window set, or Library's extract-events flag." live={live} />
  if (!queueId) return <><Header workspace="Review" page="Inspector" subtitle="opening the queue…" /><div className="rv-root"><Loading /></div></>
  return <QueueRoute queueId={queueId} rest={p.slice(2)} />
}

function QueueRoute({ queueId, rest }: { queueId: string; rest: string[] }) {
  const { route } = useApp()
  // `version` is bumped by every ACCEPTED write, so the queue is re-read from the database rather than
  // left to the session's guess about what the write did to the counts and the judged set
  const version = useReviewVersion()
  const data = useSourced(() => getQueue(queueId), [queueId, version])
  const records = useRecords()
  const d = data.data && data.data.queue.id === queueId ? data.data : null
  const state = route.query.state
  const cur = d ? currentUnit(d, records) : null
  const needsRedirect = !!d && rest.length === 0 && state !== 'empty' && state !== 'exhausted'
  useEffect(() => {
    if (!needsRedirect || !d) return
    const { state: _s, ...query } = route.query
    if (cur) replaceHash(`${unitHash(queueId, cur)}${qs(query)}`)
    else replaceHash(`review/queue/${queueId}${qs({ ...query, state: 'exhausted' })}`)
  }, [needsRedirect, cur?.kind, queueId])   // eslint-disable-line react-hooks/exhaustive-deps

  if (data.error) return <><Header workspace="Review" page="Inspector" /><div className="rv-root"><div className="error-card" data-testid="queue-error"><h3>Queue {queueId} failed to load</h3><p className="mono">{data.error.message}</p></div></div></>
  if (!data.loading && data.data === null) return <UnknownQueue queueId={queueId} />
  if (!d || needsRedirect) return <><Header workspace="Review" page="Inspector" subtitle={`queue ${queueId}`} /><div className="rv-root"><Loading /></div></>
  if (rest.length === 0) return <QueueEndView data={d} forced={state === 'empty'} />
  if (rest[0] === 'cluster') return <ClusterPage data={d} no={Number(rest[1])} />
  return <Inspector data={d} itemId={rest[0]} />
}

function UnknownQueue({ queueId }: { queueId: string }) {
  const qs = useSourced(getQueues, [])
  return <Unknown text={`No review queue called ${queueId}`} live={qs.data ?? null}
    caption={qs.data ? `queues: ${qs.data.map(q => `${q.id} ${q.title}`).join(' · ')}` : undefined} />
}

function Unknown({ text, caption, live }: { text: string; caption?: string; live?: { id: string; title: string }[] | null }) {
  // The way out has to be a queue that EXISTS. It used to be the fixture id, so
  // the only escape from "no such queue" was back to the same missing queue.
  const first = live && live.length ? live[0] : null
  return (
    <>
      <Header workspace="Review" page="Inspector" />
      <div className="rv-root"><div style={{ padding: 20 }}>
        <EmptyState icon="alert-circle" title={text} caption={caption} bordered testid="review-unknown"
          action={first ? <Button onClick={() => navigate(`review/queue/${first.id}`)}>Open {first.title}</Button> : undefined} />
      </div></div>
    </>
  )
}
