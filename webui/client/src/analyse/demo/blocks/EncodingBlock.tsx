/* 03 Symbolic encoding (frame chain-3, the reference block page; title per B24, not the frame's stale "02"): four
 * aligned strips — signal + PAA, slope + cutlines (d and u draggable, in multiples of 02's σ), quantised k 5, dSAX k 3 —
 * the parameters with recommended markers, and the noise-floor sweep against the surrogate (click a value to set it). */
import { useState } from 'react'
import { EnvelopePath, TimeAxis } from '../../../charts/primitives'
import { makeX, makeY } from '../../../charts/scale'
import { scaleLinear } from 'd3'
import { Button, Dropdown, EmptyState, Icon, InfoTip, Legend, ProgressBar, RangeSlider, Seg, useSim } from '../../../kit'
import { quantise5, toK3 } from '../../../api/analyse'
import { SYM3_DEMO, SYM5 } from '../../Renderer'
import { BlockCard, DragH, ParamSelect, ParamSlider, ParamsCard, PlotBox, Tiles, num, str, type BlockProps } from './common'

export function EncodingBlock({ fx, draft, setDraft, bundle, running }: BlockProps) {
  const [win, setWin] = useState<[number, number]>([5, 15])
  const [sweep, setSweep] = useState('noise floor')
  const [surr, setSurr] = useState('50')
  const sweepSim = useSim(`analyse.demo.sweep.${sweep}`)
  const k = num(draft.noise_k, 8)
  const alphabet = num(draft.alphabet, 3)
  const segS = num(draft.segment_s, 0.2)
  const sigma = fx.sigma
  const t0 = bundle.source.t0_s
  const w0 = t0 + win[0], w1 = t0 + win[1]
  const i0 = Math.floor(win[0] / fx.segS), i1 = Math.ceil(win[1] / fx.segS)
  const slopes = fx.slopes
  const q5 = slopes.map(v => quantise5(v, k, sigma))
  const dCount = q5.filter(q => q === 0).length, uCount = q5.filter(q => q === 4).length
  const same = Math.round(100 * q5.filter(q => q === 2).length / q5.length)
  const setK = (v: number) => setDraft('noise_k', Math.max(2, Math.min(20, Math.round(v * 2) / 2)))
  const trace = fx.detection
  const tIdx = trace.t.map((t, i) => [t, i] as const).filter(([t]) => t >= w0 - 0.2 && t <= w1 + 0.2).map(([, i]) => i)

  const STRIP_L = 80
  return (
    <div className="bx-grid">
      <BlockCard title={<><span className="mono muted" style={{ fontWeight: 400, fontSize: 12 }}>03</span> Symbolic encoding <span className="sig">Signal → Encoding</span></>} testid="block-process"
        info="What the block looked at (signal and its PAA), what it computed (the slope per segment against the cutlines) and what it emitted (the quantised and dSAX strips). Drag the d or u cutline to change the noise-floor multiple."
        actions={<span className="row" style={{ gap: 8 }}><span className="mono muted" style={{ fontSize: 10.5 }}>showing {win[0].toFixed(0)}–{win[1].toFixed(0)} s of 50 s</span><span style={{ width: 200 }}><RangeSlider value={win} onChange={v => setWin(v[1] - v[0] < 4 ? [v[0], v[0] + 4] : v)} min={0} max={50} step={1} testid="encoding-window" /></span></span>}>
        <PlotBox height={330} testid="encoding-strips">
          {(w) => {
            const x = makeX(w0, w1, w, STRIP_L, 34)
            const cw = Math.max(1, x(w0 + fx.segS) - x(w0) - 0.4)
            const ys = makeY(-0.45, 0.35, 100, 6, 6)
            const ext = Math.max(k * sigma * 1.35, 0.09)
            const yb = scaleLinear().domain([-ext, ext]).range([200, 118])
            const paa: number[] = []; const paaT: number[] = []
            const per = Math.max(1, Math.round(segS / 0.2))
            for (let j = 0; j < tIdx.length; j += per) { const chunk = tIdx.slice(j, j + per).map(i => trace.out[i]); const m = chunk.reduce((a, b) => a + b, 0) / chunk.length; paaT.push(trace.t[tIdx[j]], trace.t[tIdx[Math.min(tIdx.length - 1, j + per)]]); paa.push(m, m) }
            const lab = (y: number, a: string, b?: string) => <text x={0} y={y} style={{ fontSize: 10.5, fill: 'var(--muted)' }}>{a}{b && <tspan x={0} dy={12}>{b}</tspan>}</text>
            return (
              <>
                {lab(14, 'signal +', 'PAA')}
                <EnvelopePath t={tIdx.map(i => trace.t[i])} v={tIdx.map(i => trace.out[i])} x={x} y={ys} stroke="#a3a3a3" />
                <EnvelopePath t={paaT} v={paa} x={x} y={ys} stroke="var(--blue)" width={1.8} />
                {lab(130, 'slope +', 'cutlines')}{lab(160, 'mV/s')}
                <line x1={STRIP_L} x2={w - 34} y1={yb(0)} y2={yb(0)} stroke="var(--border)" />
                {slopes.slice(i0, i1).map((v, j) => { const i = i0 + j; const c = Math.max(-ext, Math.min(ext, v)); return <rect key={i} x={x(t0 + i * fx.segS)} y={Math.min(yb(0), yb(c))} width={cw} height={Math.max(1, Math.abs(yb(c) - yb(0)))} fill={SYM5[q5[i]]} /> })}
                <line x1={STRIP_L} x2={w - 34} y1={yb(3 * sigma)} y2={yb(3 * sigma)} stroke="#f59e0b" strokeDasharray="4 3" /><text x={w - 32} y={yb(3 * sigma) + 3} style={{ fontSize: 10, fill: '#b45309' }}>U +{(3 * sigma).toFixed(3)}</text>
                <line x1={STRIP_L} x2={w - 34} y1={yb(-3 * sigma)} y2={yb(-3 * sigma)} stroke="#f59e0b" strokeDasharray="4 3" /><text x={w - 32} y={yb(-3 * sigma) + 3} style={{ fontSize: 10, fill: '#b45309' }}>D −{(3 * sigma).toFixed(3)}</text>
                <g transform={`translate(${STRIP_L},0)`}>
                  <DragH y={yb(k * sigma)} width={w - STRIP_L - 34} onValue={setK} toValue={py => yb.invert(py) / sigma} colour="var(--red)" label={`u +${(k * sigma).toFixed(3)} · ${k}σ · drag`} testid="cutline-u" />
                  <DragH y={yb(-k * sigma)} width={w - STRIP_L - 34} onValue={setK} toValue={py => -yb.invert(py) / sigma} colour="var(--red)" label={`d −${(k * sigma).toFixed(3)} · ${k}σ · drag`} testid="cutline-d" />
                </g>
                {lab(228, 'quantised', 'k 5')}
                {q5.slice(i0, i1).map((q, j) => <rect key={j} x={x(t0 + (i0 + j) * fx.segS)} y={218} width={cw + 0.4} height={24} fill={SYM5[q]}><title>{'dDSUu'[q]}</title></rect>)}
                {lab(270, `dSAX k ${alphabet}`)}
                {q5.slice(i0, i1).map((q, j) => <rect key={j} x={x(t0 + (i0 + j) * fx.segS)} y={258} width={cw + 0.4} height={24} fill={alphabet === 3 ? SYM3_DEMO[toK3(q)] : SYM5[q]} />)}
                <TimeAxis x={x} y={296} t0={w0} t1={w1} n={4} />
              </>
            )
          }}
        </PlotBox>
        <Legend items={[{ label: 'd fast down', colour: SYM5[0] }, { label: 'D down', colour: SYM5[1] }, { label: 'S same', colour: SYM5[2] }, { label: 'U up', colour: SYM5[3] }, { label: 'u fast up', colour: SYM5[4] }, { label: 'PAA mean', colour: 'var(--blue)', shape: 'line' }]} />
      </BlockCard>

      <ParamsCard note={<><span className="bx-rec-bar" /> recommended for this span <InfoTip title="recommended">Values the adapter's recommend hook produced for this span (D4): the segment length from the event scale, the noise floor from the sweep knee.</InfoTip></>}>
        <div className="bx-param">
          <div className="lab"><span>alphabet k</span><InfoTip title="alphabet k">3: down / same / up. 5 splits each direction into slow and fast.</InfoTip></div>
          <Seg options={[{ value: '3', label: '3' }, { value: '4', label: '4' }, { value: '5', label: '5' }]} value={String(alphabet)} onChange={v => setDraft('alphabet', Number(v))} size="sm" testid="param-alphabet" />
        </div>
        <ParamSelect label="split" info="Which letters the k 5 alphabet merges when k 3 is emitted." value={str(draft.split, 'd/D · U/u')} options={['d/D · U/u', 'd · D/S/U · u']} onChange={v => setDraft('split', v)} testid="param-split" disabled={running} />
        <ParamSlider label="segment length" info="Length of one PAA segment. Shorter than a third of the fastest drop and the slope is mostly noise." value={segS} onChange={v => setDraft('segment_s', v)} min={0.2} max={2} step={0.2} unit="s" rec={0.2} testid="param-segment_s" disabled={running} />
        <ParamSlider label="same_fraction" info="The share of segments the SAME letter should hold on a quiet stretch." value={num(draft.same_fraction, 0.6)} onChange={v => setDraft('same_fraction', v)} min={0.3} max={0.9} step={0.05} rec={0.55} format={v => v.toFixed(2)} testid="param-same_fraction" disabled={running} />
        <ParamSlider label="noise floor" info="The d and u cutlines in multiples of 02's slope noise σ. The sweep below shows where it beats the surrogate." value={k} onChange={setK} min={2} max={20} step={0.5} unit="σ" rec={8} recNote="recommended · the sweep knee" testid="param-noise_k" disabled={running} />
        <ParamSelect label="edges" info="How the last partial segment is handled." value={str(draft.edges, 'reflect')} options={['reflect', 'trim', 'pad']} onChange={v => setDraft('edges', v)} testid="param-edges" disabled={running} />
        <div style={{ gridColumn: '1 / -1' }}>
          <Tiles items={[{ k: 'segments', v: Math.round(50 / segS) }, { k: 'qualify as d', v: dCount, tone: 'red' }, { k: 'qualify as u', v: uCount, tone: 'blue' }, { k: 'in SAME', v: `${same} %` }]} />
          <div className="bp-info" data-testid="encoding-readout"><Icon name="info" size={12} /> {k} σ puts ‘d’ at −{(k * sigma).toFixed(4)} mV/s — {k >= 6 ? 'faster than noise explains' : 'noise alone crosses it often'}</div>
        </div>
      </ParamsCard>

      <BlockCard className="span2" title="This parameter against the null" info="The same parameter at eight values, each with its own surrogate runs: a setting is chosen against chance rather than by counting detections."
        sub={<span className="row" style={{ gap: 8 }}><Dropdown prefix="sweep" value={sweep} onChange={setSweep} options={[{ value: 'noise floor', label: 'noise floor' }, { value: 'segment length', label: 'segment length' }, { value: 'same_fraction', label: 'same_fraction' }]} active testid="sweep-param" /><Dropdown prefix="surrogates" value={surr} onChange={setSurr} options={[{ value: '50', label: '50 per value' }, { value: '200', label: '200 per value' }]} /></span>}
        actions={<span className="mono muted" style={{ fontSize: 10.5 }}>click a value to set it</span>} testid="null-sweep">
        {sweep === 'noise floor' || sweepSim.status === 'done' ? (
          <>
            <PlotBox height={150} testid="sweep-bars">
              {(w, h) => {
                const cols = fx.sweep.length; const cwid = (w - 40) / cols
                const y = scaleLinear().domain([0, 125]).range([h - 34, 6])
                return (
                  <>
                    {[0, 40, 80, 120].map(v => <g key={v}><text x={30} y={y(v) + 3} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v}</text></g>)}
                    {fx.sweep.map((s, i) => {
                      const on = sweep === 'noise floor' ? s.k === k : i === 3
                      const x0 = 40 + i * cwid
                      return (
                        <g key={s.k} onClick={() => sweep === 'noise floor' && setK(s.k)} style={{ cursor: 'pointer' }} data-testid={`sweep-${s.k}`}>
                          <rect x={x0 + 4} y={0} width={cwid - 8} height={h - 4} fill={on ? 'var(--blue-100)' : 'transparent'} rx={6} />
                          <rect x={x0 + cwid / 2 - 22} y={y(s.observed)} width={20} height={y(0) - y(s.observed)} fill={on ? 'var(--blue)' : '#9db8e8'} />
                          <rect x={x0 + cwid / 2 + 2} y={y(s.null)} width={20} height={Math.max(1, y(0) - y(s.null))} fill="#d4d4d8" />
                          <line x1={x0 + cwid / 2 + 12} x2={x0 + cwid / 2 + 12} y1={y(s.ci[1])} y2={y(s.ci[0])} stroke="var(--text-2)" />
                          <text x={x0 + cwid / 2} y={h - 20} textAnchor="middle" style={{ fontSize: 10.5, fill: on ? 'var(--blue-600)' : 'var(--text-2)', fontWeight: on ? 600 : 400 }}>{sweep === 'noise floor' ? `${s.k}σ` : sweep === 'segment length' ? `${(0.1 * (i + 1)).toFixed(1)} s` : (0.35 + i * 0.05).toFixed(2)}</text>
                          <text x={x0 + cwid / 2} y={h - 6} textAnchor="middle" style={{ fontSize: 10, fill: 'var(--purple)' }}>{s.ratio}</text>
                        </g>
                      )
                    })}
                  </>
                )
              }}
            </PlotBox>
            <div className="row" style={{ justifyContent: 'space-between', marginTop: 4 }}>
              <Legend items={[{ label: 'observed', colour: '#9db8e8' }, { label: 'surrogate mean · 95 % CI', colour: '#d4d4d8' }, { label: 'observed ÷ null', colour: 'var(--purple)' }]} />
              <span className="mono" style={{ fontSize: 11 }}>{k === 8 ? '8σ is the knee — the ratio jumps 2.7× → 7.7× while 23 d segments remain' : `${k}σ · the knee is 8σ (the ratio jumps 2.7× → 7.7×)`}</span>
            </div>
          </>
        ) : (
          <EmptyState size="sm" icon="bar-chart" title={`${sweep} has not been swept for this span`} caption={`8 values × ${surr} surrogates each · ≈ 12 s`}
            action={sweepSim.busy ? <ProgressBar value={sweepSim.fraction} label="sweeping" width={220} /> : <Button onClick={() => sweepSim.start({ steps: Array.from({ length: 8 }, (_, i) => `value ${i + 1}`), stepMs: 250 })} testid="run-sweep">Run sweep</Button>} />
        )}
      </BlockCard>
    </div>
  )
}
