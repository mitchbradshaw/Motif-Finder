/* The Discovery session as every Discovery page sees it (P17: one session, one scope, one runs list).
 * Reads come through api/discovery.ts; writes (scope edits, added runs, picks, discards, status changes) live in
 * the in-memory demo store, so they survive moving between Runs · Seed search · Compare but not a reload. */
import { useEffect, useMemo } from 'react'
import { getRuns, getScoreboard, getSession, isHeldOut, putScope, runEstimateMin, DISCOVERY_LIMIT_MIN, type DiscoveryRun, type RecordingOption, type ScoreRun } from '../api/discovery'
import { useSourced } from '../api/seam'
import { useDemoState, useQueryState } from '../kit'
import { applyDiscoveryTemplates } from '../api'
import { useToast } from '../shell/Toast'
import { resolveScopeLink, scopeFromSession } from './scopeLink'
import { scoreKey, scoresFor, type KeyedScores } from './scoreRead'

/** The template `?state=running` applies. `mp_threshold` is the cheapest of the
 *  nine canonical detection templates on a short span. */
const RUNNING_LINK_TEMPLATE = 'mp_threshold'

/** `nullMethod` is null when Settings › Nulls names a method `preprocessing.surrogate` does not implement:
 *  the pairing is off, and `nullReason` is the server's account of why. A chip that printed a method and a
 *  draw count anyway would claim a null nothing ran. */
export interface ScopeState {
  name: string; saved: boolean; recording: string; channels: string[]; section: [number, number]
  nullMethod: string | null; nullN: number; nullRequested: string | null; nullReason: string | null
  /** fixup-T: `nullN` is the SEED SEARCH's draw count; a template run has its own (Q35: 20 against 200).
   *  `nullExplicit` is true when the session's null was set on the session rather than read from Settings. */
  nullTemplateN: number; nullTemplateMethod: string | null; nullExplicit: boolean
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
  resetScope: () => void
  /** site-runs: a deep link (`?recording=` + `?channels=`) being written to the session — hold anything that would
   *  act on the scope (the Apply-template modal) until it lands. */
  linkPending: boolean
  /** site-runs: why a deep link was refused (a name that is not a channel of the recording), in words; nothing was sent. */
  linkRefused: string | null
  clearLink: () => void
  runs: DiscoveryRun[]; patchRun: (key: string, patch: Partial<DiscoveryRun>) => void
  picks: string[]; setPicks: (p: string[]) => void; togglePick: (key: string) => void
  /** ux-1019: the runs drawn in "Where each run fires" — none on a new session, each turned on by its eye button;
   *  the human reference row is always drawn and is never in this list. */
  shown: string[]; isShown: (r: DiscoveryRun) => boolean; toggleShown: (key: string) => void; setShown: (keys: string[]) => void
  stale: boolean; setStale: (v: boolean) => void
  pending: DiscoveryRun[]; estimateMin: number; overLimit: boolean
  chPage: number; setChPage: (p: number) => void; pageCount: number; visibleChannels: string[]
  /** null until the scoreboard has answered for the runs and scope on screen (site-runs item 4) */
  scores: ScoreRun[] | null; scoresLoading: boolean; foundOf: (key: string) => number | null
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
  /* ux-1019 (the researcher, 2026-10-18): no run is drawn until its eye is pressed. Kept per session (by the
   * session's name), with the other demo-store keys: it survives moving between Discovery pages, not a reload. */
  const [shownBySession, setShownBySession] = useDemoState<Record<string, string[]>>('discovery.shown', () => ({}))
  const [stale, setStale] = useDemoState<boolean>('discovery.stale', () => false)
  const [chPageQ, setChPageQ] = useQueryState('chpage', '1')
  const [channelsQ, setChannelsQ] = useQueryState('channels', '')
  const [recordingQ, setRecordingQ] = useQueryState('recording', '')
  const [stateQ] = useQueryState('state', '')
  const toast = useToast()

  const fixtureScope: ScopeState | null = sess.data ? scopeFromSession(sess.data.session) : null
  const scope0 = scopeStore ?? fixtureScope
  const recordings = sess.data?.recordings ?? []
  /* site-runs item 5: a deep link that names channels (Cross-channel's *Apply a template across these N channels*:
   * `?recording=<key>&channels=<names>`) BECOMES the session's scope, through the Scope card's own `putScope`
   * write, and the query keys are cleared once it has landed — so a template is applied where the page says. A
   * name the recording does not have is refused in words and nothing is sent. A link with no channels
   * (`?recording=` alone, the held-out states) and a held-out recording stay a view, as before. */
  const link = scope0 && sess.data ? resolveScopeLink(recordingQ, channelsQ, scope0, recordings) : null
  const linkRefused = link && 'refused' in link ? link.refused : null
  const linkTarget = link && 'scope' in link ? link.scope : null
  const scope: ScopeState | null = !scope0 ? null
    : linkTarget ? { ...scope0, ...linkTarget }
      : linkRefused ? scope0
        : (channelsQ || recordingQ) ? {
          ...scope0,
          recording: recordingQ || scope0.recording,
          channels: channelsQ ? channelsQ.split(',').filter(Boolean) : scope0.channels,
        } : scope0
  const clearLinkKeys = () => { setChannelsQ(null); setRecordingQ(null) }
  const linkKey = linkTarget ? `${linkTarget.recording}|${linkTarget.channels.join(',')}|${linkTarget.section.join(',')}` : ''
  useEffect(() => {
    if (!link || !('scope' in link)) return
    if (link.same) { clearLinkKeys(); return }
    let alive = true
    putScope(link.scope)
      .then(p => { if (!alive) return; setScopeStore(scopeFromSession(p.session)); clearLinkKeys(); sess.reload(); base.reload() })
      .catch(e => {
        console.error('the linked scope could not be written', e)
        toast.push({ text: `the link's scope was not applied · ${e instanceof Error ? e.message : String(e)}` })
      })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkKey])
  const recording = recordings.find(r => r.key === scope?.recording) ?? null

