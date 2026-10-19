/* Helpers shared by the inspector and the cluster page: previous-verdict lines, the queue-end view, loading/not-found. */
import type { ReactNode } from 'react'
import { navigate, setQuery } from '../state'
import { Button, EmptyState, fmtInt } from '../kit'
import type { QueueData } from '../api/review'
import { Shell, useBlind } from './Shell'
import { currentUnit, relTime, unitHash } from './queue'
import { useRecords, useStack, writeLabel, type SessionWrite } from './store'
import type { PreviousLine } from './parts'

export function previousLines(data: QueueData, stack: SessionWrite[], now: number): PreviousLine[] {
  const q = data.queue.id
  const live = stack.filter(w => w.queueId === q && !w.undone && w.kind !== 'tags').reverse()
  const out: PreviousLine[] = live.map(w => ({
    text: `${writeLabel(w)} · ${relTime(w.at, now)}`,
    go: () => navigate(w.kind === 'batch' ? `review/queue/${q}/cluster/${w.clusterNo}` : `review/queue/${q}/${w.items[0]}`),
  }))
  if (data.queue.previousLine) {
    const id = data.queue.previousLine.split(' · ')[0]
    const row = data.rows.find(r => r.id === id)
    out.push({ text: data.queue.previousLine, go: row ? () => navigate(`review/queue/${q}/${id}`) : undefined })
  }
  return out
}

/** Frame-less states of a queue: every item judged (?state=empty, or ?state=exhausted with no unjudged unit left),
 *  a queue that holds no items at all, or no unjudged unit after the one the researcher stepped from.
 *  night-a: the live end of every queue read "No more items in the demo fixture" (fixture words), and "Pick another
 *  queue" went to the fixture queue q-12; it now opens the queue picker of the queue on screen. */
export function QueueEndView({ data, forced }: { data: QueueData; forced: boolean }) {
  const [blind, setBlind] = useBlind(data.queue.id, data.queue.blind)
  const records = useRecords()
  useStack()
  const q = data.queue
  const cur = currentUnit(data, records)
  const pick = <Button onClick={() => setQuery({ pop: 'queues' })} testid="pick-another-queue">Pick another queue</Button>
  const toRun = q.runId ? <Button variant="link" iconRight="arrow-right" onClick={() => navigate(`discovery/runs?run=${q.runId}`)}>Open run in Discovery</Button> : null
  const body = q.total === 0 && !forced
    ? <EmptyState icon="inbox" title={`Queue ${q.title} holds no items`} bordered testid="queue-no-items"
        caption="The source it was made from sent nothing to judge (or every item is a held-out recording's). Make a new queue where the items come from."
        action={<div className="row">{toRun}{pick}</div>} />
    : forced || !cur
      ? <EmptyState icon="check-circle" title={`Queue ${q.runId ?? q.title} is done`} bordered testid={forced ? 'queue-empty' : 'queue-done'}
          caption={`${fmtInt(q.total)} of ${fmtInt(q.total)} judged · ${q.runId ? "return to Discovery to refresh the run's score" : 'the source can send more items'}`}
          action={<div className="row">{toRun}{pick}</div>} />
      : <EmptyState icon="inbox" title="No unjudged item after this one" bordered testid="queue-exhausted"
          caption={`${fmtInt(q.total - q.judged)} of ${fmtInt(q.total)} in ${q.title} are still unjudged, earlier in the queue`}
          action={<div className="row"><Button onClick={() => navigate(unitHash(q.id, cur))}>Open {cur.kind === 'item' ? cur.id : `Cluster ${cur.no}`}</Button>
            <Button onClick={() => navigate(`review/queue/${q.id}?rail=queue`)} testid="open-queue-rail">Open the queue rail</Button></div>} />
  return (
    <Shell data={data} unit={null} blind={blind} setBlind={setBlind} micro={[]} evidenceTitle="no item" evidence={<EmptyState size="sm" title="Nothing selected" caption="the queue has no current item" />} forceDone={forced}>
      {body}
    </Shell>
  )
}

export function NotFound({ data, what }: { data: QueueData; what: string }) {
  const [blind, setBlind] = useBlind(data.queue.id, data.queue.blind)
  return (
    <Shell data={data} unit={null} blind={blind} setBlind={setBlind} micro={[]} evidenceTitle="—" evidence={<EmptyState size="sm" title="Nothing selected" />}>
      <EmptyState icon="alert-circle" title={`No ${what} in queue ${data.queue.id}`} bordered testid="item-not-found"
        caption={`${data.queue.title} does not contain ${what}`} action={<Button onClick={() => navigate(`review/queue/${data.queue.id}`)} testid="go-current">Go to the current item</Button>} />
    </Shell>
  )
}

export function Loading({ children }: { children?: ReactNode }) {
  return <div className="rv-loading" data-testid="review-loading">{children}<div className="skeleton" style={{ height: 36, width: 420 }} /><div className="skeleton" style={{ height: 240 }} /><div className="skeleton" style={{ height: 190 }} /><div className="skeleton" style={{ height: 110 }} /></div>
}
