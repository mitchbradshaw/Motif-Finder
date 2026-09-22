/* The Discovery session as every Discovery page sees it (P17: one session, one scope, one runs list).
 * Reads come through api/discovery.ts; writes (scope edits, added runs, picks, discards, status changes) live in
 * the in-memory demo store, so they survive moving between Runs · Seed search · Compare but not a reload. */
import { useEffect, useMemo } from 'react'
import { getRuns, getScoreboard, getSession, runEstimateMin, DISCOVERY_LIMIT_MIN, type DiscoveryRun, type RecordingOption, type ScoreRun } from '../api/discovery'
import { useSourced } from '../api/seam'
import { useDemoState, useQueryState } from '../kit'
import { applyDiscoveryTemplates } from '../api'

/** The template `?state=running` applies. `mp_threshold` is the cheapest of the
 *  nine canonical detection templates on a short span. */
const RUNNING_LINK_TEMPLATE = 'mp_threshold'

/** `nullMethod` is null when Settings › Nulls names a method `preprocessing.surrogate` does not implement:
 *  the pairing is off, and `nullReason` is the server's account of why. A chip that printed a method and a
 *  draw count anyway would claim a null nothing ran. */
export interface ScopeState {
  name: string; saved: boolean; recording: string; channels: string[]; section: [number, number]
  nullMethod: string | null; nullN: number; nullRequested: string | null; nullReason: string | null
}

export interface Discovery {
  /** true while any read is in flight, whether or not there is already data on screen. */
  loading: boolean
  /** No data yet: show the big loading card. */
  firstLoad: boolean
  /** Data in hand and a read in flight: show a quiet in-place indicator that does not
   *  change the layout height. The 2 s poll below made the difference matter -- a 600 px
   *  card inserted above live content shoved the page down and back every two seconds
   *  for the whole life of a run (fixup-a item 4). */
  refreshing: boolean
  error: Error | null; reload: () => void; demo: boolean
  scope: ScopeState | null; recordings: RecordingOption[]; recording: RecordingOption | null
  setScope: (patch: Partial<ScopeState>) => void
  runs: DiscoveryRun[]; patchRun: (key: string, patch: Partial<DiscoveryRun>) => void
  picks: string[]; setPicks: (p: string[]) => void; togglePick: (key: string) => void
  stale: boolean; setStale: (v: boolean) => void
  pending: DiscoveryRun[]; estimateMin: number; overLimit: boolean
  chPage: number; setChPage: (p: number) => void; pageCount: number; visibleChannels: string[]
  scores: ScoreRun[] | null; foundOf: (key: string) => number | null
  sectionH: number
}

export const PAGE_SIZE = 3
export const hasResults = (r: DiscoveryRun) => r.status === 'done'
export const pickable = (r: DiscoveryRun) => r.status === 'done' || r.status === 'reference' || r.status === 'on cluster' || r.status === 'running'

