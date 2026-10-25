/* tq-grouping (2026-10-25): section 3 of the grouping editor — a basis's parameters, each method's own fields, and
 * the feature's live distribution with the bin edges or the cut drawn on it. Split out of GroupingPage.tsx. */
import { About, Callout, Icon, InfoTip, NumberField, Seg, SelectField, Slider, TextField } from '../kit'
import type { BasisKind, FeatureBin } from '../api/library'
import type { LibGroupingMethod } from '../api'
import { DISTANCE_BASES, METHOD_FOR, SHARED_PARAMS, methodOf, parseEdges, type Draft } from './groupingDraft'

/** The unit each feature is measured in and the axis it reads best on. Facts of `bases.py`, not measurements:
 *  `frequency_content` returns the Welch dominant frequency in Hz, `amplitude` the peak-to-peak in the
 *  waveform's own mV, `timescale` the duration in seconds. The RANGE is never from here — it is the live
 *  distribution's own extent. */
const FEATURE_AXIS: Partial<Record<BasisKind, { unit: string; label: string; scale: 'log' | 'linear' }>> = {
  'frequency-content': { unit: 'Hz', label: 'dominant frequency · Welch PSD', scale: 'log' },
  amplitude: { unit: 'mV', label: 'peak-to-peak amplitude', scale: 'linear' },
  timescale: { unit: 's', label: 'duration', scale: 'log' },
  polarity: { unit: '', label: 'signed polarity, −1 … +1', scale: 'linear' },
}
/** Choices for a method's `str` params, as the method's own help text names them (the registry carries no list). */
const STR_CHOICES: Record<string, string[]> = { cluster_selection_method: ['eom', 'leaf'], distance: ['sbd', 'euclidean'] }
/** Why a method with no tree has no merge-height histogram — said in place of the histogram, never a blank. */
const NO_TREE_WHY: Record<string, string> = {
  kshape: 'k-Shape builds no tree: it fits k centres and each shape joins the nearest one after sliding into place, so there is no merge height to cut. Set k instead (0 chooses it).',
  hdbscan: 'HDBSCAN builds no tree to cut here: families are the places where shapes crowd together, so the number of families is not chosen, and stragglers are left out as “in no dense family”. Its own threshold is epsilon, a separate input — never the tree cut.',
}

