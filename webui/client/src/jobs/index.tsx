/* Jobs workspace entry — one page (fixup-jobs). Route: `#/jobs` (`?section=local|cluster|review`, `?drawer=inbox`).
 * The fixture sub-pages (`jobs/run/<id>`, `jobs/run/<id>/upload`, `jobs/cluster/<id>`) are gone with the demo half;
 * an old link to one lands on the board, told why. */
import './jobs.css'
import { Button, EmptyState, Page } from '../kit'
import { navigate, useApp } from '../state'
import { Header } from '../shell/Header'
import { AllPage } from './AllPage'

export function JobsPage() {
  const { route } = useApp()
  const p = route.parts
  if (!p.length) return <AllPage />
  const old = p[0] === 'run' || p[0] === 'cluster'
  return (
    <>
      <Header workspace="Jobs" page="Not found" subtitle={`#/jobs/${p.join('/')}`} search="Search jobs, scripts, queues" />
      <Page maxWidth={1420}>
        <EmptyState bordered icon="alert-triangle" testid="jobs-unknown-route" title={old ? 'Jobs is one page now' : `No Jobs page at “/${p.join('/')}”`}
          caption={old
            ? 'the paused-run and cluster-job pages were fixture shells; every job the site wrote for the cluster is a row under “Waiting on the cluster” on the board'
            : 'Jobs has one page: what is in progress here, what waits on the cluster, what waits in review'}
          action={<Button variant="primary" onClick={() => navigate(old && p[0] === 'cluster' ? 'jobs?section=cluster' : 'jobs')}>Open the board</Button>} />
      </Page>
    </>
  )
}