  /* The scope is the SERVER's (P17: one session, one scope). A changed recording, channel list or section is
   * written to the session row first and shown once the bridge has taken it. It used to live in this store
   * alone, so every read after a change of recording asked the old recording for the new one's channels —
   * "no channel(s) ['CH3', 'CH1', 'CH4'] on M2_aug_concat_fs1" — and the Seed page searched the section the
   * server still held while its run was started over the one on screen. A held-out recording is never
   * written: the scope card refuses it from the client's copy, as before. */
  const setScope = (patch: Partial<ScopeState>) => {
    if (!scope) return
    const next = { ...scope, ...patch }
    const clearLink = () => { if (channelsQ && (patch.channels || patch.recording)) setChannelsQ(null) }
    const moves = patch.recording !== undefined || patch.channels !== undefined || patch.section !== undefined
    if (!moves || isHeldOut(next.recording)) { setScopeStore(next); clearLink(); return }
    /* site-runs item 6: the scope shown is the bridge's ANSWER — a change of recording opens that recording's own
     * session, with its own name; merging the patch into this copy kept the old session's name on the toolbar */
    putScope({ recording: next.recording, channels: next.channels, section: next.section })
      .then(p => { setScopeStore(scopeFromSession(p.session)); clearLink(); sess.reload(); base.reload() })
      .catch(e => {
        console.error('the scope could not be changed', e)
        toast.push({ text: `the scope was not changed · ${e instanceof Error ? e.message : String(e)}` })
      })
  }
  /** Back to the scope the server holds (out of a held-out recording the card refused). */
  const resetScope = () => { setScopeStore(null); sess.reload(); base.reload() }

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
  const sessionKey = scope?.name ?? ''
  const shown = shownBySession[sessionKey] ?? []
  const setShown = (keys: string[]) => setShownBySession(m => ({ ...m, [sessionKey]: keys }))
  const toggleShown = (key: string) => setShown(shown.includes(key) ? shown.filter(k => k !== key) : [...shown, key])
  const isShown = (r: DiscoveryRun) => r.kind === 'reference' || shown.includes(r.key)
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
  /* site-runs item 4: an answer is tagged with the key it was read for (./scoreRead.ts), and no read goes out
   * before the runs are in — the empty first answer used to stand on screen as "no finished run" and "Send 0"
   * for the minutes the real read took. Until the answer for THESE runs lands, `scores` is null. */
  const wantKey = scope && base.data ? scoreKey(doneKeys, scope.channels, scope.section) : ''
  const scoreRead = useSourced<KeyedScores<ScoreRun> | null>(() => scope && base.data
    ? getScoreboard(doneKeys, scope.channels, scope.section).then(r => ({ ...r, data: { key: wantKey, rows: r.data } }))
    : Promise.resolve({ data: null, source: 'live' as const }),
    [wantKey])
  const scores = wantKey ? scoresFor(scoreRead.data, wantKey) : null
  const foundOf = useMemo(() => (key: string) => scores?.find(s => s.run === key)?.total.found ?? null, [scores])

  const loading = sess.loading || base.loading
  const firstLoad = loading && (sess.data === null || base.data === null)
  return {
    loading, firstLoad, refreshing: loading && !firstLoad,
    error: sess.error ?? base.error ?? scoreRead.error, reload: () => { sess.reload(); base.reload(); scoreRead.reload() },
    demo: sess.source === 'demo' || base.source === 'demo',
    scope, recordings, recording, setScope, resetScope,
    linkPending: !!linkTarget && !(link && 'same' in link && link.same), linkRefused, clearLink: clearLinkKeys,
    runs, patchRun, picks, setPicks, togglePick, shown, isShown, toggleShown, setShown, stale, setStale,
    pending, estimateMin, overLimit: estimateMin > DISCOVERY_LIMIT_MIN,
    chPage, setChPage: p => setChPageQ(String(p)), pageCount, visibleChannels,
    scores, scoresLoading: scoreRead.loading, foundOf, sectionH,
  }
}


