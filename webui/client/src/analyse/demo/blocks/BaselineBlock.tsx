/* 01 Baseline removal (frame chain-5, template for any Signal → Signal transform): input + estimated baseline, output,
 * edge zones; stacked / overlay / difference; the window against the events it must not eat; other windows on the same
 * stretch; what the change does downstream (a preview on the cached span — nothing is written until Apply). */
import { useMemo, useState } from 'react'
import { EnvelopePath, TimeAxis, YLabels } from '../../../charts/primitives'
import { makeX, makeY } from '../../../charts/scale'
import { Callout, Chip, Legend, MiniTrace, Seg } from '../../../kit'
import { BlockCard, ParamSelect, ParamSlider, ParamsCard, PlotBox, Tiles, num, str, type BlockProps } from './common'

/** Display-only preview of a rolling baseline on the fixture trace (demo: no core computation). */
function rolling(values: number[], halfPts: number) {
  const out: number[] = []
  for (let i = 0; i < values.length; i++) { let s = 0, c = 0; for (let k = Math.max(0, i - halfPts); k <= Math.min(values.length - 1, i + halfPts); k++) { s += values[k]; c++ } out.push(s / c) }
  return out
}
const PTS_PER_S = 5

export function BaselineBlock({ fx, draft, setDraft, step, bundle, running }: BlockProps) {
  const [view, setView] = useState<'stacked' | 'overlay' | 'difference'>('stacked')
  const window_s = num(draft.window_s, 7)
  const was = num(step.params.window_s, 7)
  const { t, raw } = fx.detection
  const t0 = bundle.source.t0_s, t1 = bundle.source.t1_s
  const input = useMemo(() => raw.map(v => v + 0.62), [raw])
  const base = useMemo(() => rolling(input, Math.round(window_s * PTS_PER_S / 2)), [input, window_s])
  const output = useMemo(() => input.map((v, i) => v - base[i]), [input, base])
  const edge = window_s / 2
  const variance = Math.round(Math.min(88, 50 + window_s * 3))
  const drift = +(0.1 + window_s * 0.045).toFixed(1)

  const panel = (w: number, top: number, h: number, series: { v: number[]; stroke: string; width?: number }[], label: string, dom: [number, number]) => {
    const x = makeX(t0, t1, w, 34, 8)
    const y = makeY(dom[0], dom[1], h, 14, 4)
    return (
      <g transform={`translate(0,${top})`}>
        <rect x={x(t0)} y={0} width={x(t0 + edge) - x(t0)} height={h} fill="#fff1dc" />
        <rect x={x(t1 - edge)} y={0} width={x(t1) - x(t1 - edge)} height={h} fill="#fff1dc" />
        <line x1={34} x2={w - 8} y1={y(0)} y2={y(0)} stroke="var(--grey-200)" />
        {series.map((s, i) => <EnvelopePath key={i} t={t} v={s.v} x={x} y={y} stroke={s.stroke} width={s.width ?? 1.2} />)}
        <YLabels y={y} values={[dom[1], 0, dom[0]]} x={2} />
        <text x={40} y={10} style={{ fill: 'var(--muted)', fontSize: 10 }}>{label}</text>
      </g>
    )
  }
  return (
    <div className="bx-grid">
      <BlockCard title={<><span className="mono muted" style={{ fontWeight: 400, fontSize: 12 }}>01</span> Baseline removal <span className="sig">Signal → Signal</span></>} testid="block-process" info="Input vs output on the same stretch. The orange band at each end is half a window: the baseline there leans on reflected samples."
        actions={<Seg options={[{ value: 'stacked', label: 'stacked' }, { value: 'overlay', label: 'overlay' }, { value: 'difference', label: 'difference' }]} value={view} onChange={v => setView(v as typeof view)} size="sm" testid="baseline-view" />}>
        <PlotBox height={300} testid="baseline-plot">
          {(w) => {
            const x = makeX(t0, t1, w, 34, 8)
            return (
              <>
                {view === 'stacked' && <>{panel(w, 0, 130, [{ v: input, stroke: '#a3a3a3' }, { v: base, stroke: '#f97316', width: 2 }], `input + estimated baseline (${window_s} s ${str(draft.method, 'rolling median')})`, [-0.9, 0.9])}{panel(w, 140, 130, [{ v: output, stroke: 'var(--blue)', width: 1.4 }], 'output = input − baseline', [-0.45, 0.35])}</>}
                {view === 'overlay' && panel(w, 0, 270, [{ v: input, stroke: '#a3a3a3' }, { v: base, stroke: '#f97316', width: 2 }, { v: output, stroke: 'var(--blue)', width: 1.4 }], 'input, baseline and output on one mV scale', [-0.9, 0.9])}
                {view === 'difference' && <>{panel(w, 0, 130, [{ v: base, stroke: '#f97316', width: 2 }], 'removed component (the baseline)', [-0.9, 0.9])}{panel(w, 140, 130, [{ v: output.map((v, i) => v - (fx.detection.out[i] ?? 0)), stroke: 'var(--purple)' }], 'residual vs the recommended 7 s output', [-0.2, 0.2])}</>}
                <text x={4} y={290} style={{ fill: 'var(--muted)', fontSize: 10 }}>mV</text>
                <TimeAxis x={x} y={276} t0={t0} t1={t1} n={5} ends />
              </>
            )
          }}
        </PlotBox>
        <Legend items={[{ label: 'input', colour: '#a3a3a3', shape: 'line' }, { label: 'baseline', colour: '#f97316', shape: 'line' }, { label: 'output', colour: 'var(--blue)', shape: 'line' }, { label: 'edge zone · half-window at each end', colour: '#ffe0b8', shape: 'box' }]} />
      </BlockCard>

      <ParamsCard>
        <ParamSelect wide label="method" info="How the slow baseline is estimated. A rolling median ignores short drops; a rolling mean is pulled into them." value={str(draft.method, 'rolling median')} options={['rolling median', 'rolling mean', 'linear', 'lowess']} onChange={v => setDraft('method', v)} testid="param-method" disabled={running} />
        <ParamSlider label="window" info="Width of the rolling baseline. Too short and it follows the drops (eats their depth); too long and slow drift survives." value={window_s} was={was} onChange={v => setDraft('window_s', v)} min={1} max={30} step={1} unit="s" rec={7} recNote="3 × longest expected event" testid="param-window_s" disabled={running} />
        <ParamSelect label="edges" info="How the window is padded at the ends of the span." value={str(draft.edges, 'reflect')} options={['reflect', 'nearest', 'constant']} onChange={v => setDraft('edges', v)} testid="param-edges" disabled={running} />
        <div className="wide" style={{ gridColumn: '1 / -1' }}>
          <Tiles items={[{ k: 'variance removed', v: `${variance} %` }, { k: 'residual drift', v: `${drift} µV/s` }, { k: 'edge samples', v: `${window_s} s × 2`, tone: 'amber' }]} />
          {window_s < 3.4 ? <Callout tone="red" style={{ marginTop: 10 }}>window {window_s} s &lt; 2 × event length · this eats drop depth</Callout> : <Callout tone="amber" style={{ marginTop: 10 }}>window &lt; 2 × event length starts eating drop depth</Callout>}
        </div>
      </ParamsCard>

      <div className="bx-row2 span2">
      <BlockCard title="Try other windows" info="The same stretch with other windows. Click one to set it (a draft until Apply)." actions={<span className="mono muted" style={{ fontSize: 10.5 }}>same stretch · click to set</span>} testid="try-windows">
        <div className="bx-try">
          {fx.tryWindows.map(tw => {
            const b = rolling(input, Math.round(tw.window * PTS_PER_S / 2))
            const o = input.map((v, i) => v - b[i]).filter((_, i) => i % 2 === 0)
            const on = tw.window === window_s
            return (
              <button key={tw.window} className={`bx-try-card${on ? ' on' : ''}`} onClick={() => setDraft('window_s', tw.window)} data-testid={`try-window-${tw.window}`} disabled={running}>
                <b>{tw.window} s</b>
                <MiniTrace values={o} yDomain={[-0.45, 0.35]} width="100%" height={70} stroke={on ? 'var(--blue)' : 'var(--text-2)'} ground="grey" />
                <span className="mono muted">{tw.caption}</span>
              </button>
            )
          })}
        </div>
      </BlockCard>

      <BlockCard title="What this change does downstream" info="Each downstream stage re-run on the cached span with the draft window. Nothing is written until Apply." actions={<Chip tone="amber" size="sm">preview on cached span</Chip>} testid="downstream-preview">
        <div className="bx-table">
          {fx.downstream.map((r, i) => (
            <div key={i} className="bx-tr"><span className="mono muted">{r.stage}</span><span>{r.metric}</span><span className="mono muted">{window_s === was ? r.after.split(' ')[0] : r.before}</span><span className="mono">→</span><b className={`mono${r.better ? ' t-green' : ''}`}>{r.after}</b></div>
          ))}
        </div>
        <div className="mono muted" style={{ fontSize: 10.5, marginTop: 8 }}>previews run on the cached span only · nothing is written until Apply</div>
      </BlockCard>
      </div>
    </div>
  )
}