export function Params({ d, set, basis, dist, extent, clusterings, invalid, methods, cutMax = 1 }: {
  d: Draft; set: (p: Partial<Draft>) => void; basis: BasisKind; dist?: FeatureBin[]; extent: [number, number] | null
  clusterings: { value: string; label: string; scope: string }[]; invalid: { field: string; message: string } | null
  methods: LibGroupingMethod[]
  /** fixup-an: the slider's top — the kept tree's highest merge when there is one (Ward heights can pass 1) */
  cutMax?: number
}) {
  const axis = FEATURE_AXIS[basis]
  const err = (field: string) => invalid?.field === field ? <span className="k-field-error" role="alert" data-testid="param-error"><Icon name="alert-circle" size={11} />{invalid.message}</span> : null

  if (METHOD_FOR[basis] === 'feature_bins') {
    const [lo, hi] = d.range ?? extent ?? [0, 1]
    const edges = d.bins === 'fixed' ? parseEdges(d.edges).edges
      : d.bins === 'log' && lo > 0 ? Array.from({ length: d.nBins + 1 }, (_, i) => lo * Math.pow(hi / lo, i / d.nBins))
        : dist && dist.length ? quantileEdges(dist, d.nBins) : []
    return (
      <div className="lib-params">
        <div className="stack" style={{ gap: 6 }}>
          <span className="lib-key">feature</span>
          {/* one basis, one measurement: `bases.py` computes exactly one number per feature basis, so there is
              no feature to choose and the old two-option select was a choice that did not exist */}
          <div className="mono small">{axis?.label ?? basis}{axis?.unit ? ` · ${axis.unit}` : ''}</div>
          <div className="lib-param-row"><span>bins</span><Seg size="sm" ariaLabel="bins" testid="param-bins" value={d.bins} onChange={v => set({ bins: v })} options={[{ value: 'quantiles', label: 'quantiles' }, { value: 'log', label: 'log-spaced' }, { value: 'fixed', label: 'fixed edges' }]} /></div>
          {d.bins !== 'fixed' && <div className="lib-param-row"><span>number of bins</span><NumberField size="sm" width={64} value={d.nBins} integer min={2} max={20} showError={false} testid="param-nbins" ariaLabel="number of bins" onValid={n => set({ nBins: n })} onChange={(raw, reason) => { if (reason) set({ nBins: Number(raw) || 0 }) }} /></div>}
          {err('number of bins')}
          {d.bins !== 'fixed' && <div className="lib-param-row"><span>range</span><span className="row" style={{ gap: 4 }}>
            <NumberField size="sm" width={78} value={lo} showError={false} testid="param-lo" ariaLabel="range lower" onValid={n => set({ range: [n, hi] })} />–
            <NumberField size="sm" width={78} value={hi} unit={axis?.unit} showError={false} testid="param-hi" ariaLabel="range upper" onValid={n => set({ range: [lo, n] })} />
          </span></div>}
          {err('range')}
          {d.bins === 'fixed' && <><div className="lib-param-row"><span>edges</span><TextField size="sm" value={d.edges} onChange={v => set({ edges: v })} invalid={invalid?.field === 'edges'} testid="param-edges" width={190} suffix={axis?.unit} /></div>{err('edges')}</>}
          {d.bins === 'quantiles' && <span className="lib-cap row" style={{ gap: 4 }}>quantile edges <InfoTip title="Quantile bins">edges at the quantiles; every member falls in a bin</InfoTip></span>}
          {extent && <span className="lib-meta">measured range {extent[0].toPrecision(3)} – {extent[1].toPrecision(3)} {axis?.unit}</span>}
        </div>
        {dist && dist.length
          ? <FeatureHistogram bins={dist} edges={invalid ? [] : edges} scale={axis?.scale ?? 'linear'} unit={axis?.unit ?? ''} lo={lo} hi={hi}
            title={`members per ${axis?.label ?? basis} · ${axis?.scale ?? 'linear'} axis · sampled from the catalogue`} />
          : <NoDistribution what={basis} />}
      </div>
    )
  }

  if (DISTANCE_BASES.includes(basis)) {
    const method = methodOf(d)
    const spec = methods.find(m => m.name === method)
    // w2-f: the registered methods for this basis, from the editor read (one option, Ward, when the read lists none)
    const options = (methods.length ? methods : [{ name: 'ward', label: 'Ward linkage' } as LibGroupingMethod]).map(m => ({ value: m.name, label: m.label }))
    const methodRow = <div className="lib-param-row"><span>method</span><SelectField size="sm" value={method} onChange={v => set({ method: v })} options={options} width={170} testid="param-method" ariaLabel="grouping method" /></div>
    if (method !== 'ward') {
      return (
        <div className="lib-params">
          <div className="stack" style={{ gap: 6 }}>
            {methodRow}
            {spec?.description && <About label="about this method" testid="method-about"><span data-testid="method-description">{spec.description}</span></About>}
            {spec ? <MethodParams spec={spec} values={d.mparams[method] ?? {}} onChange={(k, v) => set({ mparams: { ...d.mparams, [method]: { ...(d.mparams[method] ?? {}), [k]: v } } })} />
              : <span className="lib-cap">the editor read carries no parameters for {method}</span>}
            <span className="row small" style={{ gap: 6 }}>how many families<InfoTip title="How many families">How many families this gives, and whether each beats noise of the same colour, is measured by the preview.</InfoTip></span>
          </div>
          <div className="k-card grey" style={{ padding: 10 }} data-testid="no-tree-line" data-method={method}>
            <span className="lib-cap">{spec?.tree ? 'this method builds a tree, but its merge heights are not sampled for the editor yet' : (NO_TREE_WHY[method] ?? `${spec?.label ?? method} builds no tree, so there is no merge-height histogram to cut`)}</span>
          </div>
        </div>
      )
    }
    return (
      <div className="lib-params">
        <div className="stack" style={{ gap: 6 }}>
          {methodRow}
          <div className="lib-param-row"><span>cut <InfoTip title="How many families">How many families the cut gives is measured by the preview, not guessed here.</InfoTip></span><Slider value={Math.min(d.cut, cutMax)} min={0.1} max={cutMax} step={0.01} onChange={v => set({ cut: +v.toFixed(2) })} format={v => v.toFixed(2)} width={190} testid="param-cut" ariaLabel="cut" /></div>
          <div className="lib-param-row"><span>nearest family past</span><NumberField size="sm" width={64} value={d.nearest} min={0.1} max={1} step={0.01} testid="param-nearest" ariaLabel="nearest family distance" onValid={n => set({ nearest: n })} /></div>
          {err('cut')}
        </div>
        {dist && dist.length
          ? <FeatureHistogram bins={dist} edges={[]} scale="linear" unit="" lo={0} hi={1} cut={d.cut}
            title={basis === 'shape-distance' ? 'Ward merge heights · sampled from the catalogue' : 'pairwise sequence similarity · sampled from the catalogue'} />
          : <NoDistribution what={basis} />}
      </div>
    )
  }

  return (
    <div className="lib-params">
      <div className="stack" style={{ gap: 6 }}>
        {basis === 'tag' && <>
          <div className="lib-param-row"><span>several tags <InfoTip title="Untagged members">A member with no tag is omitted and flagged; how many that is, is what the preview measures.</InfoTip></span><Seg size="sm" value={d.tagMode} onChange={v => set({ tagMode: v })} testid="param-tag-mode" options={[{ value: 'first', label: 'first tag' }, { value: 'each', label: 'one group per tag' }]} /></div>
        </>}
        {basis === 'provenance' && <div className="lib-param-row"><span>by</span><Seg size="sm" value={d.provBy} onChange={v => set({ provBy: v })} testid="param-prov" options={[{ value: 'recording', label: 'recording' }, { value: 'run', label: 'run' }, { value: 'spike_train', label: 'spike train' }]} /></div>}
        {basis === 'custom' && (clusterings.length
          ? <>
            <span className="lib-key">clustering</span>
            <SelectField value={d.clustering} onChange={v => set({ clustering: v })} options={clusterings.map(c => ({ value: c.value, label: c.label }))} testid="param-clustering" />
            <Callout tone="grey" icon="info">{clusterings.find(c => c.value === d.clustering)?.scope ?? 'registered clustering'}</Callout>
          </>
          : <Callout tone="amber" icon="info" testid="no-clusterings">No clustering is registered. Export one from Analyse and register it before grouping by it.</Callout>)}
      </div>
      <div className="k-card grey" style={{ padding: 10 }} data-testid="param-bars">
        {/* polarity, tag, provenance and custom used to draw invented bar charts here (`vals: [388, 702, 312]`).
            `GET /grouping-editor` returns distributions for five bases and this is not one of them. */}
        <NoDistribution what={basis} />
      </div>
    </div>
  )
}

