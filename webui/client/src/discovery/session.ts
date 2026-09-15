/* The Discovery session as every Discovery page sees it (P17: one session, one scope, one runs list).
 * Reads come through api/discovery.ts; writes (scope edits, added runs, picks, discards, status changes) live in
 * the in-memory demo store, so they survive moving between Runs · Seed search · Compare but not a reload. */
import { useEffect, useMemo } from 'react'
import { getRuns, getScoreboard, getSession, runEstimateMin, DISCOVERY_LIMIT_MIN, type DiscoveryRun, type RecordingOption, type ScoreRun } from '../api/discovery'
import { useSourced } from '../api/seam'
import { forceSim, getSim, useDemoState, useQueryState } from '../kit'

export interface ScopeState { name: string; saved: boolean; recording: string; channels: string[]; section: [number, number]; nullMethod: string; nullN: number }

export interface Discovery {
  loading: boolean; error: Error | null; reload: () => void; demo: boolean
  scope: ScopeState | null; recordings: RecordingOption[]; recording: RecordingOption | null
  setScope: (patch: Partial<ScopeState>) => void
  runs: DiscoveryRun[]; patchRun: (key: string, patch: Partial<DiscoveryRun>) => void; addRuns: (runs: DiscoveryRun[]) => void
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
  const [added, setAdded] = useDemoState<DiscoveryRun[]>('discovery.runs.added', () => [])
  const [patches, setPatches] = useDemoState<Record<string, Partial<DiscoveryRun>>>('discovery.runs.patch', () => ({}))
  const [picks, setPicks] = useDemoState<string[]>('discovery.picks', () => ['drop_motifs9'])
  const [stale, setStale] = useDemoState<boolean>('discovery.stale', () => false)
  const [chPageQ, setChPageQ] = useQueryState('chpage', '1')
  const [channelsQ, setChannelsQ] = useQueryState('channels', '')
  const [recordingQ] = useQueryState('recording', '')
  const [stateQ] = useQueryState('state', '')

  const fixtureScope: ScopeState | null = sess.data ? { name: sess.data.session.name, saved: true, recording: sess.data.session.recording, channels: sess.data.session.channels, section: sess.data.session.section, nullMethod: sess.data.session.null.method, nullN: sess.data.session.null.n } : null
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

  let runs: DiscoveryRun[] = (base.data ?? []).concat(added).map(r => patches[r.key] ? { ...r, ...patches[r.key] } : r)
  if (stateQ === 'empty') runs = runs.filter(r => r.kind === 'reference')
  if (stateQ === 'failed') runs = runs.map(r => r.key === 'seed_E0102_bank' ? { ...r, status: 'failed', error: 'MASS failed on CH7_B2 · scale bank length 63 s ran out of memory (simulated)' } : r)
  const patchRun = (key: string, patch: Partial<DiscoveryRun>) => setPatches(p => ({ ...p, [key]: { ...p[key], ...patch } }))
  const addRuns = (rs: DiscoveryRun[]) => setAdded(a => [...a, ...rs.filter(r => !a.some(x => x.key === r.key))])
  const togglePick = (key: string) => setPicks(picks.includes(key) ? picks.filter(k => k !== key) : picks.length < 2 ? [...picks, key] : [picks[0], key])

  // ?state=running: a template added in this session, running locally under the 20 min ceiling
  useEffect(() => {
    if (stateQ !== 'running' || !base.data) return
    if (!added.some(r => r.key === 'spike_shape_v1')) {
      setAdded(a => [...a, { key: 'spike_shape_v1', label: 'spike_shape_v1', kind: 'template', colour: '#5E7CE2', glyph: 'spike', detail: 'v1 · 3 stages', template: 'spike_shape_v1', status: 'running', perChannelMin: 2, addedThisSession: true }])
    }
    const id = 'discovery.run.spike_shape_v1'
    if (getSim(id).status === 'idle') forceSim(id, { status: 'running', steps: ['01 Gaussian shape', '02 Spike mark', '03 Band detect'], step: 1, fraction: 0.42, startedAt: Date.now() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateQ, base.data])

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

  return {
    loading: sess.loading || base.loading, error: sess.error ?? base.error ?? scoreRead.error, reload: () => { sess.reload(); base.reload(); scoreRead.reload() },
    demo: sess.source === 'demo' || base.source === 'demo',
    scope, recordings, recording, setScope,
    runs, patchRun, addRuns, picks, setPicks, togglePick, stale, setStale,
    pending, estimateMin, overLimit: estimateMin > DISCOVERY_LIMIT_MIN,
    chPage, setChPage: p => setChPageQ(String(p)), pageCount, visibleChannels,
    scores: scoreRead.data, foundOf, sectionH,
  }
}


