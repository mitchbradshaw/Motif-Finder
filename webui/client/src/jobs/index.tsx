/* Jobs workspace entry — owned by the Jobs builder (spec §7c, P24).
 * Routes: `#/jobs` · `#/jobs/run/<id>` · `#/jobs/run/<id>/upload` · `#/jobs/cluster/<id>`. */
import './jobs.css'
import { Button, EmptyState, Page } from '../kit'
import { navigate, useApp } from '../state'
import { Header } from '../shell/Header'
import { AllPage } from './AllPage'
import { RunPage } from './RunPage'
import { ClusterPage } from './ClusterPage'
import { BackToAll } from './chrome'

export function JobsPage() {
  const { route } = useApp()
  const p = route.parts
  if (p[0] === 'run' && p[1]) return <RunPage runId={p[1]} upload={p[2] === 'upload'} />
  if (p[0] === 'cluster' && p[1]) return <ClusterPage jobId={p[1]} />
  if (!p.length) return <AllPage />
  return (
    <>
      <Header workspace="Jobs" page="Not found" subtitle={`#/jobs/${p.join('/')}`} search="Search jobs, runs, queues" />
      <Page maxWidth={1420}>
        <BackToAll />
        <EmptyState bordered icon="alert-triangle" testid="jobs-unknown-route" title={`No Jobs page at “/${p.join('/')}”`}
          caption="Jobs has four: all jobs, a paused run, its upload modal and a cluster job."
          action={<Button variant="primary" onClick={() => navigate('jobs')}>All jobs</Button>} />
      </Page>
    </>
  )
}