/** w2-f: a registered method's own parameters, rendered from its spec (type, default, label, help). Numbers are
 *  number fields, a known string choice is a segmented control, anything else a text field. */
function MethodParams({ spec, values, onChange }: { spec: LibGroupingMethod; values: Record<string, unknown>; onChange: (k: string, v: unknown) => void }) {
  return (
    <>
      {Object.entries(spec.params).filter(([k]) => !SHARED_PARAMS.has(k)).map(([k, ps]) => {
        const v = k in values ? values[k] : ps.default
        const tip = <InfoTip title={ps.label}>{ps.help}</InfoTip>
        if (ps.type === 'int' || ps.type === 'float') {
          return <div key={k} className="lib-param-row"><span>{ps.label} {tip}</span>
            <NumberField size="sm" width={78} value={typeof v === 'number' ? v : Number(v ?? 0)} integer={ps.type === 'int'} min={0} step={ps.type === 'int' ? 1 : 0.01} showError={false}
              testid={`param-${k}`} ariaLabel={ps.label} onValid={n => onChange(k, n)} /></div>
        }
        const choices = STR_CHOICES[k]
        if (choices) {
          return <div key={k} className="lib-param-row"><span>{ps.label} {tip}</span>
            <Seg size="sm" value={String(v)} onChange={x => onChange(k, x)} testid={`param-${k}`} ariaLabel={ps.label} options={choices.map(c => ({ value: c, label: c }))} /></div>
        }
        return <div key={k} className="lib-param-row"><span>{ps.label} {tip}</span><TextField size="sm" value={String(v ?? '')} onChange={x => onChange(k, x)} testid={`param-${k}`} width={120} /></div>
      })}
    </>
  )
}

