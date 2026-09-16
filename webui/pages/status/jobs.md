# Jobs — build status

| page | route | status | what's left | last commit |
|---|---|---|---|---|
| jobs.all | `#/jobs` | done | — | 431e079 |
| jobs.paused | `#/jobs/run/r-0431` · `#/jobs/run/a-0098` | done | — | 431e079 |
| jobs.upload | `#/jobs/run/r-0431/upload` | done | — | 431e079 |
| jobs.cluster | `#/jobs/cluster/j-0214` (also j-0217, j-0212, j-0209) | done | — | 431e079 |

Step 1 (inventory `pages/inventory/review-jobs.md` § jobs.*) written and committed before this run.

## Files owned

`webui/client/src/jobs/{index,AllPage,RunPage,UploadModal,ClusterPage,chrome}.tsx`, `jobs/{store.ts,jobs.css}`,
`webui/client/src/api/jobs.ts`, `webui/client/src/fixtures/jobs.ts`, `webui/smoke_pages/jobs.json`,
`webui/pages/{status,fog,requests}/jobs.md`, `webui/screenshots/build/jobs/`.

## States reachable by click and by deep link

- **jobs.all** `?filter=all|needs-you|paused|cluster|local|queues|finished` · `?ws=<workspace>` · `?sel=<id>`
  (rail: paused run / cluster job / local job / review queue / finished) · `?finished=1` (expand the collapsed
  group) · `?drawer=inbox` · `?modal=new-script&job=<id>` · `?modal=cancel&job=<id>` · `?kind=cluster` (the
  alias Models links in with).
- **jobs.paused** `?state=arrived|waiting` · `?modal=new-script` · `?modal=cancel`; *Continue* runs a `useSim`
  (queued → running per remaining stage → done); *Look again* flips the result to arrived; *Cancel run* →
  cancelled (with *Put it back to paused*). An unknown id renders a named empty state, not a blank.
- **jobs.upload** `?file=mismatch|ok|ok-no-nulls|held-out|none` · `?pop=file` (the file picker popover).
  The checks tick in one at a time; *Place file and continue* is disabled with a reason until every check
  passes, and placing continues the run.
- **jobs.cluster** `?modal=new-script` · `?inbox=pending` (a manifest arrives for this job). Marks
  (submitted / running / finished / failed), the 3×-estimate reminder and its snooze, the editable cluster job
  id, the profile select, *Copy* / *Save .sh* and the manifest inbox with *Import results* all write to the
  in-memory store and survive navigation.

## Cross-workspace contract

- Reads `useDemoWrites('jobs')` for `add-job` (Analyse chain-1g, Discovery, Models "Create SLURM script"):
  added jobs appear in the cluster group marked `new · this session` and open at `#/jobs/cluster/<id>` as
  *script created*.
- Writes `recordDemoWrite('jobs', …)` for `continue-run`, `cancel-run`, `mark-cluster-job`,
  `cancel-local-job`, `place-result`, and `add-job` (a new SLURM script created here).

## Gate

- `npx tsc --noEmit -p tsconfig.app.json` — clean for `src/jobs/**`, `src/api/jobs.ts`, `src/fixtures/jobs.ts`.
- `smoke.py --pages-only --only jobs` — 44 states, 0 failures, 0 browser console/page errors.
- Screenshots of every state next to the frames: `webui/screenshots/build/jobs/`.