export function useDiscovery(): Discovery {
  const sess = useSourced(getSession, [])
  const base = useSourced(getRuns, [])
  const [scopeStore, setScopeStore] = useDemoState<ScopeState | null>('discovery.scope', () => null)
  /* There is no client-side list of added runs any more. Everything that used
   * to append one — *Add and run*, the History popover — is a write now, and
   * the row comes back from /runs. A key this store had invented went out in
   * `runs=` on /fires and /scoreboard, which know only the keys the table
   * holds; the store survived a page reload, so the 404 outlived the session
   * that caused it. */
  const [patches, setPatches] = useDemoState<Record<string, Partial<DiscoveryRun>>>('discovery.runs.patch', () => ({}))
  // nothing is picked until the researcher picks it: the old default named a
  // fixture run (`drop_motifs9`) that no live session has
  const [picks, setPicks] = useDemoState<string[]>('discovery.picks', () => [])
  const [stale, setStale] = useDemoState<boolean>('discovery.stale', () => false)
  const [chPageQ, setChPageQ] = useQueryState('chpage', '1')
  const [channelsQ, setChannelsQ] = useQueryState('channels', '')
  const [recordingQ] = useQueryState('recording', '')
  const [stateQ] = useQueryState('state', '')

  const fixtureScope: ScopeState | null = sess.data ? { name: sess.data.session.name, saved: true, recording: sess.data.session.recording, channels: sess.data.session.channels, section: sess.data.session.section, nullMethod: sess.data.session.null.method, nullN: sess.data.session.null.n, nullRequested: sess.data.session.null.requested ?? null, nullReason: sess.data.session.null.reason ?? null } : null
  const scope0 = scopeStore ?? fixtureScope
  const recordings = sess.data?.recordings ?? []
  // deep links: ?channels=a,b,c and ?recording=<key> seed the scope
  const scope: ScopeState | null = scope0 && (channelsQ || recordingQ) ? {
    ...scope0,
    recording: recordingQ || scope0.recording,
    channels: channelsQ ? channelsQ.split(',').filter(Boolean) : scope0.channels,
  } : scope0
  const recording = recordings.find(r => r.key === scope?.recording) ?? null

  const setScope = (patch: Partial<ScopeState>) => {
    if (!scope) return
    setScopeStore({ ...scope, ...patch })
    if (channelsQ && (patch.channels || patch.recording)) setChannelsQ(null)
  }

  let runs: DiscoveryRun[] = (base.data ?? []).map(r => patches[r.key] ? { ...r, ...patches[r.key] } : r)
  if (stateQ === 'empty') runs = runs.filter(r => r.kind === 'reference')
  /* The three deep-link states name the session's FIRST real run rather than a
   * fixture key: `drop_motifs9` and `seed_E0102_bank` were inventions and no
   * live session has them, so the state silently did nothing. `discarded` is
   * the end state the Discard confirm reaches by click; `failed` is a display
   * of the failed row and says so in its own text, because a real failure
   * cannot be provoked from a URL. */
  const firstReal = runs.find(r => r.kind !== 'reference')?.key
  if (stateQ === 'discarded' && firstReal) runs = runs.map(r => r.key === firstReal ? { ...r, status: 'superseded' as const } : r)
  if (stateQ === 'failed' && firstReal) runs = runs.map(r => r.key === firstReal
    ? { ...r, status: 'failed' as const, error: 'shown by the ?state=failed deep link — not a real failure; a real one carries the run’s traceback' }
    : r)
  const patchRun = (key: string, patch: Partial<DiscoveryRun>) => setPatches(p => ({ ...p, [key]: { ...p[key], ...patch } }))
  const togglePick = (key: string) => setPicks(picks.includes(key) ? picks.filter(k => k !== key) : picks.length < 2 ? [...picks, key] : [picks[0], key])

  /* ?state=running starts a REAL run over the first fifteen minutes of the
   * section — short enough to finish while you look at it, long enough to have
   * a progress bar. The old version added a run that did not exist
   * (`spike_shape_v1`) and drove a simulated progress bar at a fixed 42 %,
   * which is the sort of picture this wiring exists to remove. It runs once per
   * page load and the toolbar says where the run came from. */
  const [startedByLink, setStartedByLink] = useDemoState<boolean>('discovery.state.running', () => false)
  useEffect(() => {
    if (stateQ !== 'running' || !scope || startedByLink) return
    setStartedByLink(true)
    const t0 = scope.section[0]
    const t1 = Math.min(scope.section[1], t0 + 0.25)
    applyDiscoveryTemplates([RUNNING_LINK_TEMPLATE], scope.channels, t0, t1)
      .then(() => base.reload())
      .catch(e => console.error('?state=running could not start a run', e))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ, scope?.recording, scope?.channels.join(','), startedByLink])

  /* A run that is running is a moving number: its progress, its channels-done
   * and, when it finishes, its detection count all change on the server with
   * no event this page is subscribed to. Re-read the runs while any of them is
   * running, and stop the moment none is — an idle Discovery page makes no
   * requests. The scores follow on the transition to done, because `doneKeys`
   * changes and `useSourced` re-runs. */
  const anyRunning = runs.some(r => r.status === 'running' || r.status === 'queued')
  useEffect(() => {
    if (!anyRunning) return
    const t = setInterval(() => base.reload(), 2000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anyRunning])

  const sectionH = scope ? scope.section[1] - scope.section[0] : 0
  const nCh = scope?.channels.length ?? 0
  const pending = runs.filter(r => r.status === 'new' || r.status === 'failed')
  const estimateMin = pending.reduce((s, r) => s + runEstimateMin(r.perChannelMin ?? 0, nCh, sectionH), 0)
  const pageCount = Math.max(1, Math.ceil(nCh / PAGE_SIZE))
  const chPage = Math.min(pageCount, Math.max(1, parseInt(chPageQ, 10) || 1))
  const visibleChannels = scope ? scope.channels.slice((chPage - 1) * PAGE_SIZE, chPage * PAGE_SIZE) : []

  const doneKeys = runs.filter(hasResults).map(r => r.key)
  const scoreRead = useSourced(() => scope ? getScoreboard(doneKeys, scope.channels, scope.section) : Promise.resolve({ data: [] as ScoreRun[], source: 'demo' as const }),
    [doneKeys.join(','), scope?.channels.join(','), scope?.section.join(',')])
  const foundOf = useMemo(() => (key: string) => scoreRead.data?.find(s => s.run === key)?.total.found ?? null, [scoreRead.data])

  const loading = sess.loading || base.loading
  const firstLoad = loading && (sess.data === null || base.data === null)
  return {
    loading, firstLoad, refreshing: loading && !firstLoad,
    error: sess.error ?? base.error ?? scoreRead.error, reload: () => { sess.reload(); base.reload(); scoreRead.reload() },
    demo: sess.source === 'demo' || base.source === 'demo',
    scope, recordings, recording, setScope,
    runs, patchRun, picks, setPicks, togglePick, stale, setStale,
    pending, estimateMin, overLimit: estimateMin > DISCOVERY_LIMIT_MIN,
    chPage, setChPage: p => setChPageQ(String(p)), pageCount, visibleChannels,
    scores: scoreRead.data, foundOf, sectionH,
  }
}