function NoDistribution({ what }: { what: string }) {
  return <div className="stack" style={{ gap: 4, padding: 6 }}><span className="lib-cap">no distribution for {what} <InfoTip title="No distribution">The editor read carries distributions for amplitude, timescale, frequency content and the two distance bases; the group sizes for this basis are what the preview measures.</InfoTip></span></div>
}

function quantileEdges(dist: FeatureBin[], n: number): number[] {
  if (!dist.length || n < 1) return []
  const total = dist.reduce((s, b) => s + b.n, 0), out = [dist[0].lo]
  let acc = 0, k = 1
  for (const b of dist) { acc += b.n; while (k < n && total > 0 && acc >= (total * k) / n) { out.push(b.hi); k++ } }
  out.push(dist[dist.length - 1].hi)
  return out
}

/** Distribution with bin edges (or a cut) drawn on it; log or linear x. Bars outside [lo, hi] are amber.
 *  Every bar is a live count from the editor read — nothing here is generated. */
function FeatureHistogram({ bins, edges, scale, unit, lo, hi, cut, title }: { bins: FeatureBin[]; edges: number[]; scale: 'log' | 'linear'; unit: string; lo: number; hi: number; cut?: number; title: string }) {
  const W = 430, H = 112, padL = 8, padR = 8, padT = 22, padB = 18
  if (!bins.length) return <div className="k-card grey" style={{ padding: 10 }}><span className="lib-cap">no distribution</span></div>
  const x0 = bins[0].lo, x1 = bins[bins.length - 1].hi
  const logOk = scale === 'log' && x0 > 0 && x1 > x0
  const tx = (v: number) => padL + (logOk ? (Math.log(Math.max(v, x0)) - Math.log(x0)) / (Math.log(x1) - Math.log(x0)) : (v - x0) / (x1 - x0 || 1)) * (W - padL - padR)
  const max = Math.max(...bins.map(b => b.n), 1)
  const ty = (n: number) => H - padB - (n / max) * (H - padT - padB)
  const ticks = logOk ? [lo, Math.sqrt(Math.max(lo, x0) * hi), hi].map(v => +v.toPrecision(2)) : [x0, (x0 + x1) / 2, x1].map(v => +v.toPrecision(3))
  const outside = (b: FeatureBin) => cut == null && (b.hi > hi * 1.0001 || b.lo < lo * 0.9999)
  return (
    <div className="k-card grey" style={{ padding: '6px 8px' }} data-testid="feature-histogram">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 9 }}>
        <text x={padL} y={11} fill="var(--muted)">{title}</text>
        {bins.map((b, i) => <rect key={i} x={tx(b.lo) + 0.8} width={Math.max(1, tx(b.hi) - tx(b.lo) - 1.6)} y={ty(b.n)} height={H - padB - ty(b.n)} fill={outside(b) ? '#f6c27a' : '#94c2ff'}><title>{`${b.lo.toPrecision(3)}–${b.hi.toPrecision(3)} ${unit} · ${b.n} members`}</title></rect>)}
        <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} stroke="var(--border-strong)" />
        {edges.map((e, i) => <line key={i} x1={tx(e)} x2={tx(e)} y1={padT - 4} y2={H - padB} stroke={i === 0 || i === edges.length - 1 ? 'var(--blue)' : '#1f2937'} strokeWidth={1} />)}
        {cut != null && <g><line x1={tx(cut)} x2={tx(cut)} y1={padT - 6} y2={H - padB} stroke="var(--amber)" strokeWidth={1.5} strokeDasharray="4 3" /><text x={tx(cut) + 4} y={padT} fill="#c27400">cut {cut.toFixed(2)}</text></g>}
        {cut == null && bins.some(outside) && <text x={W - padR} y={padT} textAnchor="end" fill="#c27400">outside range</text>}
        {ticks.map((t, i) => <text key={i} x={tx(Math.min(x1, Math.max(x0, t)))} y={H - 5} textAnchor={i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'} fill="var(--muted)">{t}{i === ticks.length - 1 && unit ? ` ${unit}` : ''}</text>)}
      </svg>
    </div>
  )
}
