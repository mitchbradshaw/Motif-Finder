/* Round A_2 · P3: *Apply template*'s window scope, beside Channels and Bands. Off is today's run over the whole section.
 * On, the section is cut into windows of the chosen length with an overlap (50 % recommended); each window is an
 * ordinary run of the template's chain, judged on its own scale, and the windows' detections are stitched into one
 * result with nothing counted twice (`Working/discovery/windowed.py`). The plan below is the bridge's: how many windows
 * each channel has, how many runs that is with the null, what it costs, and the shortest window this chain allows
 * (4 × its longest rolling window or baseline, or one whole piece of a block that cuts its input into pieces), named by
 * the step that sets it. Fitting the chain to a shorter window scales those windows down: a different chain, its own
 * row on the Map. Nothing here is computed in the browser. */
import { Checkbox, Dropdown, Icon, InfoTip, Seg, TextField, cx } from '../kit'
import { useSourced } from '../api/seam'
import { planRun, fmtMin } from '../api/discovery'
import type { DiscPlanWindows } from '../api'
import { LoadFailed, Loading } from './chrome'

export const WINDOW_LENGTHS: { value: string; label: string }[] = [
  { value: '600', label: '10 min' }, { value: '3600', label: '1 h' }, { value: '21600', label: '6 h' },
  { value: '43200', label: '12 h' }, { value: '86400', label: '24 h' }, { value: '259200', label: '72 h' },
  { value: '604800', label: '168 h' }, { value: 'custom', label: 'other…' },
]
export const WINDOW_OVERLAPS: { value: string; label: string }[] = [
  { value: '0', label: '0 %' }, { value: '0.25', label: '25 %' }, { value: '0.5', label: '50 % (recommended)' },
  { value: '0.75', label: '75 %' }, { value: '0.9', label: '90 %' },
]
export const TRADE_OFF = 'Each window sets its own thresholds: a quiet window finds weaker events than the whole-span run would, and a busy one finds fewer.'

const fmtLen = (s: number) => s < 3600 ? `${+(s / 60).toFixed(1)} min` : `${+(s / 3600).toFixed(1)} h`

export interface WindowScopeState {
  on: boolean; lengthS: number | null; overlap: number; fit: boolean; allowShort: boolean
}
/** The scope the apply and preview routes take, or null when off (or the length is not a number yet). */
export const windowScopeOf = (w: WindowScopeState) => (w.on && w.lengthS && w.lengthS > 0
  ? { window_s: w.lengthS, overlap_frac: w.overlap, fit: w.fit, ...(w.allowShort && !w.fit ? { allow_short: true } : {}) } : null)

