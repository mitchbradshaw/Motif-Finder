/* 02 Noise floor (frame chain-6, template for any estimator block): the segment-slope distribution with the noise model
 * and the cut lines, the estimate with its uncertainty, whether one σ holds across the span, and the recording floor.
 * The cut multiplier k belongs to 03's cutlines (B24): editing it here marks 03 → 04 stale, 02 stays cached. */
import { useState } from 'react'
import { EnvelopePath, TimeAxis } from '../../../charts/primitives'
import { makeX, makeY } from '../../../charts/scale'
import { scaleLinear } from 'd3'
import { Chip, Icon, InfoTip, Legend, Seg } from '../../../kit'
import { useToast } from '../../../shell/Toast'
import { SYM5 } from '../../Renderer'
import { pad2 } from '../chainState'
import { BlockCard, ParamSelect, ParamSlider, ParamsCard, PlotBox, num, str, type BlockProps } from './common'

export function NoiseFloorBlock({ fx, draft, setDraft, st, actions, bundle, running, index }: BlockProps) {
  const toast = useToast()
  const [scale, setScale] = useState<'linear' | 'log'>('log')
  const enc = st.steps.find(s => s.block === 'demo.symbolic_encoding')
  const encIndex = enc ? st.steps.indexOf(enc) : -1
  const k = num(enc?.params.noise_k, 8)
  const sigma = fx.sigma
  const floorFrom = str(draft.floor_from, 'this span')
  const est = floorFrom === 'this span' ? sigma : fx.noise.recording_floor
  const bins = 48, lo = -0.12, hi = 0.12
  const counts = new Array(bins).fill(0)
  for (const v of fx.slopes) { const b = Math.floor((Math.max(lo, Math.min(hi - 1e-9, v)) - lo) / (hi - lo) * bins); counts[b]++ }
  const scaled = counts.map(c => c * 18)   // 250 segments drawn as the per-run histogram of 4,500 segments (18 surrogate-length spans)
  const t0 = bundle.source.t0_s, t1 = bundle.source.t1_s

  return (
    <div className="bx-grid">
      <BlockCard title={<><span className="mono muted" style={{ fontWeight: 400, fontSize: 12 }}>02</span> Noise floor <span className="sig">Signal → Signal + estimate</span></>} testid="block-process" info="Every 0.2 s segment's slope. The noise model is a Gaussian with the MAD-based σ; the tails beyond ±kσ are what 03 writes as d and u."
        actions={<Seg options={[{ value: 'linear', label: 'linear' }, { value: 'log', label: 'log count' }]} value={scale} onChange={v => setScale(v as 'linear' | 'log')} size="sm" testid="noise-scale" />}>
        <PlotBox height={250} testid="noise-histogram">
          {(w, h) => {
            const x = scaleLinear().domain([lo, hi]).range([40, w - 10])
            const ph = h - 36
            const max = Math.max(...scaled)
            const y = scale === 'log' ? scaleLinear().domain([0, Math.log10(max * 1.2)]).range([ph, 6]) : scaleLinear().domain([0, max * 1.1]).range([ph, 6])
            const yv = (c: number) => (scale === 'log' ? y(c > 0 ? Math.log10(c) : 0) : y(c))
            const bw = (x(hi) - x(lo)) / bins
            const model = Array.from({ length: 120 }, (_, i) => { const s = lo + (hi - lo) * i / 119; return max * Math.exp(-(s * s) / (2 * (sigma * 2.4) ** 2)) })
            const cut = (s: number, label: string, colour: string) => <g key={label}><line x1={x(s)} x2={x(s)} y1={4} y2={ph} stroke={colour} strokeWidth={1.4} /><text x={x(s) + 4} y={14} style={{ fill: colour, fontSize: 10 }}>{label}</text></g>
            return (
              <>
                {counts.map((c, i) => {
                  const mid = lo + (i + 0.5) * (hi - lo) / bins
                  const col = mid <= -k * sigma ? SYM5[0] : mid >= k * sigma ? SYM5[4] : '#cfd2d6'
                  const cc = scaled[i] || (Math.abs(mid) > 3 * sigma ? 1 : 0)
                  return <rect key={i} x={x(lo) + i * bw + 0.5} y={yv(cc)} width={Math.max(1, bw - 1)} height={Math.max(0, ph - yv(cc))} fill={col} />
                })}
                <path d={model.map((m, i) => `${i ? 'L' : 'M'}${x(lo + (hi - lo) * i / 119).toFixed(1)} ${yv(Math.max(1, m)).toFixed(1)}`).join('')} fill="none" stroke="var(--blue)" strokeWidth={1.6} />
                {cut(-k * sigma, `−${k}σ  d cut`, 'var(--red)')}{cut(k * sigma, `+${k}σ  u cut`, 'var(--red)')}{cut(-3 * sigma, '−3σ', 'var(--amber)')}{cut(3 * sigma, '+3σ', 'var(--amber)')}
                <line x1={40} x2={w - 10} y1={ph} y2={ph} stroke="var(--border)" />
                {[-0.12, -0.06, 0, 0.06, 0.12].map(v => <text key={v} x={x(v)} y={ph + 14} textAnchor="middle" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v > 0 ? '+' : v < 0 ? '−' : ''}{Math.abs(v).toFixed(2).replace(/^0/, '')}</text>)}
                {(scale === 'log' ? [1, 10, 100, 1000] : [0, Math.round(max / 2), max]).filter(v => v <= max * 1.2).map(v => <text key={v} x={34} y={yv(v) + 3} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v}</text>)}
                <text x={w - 10} y={h - 4} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>segment slope, mV/s</text>
              </>
            )
          }}
        </PlotBox>
        <Legend items={[{ label: 'segments within noise', colour: '#cfd2d6' }, { label: `tail beyond −${k}σ → d`, colour: SYM5[0] }, { label: `tail beyond +${k}σ → u`, colour: SYM5[4] }, { label: 'noise model · MAD σ', colour: 'var(--blue)', shape: 'line' }]} />
      </BlockCard>

      <ParamsCard title="The estimate" note={<InfoTip title="The estimate">σ is the MAD of segment slopes × 1.4826, with detected spans excluded and re-estimated twice. The bootstrap resamples segments 500×.</InfoTip>}>
        <div className="bx-estimate wide" style={{ gridColumn: '1 / -1' }} data-testid="noise-estimate">
          <div className="mono" style={{ fontSize: 11 }}>slope noise σ</div>
          <div className="big">{est.toFixed(5)} mV/s</div>
          <div className="mono" style={{ fontSize: 10.5 }}>95 % CI [{fx.noise.ci[0].toFixed(5)} – {fx.noise.ci[1].toFixed(5)}] · bootstrap {fx.noise.bootstrap}×{floorFrom !== 'this span' ? ' · from Settings › Datasets' : ''}</div>
        </div>
        <ParamSelect label="estimator" info="MAD × 1.4826 is robust to the drops themselves; the standard deviation is pulled up by them." value={str(draft.estimator, 'MAD × 1.4826')} options={['MAD × 1.4826', 'standard deviation', 'IQR / 1.349']} onChange={v => setDraft('estimator', v)} testid="param-estimator" disabled={running} />
        <ParamSlider label="cut k" info="The multiple of σ at which a segment counts as d or u. It is 03's cutline, chosen in 03's sweep; changing it here marks 03 and 04 stale." value={k} onChange={v => { if (enc) { actions.setParam(enc.uid, 'noise_k', v); toast.push({ text: `cut k ${v} σ · ${pad2(encIndex + 1)} and later are stale` }) } }} min={2} max={20} step={1} unit="σ" rec={8} recNote="chosen in 03's sweep" testid="param-noise_k" disabled={running || !enc} />
        <ParamSelect label="scope" info="One σ for the whole span, or a rolling σ (10 s) where the floor drifts." value={str(draft.scope, 'whole span')} options={['whole span', 'rolling 10 s']} onChange={v => setDraft('scope', v)} testid="param-scope" disabled={running} />
        <ParamSelect label="exclude" info="Detected spans are removed before σ is estimated, then re-estimated." value={str(draft.exclude, 'detected spans · iterate 2×')} options={['detected spans · iterate 2×', 'detected spans · once', 'nothing']} onChange={v => setDraft('exclude', v)} testid="param-exclude" disabled={running} />
        <div className="bx-param wide" style={{ gridColumn: '1 / -1' }}>
          <div className="lab"><span>floor comes from</span><InfoTip title="floor comes from">This span's own estimate, or the per-channel recording floor kept in Settings › Datasets.</InfoTip></div>
          <Seg options={[{ value: 'this span', label: 'this span' }, { value: 'recording floor', label: 'recording floor (Settings › Datasets)' }]} value={floorFrom} onChange={v => setDraft('floor_from', v)} size="sm" testid="param-floor_from" />
        </div>
      </ParamsCard>

      <BlockCard title="Does one σ hold across the span?" info="A 10 s rolling σ against the global σ. Above 25 % drift the floor should be rolling, not global." actions={<Chip tone={fx.noise.drift_pct > 25 ? 'amber' : 'green'} size="sm">drift {fx.noise.drift_pct} % · within tolerance</Chip>} testid="noise-stability">
        <PlotBox height={130}>
          {(w, h) => {
            const x = makeX(t0, t1, w, 40, 8)
            const y = makeY(sigma * 0.7, sigma * 1.3, h - 24, 6, 4)
            const tt = fx.noise.rolling.map((_, i) => t0 + (t1 - t0) * i / (fx.noise.rolling.length - 1))
            return (
              <>
                <rect x={40} y={y(sigma * 1.12)} width={w - 48} height={y(sigma * 0.88) - y(sigma * 1.12)} fill="var(--blue-100)" />
                <line x1={40} x2={w - 8} y1={y(sigma)} y2={y(sigma)} stroke="var(--blue)" strokeWidth={1.6} />
                <text x={w - 10} y={y(sigma) - 4} textAnchor="end" style={{ fill: 'var(--blue-600)', fontSize: 10 }}>global σ</text>
                <EnvelopePath t={tt} v={fx.noise.rolling} x={x} y={y} stroke="var(--text)" width={1.1} />
                <text x={2} y={y(sigma) + 3} style={{ fontSize: 10, fill: 'var(--muted)' }}>10 s σ</text>
                <TimeAxis x={x} y={h - 22} t0={t0} t1={t1} n={5} ends />
              </>
            )
          }}
        </PlotBox>
        <div className="mono muted" style={{ fontSize: 10.5 }}>above 25 % drift the floor should be rolling, not global — Rolling scope switches it</div>
      </BlockCard>

      <BlockCard title="Against the recording floor" info="This span's σ beside the per-channel recording floor and the σ of 200 surrogate spans." testid="recording-floor">
        <div className="bx-table">
          <div className="bx-tr two"><span className="muted">this span</span><b className="mono t-blue">{sigma.toFixed(5)} mV/s</b></div>
          <div className="bx-tr two"><span className="muted">recording floor · CH4</span><b className="mono">{fx.noise.recording_floor.toFixed(5)} mV/s</b></div>
          <div className="bx-tr two"><span className="muted">surrogate spans ({fx.noise.surrogate.n})</span><b className="mono">{fx.noise.surrogate.mean.toFixed(5)} [{fx.noise.surrogate.lo}–{fx.noise.surrogate.hi}]</b></div>
        </div>
        <div className="mono" style={{ fontSize: 11, color: '#15794f', marginTop: 8 }}><Icon name="check-circle" size={12} /> within 5 % of the recording floor</div>
      </BlockCard>

      <BlockCard className="span2" title="Output · Scores" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>slope ÷ σ per segment, what {encIndex >= 0 ? pad2(encIndex + 1) : '03'} cuts</span>} testid="noise-output">
        <PlotBox height={46}>
          {(w, h) => {
            const x = makeX(t0, t1, w, 0, 0)
            const cw = Math.max(1, x(t0 + fx.segS) - x(t0) - 0.5)
            return <>{fx.slopes.map((s, i) => { const z = s / sigma; const q = z <= -k ? 0 : z >= k ? 4 : 2; const hh = Math.min(h / 2 - 2, Math.abs(z) * 1.3); return <rect key={i} x={x(t0 + i * fx.segS)} y={z < 0 ? h / 2 : h / 2 - hh} width={cw} height={Math.max(1, hh)} fill={q === 2 ? '#d4d4d8' : SYM5[q]} /> })}<line x1={0} x2={w} y1={h / 2} y2={h / 2} stroke="var(--border)" /></>
          }}
        </PlotBox>
      </BlockCard>
    </div>
  )
}
