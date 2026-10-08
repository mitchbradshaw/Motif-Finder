/* jobs.all — `#/jobs`: one real board of the long work, in the order a researcher waits on it (fixup-jobs).
 *   1. In progress here — this bridge's own jobs, live from its job table (finished and failed behind a filter);
 *   2. Waiting on the cluster — every script the site wrote for the cluster, whatever wrote it, with its state and
 *      how its results come back;
 *   3. Waiting in review — the open review queues and how much is left to judge;
 *   plus the Manifest inbox in a drawer.
 * The fixture half (paused runs, hand-marked cluster jobs, a canon of invented ids) is gone: nothing on this page is
 * drawn from anything but the bridge. Deep links: `?section=local|cluster|review` (and the older `?kind=cluster`,
 * `?filter=queues|local`) scroll to a section; `?drawer=inbox` opens the inbox. */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button, Chip, Drawer, PageTitle, Page, useQueryState } from '../kit'
import { getClusterJobs, getInboxAttempts, getLocalJobs, isActive } from '../api/jobs'
import { getQueues } from '../api/review'
import { Header } from '../shell/Header'
import { ClusterJobsCard, InboxLive, LocalJobsCard, ReviewQueuesCard, useImport, useLiveRead, useSeedImport } from './LiveJobs'

type Section = 'local' | 'cluster' | 'review'
const SECTION_ID: Record<Section, string> = { local: 'jobs-live-local', cluster: 'jobs-cluster', review: 'jobs-review' }

export function AllPage() {
  const [sectionQ, setSection] = useQueryState('section', '')
  const [kindAlias] = useQueryState('kind', '')              // Models links in as ?kind=cluster
  const [filterAlias] = useQueryState('filter', '')          // Review links in as ?filter=queues; older links said ?filter=local
  const [drawer, setDrawer] = useQueryState('drawer', '')
  const section: Section | null = sectionQ === 'local' || sectionQ === 'cluster' || sectionQ === 'review' ? sectionQ
    : kindAlias === 'cluster' ? 'cluster' : filterAlias === 'queues' ? 'review' : filterAlias === 'local' ? 'local' : null

  const [limit, setLimit] = useState(25)
  const [reloadKey, setReloadKey] = useState(0)
  const bump = useCallback(() => setReloadKey(k => k + 1), [])
  const local = useLiveRead(() => getLocalJobs(limit), [limit, reloadKey], d => (d?.some(isActive) ? 2000 : 8000))
  const cluster = useLiveRead(getClusterJobs, [reloadKey], d => (d?.jobs.some(j => j.state === 'importing') ? 1500 : 10000))
  const queues = useLiveRead(getQueues, [reloadKey], () => 15000)
  const attempts = useLiveRead(getInboxAttempts, [reloadKey], () => 10000)
  const imp = useImport(bump)
  const seedImp = useSeedImport(bump)

  const running = local.data?.filter(isActive).length ?? 0
  const counts = cluster.data?.counts
  const reviewLeft = useMemo(() => (queues.data ?? []).reduce((n, q) => n + Math.max(0, q.total - q.judged), 0), [queues.data])
  const nQueues = queues.data?.length ?? 0
  const loaded = !!(local.data || local.error) && !!(cluster.data || cluster.error) && !!(queues.data || queues.error)

  // a deep link scrolls to its section once the cards exist
  useEffect(() => {
    if (!section || !loaded) return
    const el = document.getElementById(SECTION_ID[section])
    if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [section, loaded])
  const go = (s: Section) => { setSection(s); document.getElementById(SECTION_ID[s])?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }

  const subtitle = [
    `${running} in progress here`,
    counts ? `${counts.waiting} waiting on the cluster` : 'cluster: reading…',
    counts && counts.to_import ? `${counts.to_import} back to import` : null,
    queues.data ? `${reviewLeft} to judge in ${nQueues} queue${nQueues === 1 ? '' : 's'}` : 'review: reading…',
  ].filter(Boolean).join(' · ')

  return (
    <>
      <Header workspace="Jobs" page="All jobs" subtitle={subtitle} search="Search jobs, scripts, queues" />
      <Page maxWidth={1420}>
        <PageTitle title="Jobs"
          actions={<Button icon="inbox" testid="open-inbox" onClick={() => setDrawer('inbox')}>Manifest inbox · import results</Button>}>
          <Chip tone={running ? 'blue' : 'grey'} dot={running ? 'var(--blue)' : undefined} testid="chip-local" onClick={() => go('local')} title="this bridge's jobs, live">{running} in progress here</Chip>
          <Chip tone={counts?.waiting ? 'purple' : 'grey'} testid="chip-cluster" onClick={() => go('cluster')} title="scripts the site wrote whose results are not back yet">{counts ? counts.waiting : '…'} waiting on the cluster</Chip>
          <Chip tone={counts?.to_import ? 'amber' : 'grey'} dot={counts?.to_import ? 'var(--amber)' : undefined} testid="chip-to-import" onClick={() => go('cluster')} title="results copied back and not imported yet">{counts ? counts.to_import : '…'} results to import</Chip>
          <Chip tone={reviewLeft ? 'amber' : 'grey'} dot={reviewLeft ? 'var(--amber)' : undefined} testid="chip-review" onClick={() => go('review')} title="unjudged items across the open review queues">{queues.data ? reviewLeft : '…'} to judge · {nQueues} queue{nQueues === 1 ? '' : 's'}</Chip>
        </PageTitle>

        <div className="jb-live-stack" data-testid="jobs-live">
          <LocalJobsCard q={local} limit={limit} onMore={() => setLimit(l => l + 100)} />
          <ClusterJobsCard q={cluster} imp={imp} seedImp={seedImp} />
          <ReviewQueuesCard q={queues} />
        </div>

        <Drawer open={drawer === 'inbox'} onClose={() => setDrawer(null)} title="Manifest inbox" side="right" width={520} testid="inbox-drawer"
          subtitle="hand it a job folder the cluster's results were copied back into">
          <InboxLive imp={imp} cluster={cluster.data} attempts={attempts} />
        </Drawer>
      </Page>
    </>
  )
}