export function WindowScope({ template, channels, section, state, mode, setMode, length, setLength, custom, setCustom, overlap, setOverlap, fit, setFit, allowShort, setAllowShort }: {
  template: string | null; channels: string[]; section: [number, number]; state: WindowScopeState
  mode: string; setMode: (v: string) => void; length: string; setLength: (v: string) => void
  custom: string; setCustom: (v: string) => void; overlap: string; setOverlap: (v: string) => void
  fit: boolean; setFit: (v: boolean) => void; allowShort: boolean; setAllowShort: (v: boolean) => void
}) {
  const scope = windowScopeOf(state)
  const key = scope ? `${template}|${channels.join(',')}|${section.join('-')}|${scope.window_s}|${scope.overlap_frac}|${scope.fit}|${'allow_short' in scope}` : 'off'
  const plan = useSourced(() => (scope && template
    ? planRun({ template, channels, t0: section[0], t1: section[1], windows: scope })
    : Promise.resolve({ data: null, source: 'live' as const })), [key])
  const w = plan.data?.windows ?? null
  return (
    <>
      <div className="dsc-sub-label row" style={{ gap: 6 }} data-testid="window-scope-head">
        Windows
        <InfoTip title="Window scope">With windows, the template's chain runs over sliding windows of the section instead of all of it at once. Each window is judged on its own scale — the noise level, cutlines and depth gates a detector fits to the span it is given are fitted to the window — and the windows' detections are stitched into one result: where windows overlap, an event counts once, decided by the window that sees it most centrally. Each window is an ordinary run, kept and reused when you apply the same scope again, with its own null. The result is one Discovery run, and its own row on the Map: each window length is its own version of the algorithm.</InfoTip>
        <span className="k-spacer" />
        <Seg size="sm" value={mode} onChange={setMode} testid="window-scope-mode"
          options={[{ value: 'off', label: 'off' }, { value: 'on', label: state.on && state.lengthS ? `${fmtLen(state.lengthS)} windows` : 'windows' }]} />
      </div>
      {mode === 'on' && (
        <div className="dsc-scope-channels" data-testid="window-scope">
          <div className="small muted" data-testid="window-tradeoff">{w?.tradeOff ?? TRADE_OFF}</div>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <Dropdown prefix="length" value={length} onChange={setLength} options={WINDOW_LENGTHS} size="sm" testid="window-length" />
            {length === 'custom' && <TextField value={custom} onChange={setCustom} placeholder="hours" suffix="h" size="sm" width={90} invalid={!state.lengthS} ariaLabel="window length in hours" testid="window-length-custom" />}
            <Dropdown prefix="overlap" value={overlap} onChange={setOverlap} options={WINDOW_OVERLAPS} size="sm" testid="window-overlap" />
          </div>
          <Checkbox checked={fit} onChange={setFit} testid="window-fit"
            label={<span className="small">fit the chain's internal windows to this window length <span className="muted">(a different chain: its own row on the Map)</span></span>} />
          <Checkbox checked={allowShort && !fit} onChange={setAllowShort} disabled={fit} disabledReason="fitting already makes the chain fit the window" testid="window-allow-short"
            label={<span className="small">or run it as it is in a shorter window <span className="muted">(its own windows overrun the edges; the run says so)</span></span>} />
          <div className="dsc-preview-card" data-testid="window-plan">
            {!template ? <div className="mono small muted">pick a template to see its windows</div>
              : !scope ? <div className="dsc-err">give the window a length in hours</div>
                : plan.error ? <LoadFailed what="the window plan" error={plan.error} onRetry={plan.reload} />
                  : plan.loading || !plan.data ? <Loading height={40} label="planning the windows" />
                    : !w ? <div className="mono small muted">the bridge sent no window plan</div>
                      : <>
                        <div className="row small" style={{ gap: 6 }}><Icon name="flask" size={12} /><b>{template}</b><span className="muted">in {w.label}</span></div>
                        <WindowPlan w={w} runnable={plan.data.runnable} reason={plan.data.reason} estimateS={plan.data.estimate_s} route={plan.data.route} ceilingS={plan.data.ceiling_s} channels={channels.length} />
                      </>}
          </div>
        </div>
      )}
    </>
  )
}

function WindowPlan({ w, runnable, reason, estimateS, route, ceilingS, channels }: {
  w: DiscPlanWindows; runnable: boolean; reason: string | null
  estimateS: number | null; route: string; ceilingS: number; channels: number
}) {
  const m = w.minimum
  return (
    <>
      {m && <div className="mono small" data-testid="window-minimum">
        shortest window this chain allows: <b>{fmtLen(m.minimum_s)}</b> — step {String(m.step + 1).padStart(2, '0')} {m.label} ({m.param}, {fmtLen(m.seconds)}{m.kind === 'context' ? ', × 4' : ', one whole piece'})
        <InfoTip title="Why a minimum">{m.kind === 'context'
          ? 'This step reads a stretch of signal around every point (a rolling mean, a baseline). Near a window’s edge it sees only half of it, so a window must be at least four times as long for its edges to distort a quarter of it at most.'
          : 'This step cuts its input into pieces of this length and treats each on its own, so a window must hold one whole piece; the window’s edge is then one more piece boundary.'}</InfoTip>
      </div>}
      {!runnable
        ? <div className="dsc-err" data-testid="window-refused">{reason ?? w.refused}</div>
        : <>
          <div className="mono small" data-testid="window-count">
            {w.per_channel.toLocaleString('en-US')} window{w.per_channel === 1 ? '' : 's'} per channel × {channels} channel{channels === 1 ? '' : 's'} = {w.targets.toLocaleString('en-US')} · {w.runs.toLocaleString('en-US')} run{w.runs === 1 ? '' : 's'} to make with the null{w.done ? ` · ${w.done.toLocaleString('en-US')} already run` : ''}
          </div>
          <div className={cx('mono small', route === 'cluster' ? 'amber' : 'muted')} data-testid="window-estimate">
            {estimateS != null ? `estimate ${fmtMin(estimateS / 60)}` : 'the blocks declare no estimate'} · at least {fmtMin(w.overhead_s / 60)} of run bookkeeping ({w.run_overhead_s} s a run)
            {' · '}{route === 'cluster' ? `over the ${Math.round(ceilingS / 60)} min local limit → create a SLURM script` : route === 'local' ? 'runs here' : 'cost unknown — runs here; Preview on a sample to measure one window'}
          </div>
          {w.warning && <div className="mono small amber" data-testid="window-warning"><Icon name="flag" size={11} /> {w.warning}</div>}
          {w.fitted.length > 0 && <div className="mono small" data-testid="window-fitted">
            <Icon name="info" size={11} /> fitted: {w.fitted.map(f => `step ${String(f.step + 1).padStart(2, '0')} ${f.param} ${f.from} → ${f.to}`).join(' · ')}
          </div>}
          <div className="small row" style={{ gap: 6 }} data-testid="window-rules">
            how the windows are stitched
            <InfoTip title="Stitching">{w.rules.map(r => <p key={r.name} style={{ margin: '0 0 6px' }}><b>{r.name}</b> — {r.rule}</p>)}</InfoTip>
          </div>
        </>}
    </>
  )
}
