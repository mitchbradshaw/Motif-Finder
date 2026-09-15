/* Matrix profile, a Signal → Scores block page (frame chain-7): the signal with the subsequence length drawn to scale,
 * one worked distance profile, the profile against its surrogate p5 / p95, the value distribution against the surrogate,
 * m against the null, parameters, top locations (click to centre panels 1–3) and the cost with the HPC hand-off (P4). */
import { useState } from 'react'
import { EnvelopePath, TimeAxis } from '../../../charts/primitives'
import { makeX, makeY } from '../../../charts/scale'
import { scaleLinear } from 'd3'
import { Button, Callout, InfoTip, Legend, Seg, recordDemoWrite } from '../../../kit'
import { navigate } from '../../../state'
import { useToast } from '../../../shell/Toast'
import { writeHpcJob } from '../parts'
import { BlockCard, ParamSelect, ParamSlider, ParamsCard, PlotBox, Tiles, num, str, type BlockProps } from './common'

const H = 3600
export function MatrixProfileBlock({ fx, draft, setDraft, bundle, running, index, st, actions }: BlockProps) {
  const toast = useToast()
  const [sel, setSel] = useState('M1')
  const m = num(draft.m_s, 600)
  const mp = fx.mp
  const top = mp.top.find(t => t.id === sel) ?? mp.top[0]
  const t0 = bundle.source.t0_s, t1 = bundle.source.t1_s
  const hpcDone = !!st.hpcJob
  const axis = (w: number, y: number) => { const x = makeX(t0, t1, w, 40, 10); const ticks = scaleLinear().domain([t0 / H, t1 / H]).ticks(6); return <g className="time-axis">{ticks.map(hh => <text key={hh} x={x(hh * H)} y={y} textAnchor="middle" style={{ fontSize: 10, fill: 'var(--muted)' }}>{hh.toFixed(2)} h</text>)}</g> }
  const insertThreshold = () => {
    const n = st.steps.length
    if (st.steps[index + 1]?.block !== 'demo.threshold') actions.insert(index + 1, 'demo.threshold')
    toast.push({ text: `inserted Threshold to spans as ${String(index + 2).padStart(2, '0')}${index + 1 < n ? '' : ' · terminal becomes SpanSet'}` })
    navigate(`analyse/block/${index + 1}?template=${st.template}`)
  }
  return (
    <div className="bx-grid mp">
      <div className="bx-col">
        <BlockCard title="1 · Signal, subsequence length to scale" info="The query subsequence (blue) is m long, to scale; grey is its exclusion zone ± m/2; green is its nearest neighbour." sub={<span className="mono muted" style={{ fontSize: 10.5 }}>query at {top.t_h.toFixed(2)} h{top.nn_h !== null ? ` · best match at ${top.nn_h.toFixed(2)} h` : ' · a discord has no close match'}</span>} testid="block-process">
          <PlotBox height={120} testid="mp-signal">
            {(w, h) => {
              const x = makeX(t0, t1, w, 40, 10); const y = makeY(-0.5, 0.45, h - 16, 6, 4)
              const band = (at: number, col: string, fill: string) => <rect x={x(at * H)} y={6} width={Math.max(3, x(at * H + m) - x(at * H))} height={h - 26} fill={fill} stroke={col} />
              return (
                <>
                  <rect x={x(top.t_h * H - m / 2)} y={6} width={x(top.t_h * H + m * 1.5) - x(top.t_h * H - m / 2)} height={h - 26} fill="rgba(107,114,128,0.12)" />
                  {band(top.t_h, 'var(--blue)', 'rgba(10,132,255,0.2)')}
                  {top.nn_h !== null && band(top.nn_h, 'var(--green)', 'rgba(34,160,107,0.18)')}
                  <EnvelopePath t={mp.signal.t} v={mp.signal.v} x={x} y={y} stroke="var(--text)" />
                  <text x={4} y={14} style={{ fontSize: 10, fill: 'var(--muted)' }}>mV</text><text x={4} y={26} style={{ fontSize: 10, fill: 'var(--muted)' }}>+0.4</text><text x={4} y={h - 20} style={{ fontSize: 10, fill: 'var(--muted)' }}>−0.4</text>
                  <text x={x(top.t_h * H)} y={h - 4} style={{ fontSize: 10, fill: 'var(--blue-600)' }}>query · m = {m} s</text>
                  {top.nn_h !== null && <text x={x(top.nn_h * H)} y={h - 4} style={{ fontSize: 10, fill: '#15794f' }}>nearest neighbour · d {top.d}</text>}
                </>
              )
            }}
          </PlotBox>
        </BlockCard>
        <BlockCard title="2 · Distance profile of the query" info="z-normalised Euclidean distance from the query to every other subsequence. Its minimum outside the trivial-match zone becomes the profile value at the query." sub={<span className="mono muted" style={{ fontSize: 10.5 }}>z-normalised Euclidean distance to every other subsequence</span>} testid="mp-distance">
          <PlotBox height={100}>
            {(w, h) => {
              const x = makeX(t0, t1, w, 40, 10); const y = makeY(0, 16, h - 8, 6, 4)
              const d = mp.profile.v.map((v, i) => { const hh = mp.profile.t[i] / H; return 10 + (v - 8) * 0.5 - (top.nn_h !== null ? 7.5 * Math.exp(-(((hh - top.nn_h) / 0.08) ** 2)) : 0) })
              return (
                <>
                  <rect x={x(top.t_h * H - m)} y={4} width={x(top.t_h * H + m) - x(top.t_h * H - m)} height={h - 12} fill="rgba(107,114,128,0.15)" /><text x={x(top.t_h * H + m) + 4} y={12} style={{ fontSize: 10, fill: 'var(--muted)' }}>trivial matches</text>
                  <EnvelopePath t={mp.profile.t} v={d} x={x} y={y} stroke="#6d5bd0" />
                  {[0, 8, 16].map(v => <text key={v} x={30} y={y(v) + 3} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v}</text>)}
                  {top.nn_h !== null && <><circle cx={x(top.nn_h * H)} cy={y(2.4)} r={3.5} fill="var(--green)" /><text x={x(top.nn_h * H) + 6} y={y(2.4) + 3} style={{ fontSize: 10, fill: '#15794f' }}>min {top.d} → this value becomes the profile at {top.t_h.toFixed(2)} h</text></>}
                </>
              )
            }}
          </PlotBox>
        </BlockCard>
        <BlockCard title="3 · Matrix profile = the minimum of every distance profile" info="The block's output: one Scores value per second. Dips below the surrogate p5 are motifs; peaks above p95 are discords." sub={<span className="mono muted" style={{ fontSize: 10.5 }}>output · Scores · one value per second</span>} testid="mp-profile">
          <PlotBox height={150}>
            {(w, h) => {
              const x = makeX(t0, t1, w, 40, 10); const y = makeY(0, 15, h - 20, 16, 4)
              const marks = [{ l: 'M1a', t: 7.2, c: 'var(--green)' }, { l: 'D1', t: 8.9, c: 'var(--red)' }, { l: 'M1b', t: 10.1, c: 'var(--green)' }, { l: 'M2', t: 11.2, c: 'var(--green)' }]
              return (
                <>
                  <line x1={40} x2={w - 10} y1={y(12)} y2={y(12)} stroke="var(--muted-2)" /><text x={w - 12} y={y(12) - 3} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>p95</text>
                  <rect x={40} y={y(5.3)} width={w - 50} height={y(4.7) - y(5.3)} fill="rgba(107,114,128,0.18)" /><text x={w - 12} y={y(5) + 12} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>surrogate p5</text>
                  {marks.map(k => <g key={k.l}><line x1={x(k.t * H)} x2={x(k.t * H)} y1={14} y2={h - 20} stroke={k.c} strokeOpacity={0.6} /><rect x={x(k.t * H) - 13} y={2} width={26} height={12} rx={2} fill={k.c} /><text x={x(k.t * H)} y={11} textAnchor="middle" style={{ fontSize: 9, fill: '#fff', fontWeight: 600 }}>{k.l}</text></g>)}
                  <EnvelopePath t={mp.profile.t} v={mp.profile.v} x={x} y={y} stroke="var(--blue)" width={1.3} />
                  {[0, 5, 10, 15].map(v => <text key={v} x={30} y={y(v) + 3} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v}</text>)}
                  {axis(w, h - 4)}
                </>
              )
            }}
          </PlotBox>
        </BlockCard>
        <div className="bx-row2">
          <BlockCard title="Profile values vs surrogate" info="How many profile values fall below the surrogate's p5. Under the null 5 % would." sub={<span className="mono muted" style={{ fontSize: 10.5 }}>{mp.below_p5}</span>} testid="mp-hist">
            <PlotBox height={150}>
              {(w, h) => {
                const bins = 24; const x = scaleLinear().domain([0, 16]).range([30, w - 10]); const bw = (w - 40) / bins
                const real = Array.from({ length: bins }, (_, i) => { const c = (i + 0.5) * 16 / bins; return Math.round(900 * Math.exp(-(((c - 8.4) / 1.6) ** 2)) + (c < 5 ? 40 : 0)) })
                const sur = Array.from({ length: bins }, (_, i) => { const c = (i + 0.5) * 16 / bins; return Math.round(950 * Math.exp(-(((c - 8.8) / 1.5) ** 2))) })
                const y = scaleLinear().domain([0, 1000]).range([h - 20, 8])
                return (
                  <>
                    {real.map((r, i) => <rect key={i} x={30 + i * bw + 0.5} y={y(r)} width={bw - 1} height={y(0) - y(r)} fill={(i + 0.5) * 16 / bins < 5 ? 'var(--green)' : '#60a5fa'} />)}
                    <path d={sur.map((s, i) => `${i ? 'L' : 'M'}${(30 + i * bw).toFixed(1)} ${y(s).toFixed(1)}H${(30 + (i + 1) * bw).toFixed(1)}`).join('')} fill="none" stroke="var(--text)" />
                    <line x1={x(5)} x2={x(5)} y1={8} y2={h - 20} stroke="var(--muted)" /><text x={x(5) - 4} y={16} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>surrogate p5</text>
                    {[0, 4, 8, 12, 16].map(v => <text key={v} x={x(v)} y={h - 6} textAnchor="middle" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v}</text>)}
                  </>
                )
              }}
            </PlotBox>
            <Legend items={[{ label: 'real', colour: '#60a5fa' }, { label: 'surrogate', colour: 'var(--text)', shape: 'line' }, { label: 'below p5', colour: 'var(--green)' }]} />
          </BlockCard>
          <BlockCard title="Subsequence length vs null" info="Motif pairs below the surrogate p1 at six lengths, each with its own null. Click a length to set m (a draft until Apply)." sub={<span className="mono muted" style={{ fontSize: 10.5 }}>motif pairs below surrogate p1</span>} testid="mp-m-sweep">
            <PlotBox height={150}>
              {(w, h) => {
                const cw = (w - 40) / mp.mSweep.length; const y = scaleLinear().domain([0, 4]).range([h - 20, 8])
                return <>{[0, 1, 2, 3, 4].map(v => <text key={v} x={26} y={y(v) + 3} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v}</text>)}{mp.mSweep.map((s, i) => { const on = s.m === m; const x0 = 34 + i * cw; return <g key={s.m} onClick={() => setDraft('m_s', s.m)} style={{ cursor: 'pointer' }} data-testid={`m-${s.m}`}><rect x={x0 + cw / 2 - 16} y={y(s.null)} width={32} height={y(0) - y(s.null)} fill="#e5e7eb" /><rect x={x0 + cw / 2 - 11} y={y(s.real)} width={22} height={y(0) - y(s.real)} fill={on ? 'var(--blue)' : '#9db8e8'} /><text x={x0 + cw / 2} y={h - 6} textAnchor="middle" style={{ fontSize: 10, fill: on ? 'var(--blue-600)' : 'var(--muted)', fontWeight: on ? 600 : 400 }}>{s.m}</text></g> })}</>
              }}
            </PlotBox>
            <Legend items={[{ label: 'real', colour: 'var(--blue)' }, { label: 'null 95 % range', colour: '#e5e7eb' }]} />
          </BlockCard>
        </div>
      </div>

      <div className="bx-col">
        <ParamsCard note={<span className="mono muted" style={{ fontSize: 10.5 }}>changing any re-runs {String(index + 1).padStart(2, '0')}</span>}>
          <ParamSlider wide label="subsequence length m" info="The motif length the profile compares, in seconds. 3 × the longest expected event is recommended." value={m} onChange={v => setDraft('m_s', v)} min={60} max={1800} step={60} unit="s" rec={540} recNote="3 × longest expected event" testid="param-m_s" disabled={running} />
          <ParamSelect label="exclusion zone" info="Matches closer than this to the query are trivial and ignored." value={str(draft.exclusion, 'm / 2')} options={['m / 2', 'm / 4', 'm']} onChange={v => setDraft('exclusion', v)} testid="param-exclusion" disabled={running} />
          <ParamSelect label="top-k reported" info="How many motif pairs and discords are marked." value={str(draft.topk, '3 motifs · 1 discord')} options={['3 motifs · 1 discord', '5 motifs · 2 discords', '1 motif · 1 discord']} onChange={v => setDraft('topk', v)} testid="param-topk" disabled={running} />
          <div className="bx-param"><div className="lab"><span>normalisation</span><InfoTip title="normalisation">z-norm compares shape; raw compares amplitude too. The picture is never normalised (D5).</InfoTip></div><Seg options={[{ value: 'z-norm', label: 'z-norm' }, { value: 'raw', label: 'raw' }]} value={str(draft.normalise, 'z-norm')} onChange={v => setDraft('normalise', v)} size="sm" testid="param-normalise" /></div>
          <ParamSelect label="algorithm" info="STUMP is exact; SCRIMP++ is approximate and faster." value={str(draft.algorithm, 'STUMP · exact')} options={['STUMP · exact', 'SCRIMP++ · approximate', 'STUMPY']} onChange={v => setDraft('algorithm', v)} testid="param-algorithm" disabled={running} />
          <ParamSelect label="surrogate" info="The null the profile is judged against." value={str(draft.surrogate, 'IAAFT · 200×')} options={['IAAFT · 200×', 'phase-rand · 200×', 'circular shift · 200×']} onChange={v => setDraft('surrogate', v)} testid="param-surrogate" disabled={running} />
          <ParamSelect label="null reference" info="Which surrogate percentiles are drawn." value={str(draft.nullref, 'p5 / p95')} options={['p5 / p95', 'p1 / p99']} onChange={v => setDraft('nullref', v)} testid="param-nullref" disabled={running} />
        </ParamsCard>
        <BlockCard title="Top locations" actions={<span className="mono muted" style={{ fontSize: 10.5 }}>click to centre panels 1–3</span>} testid="mp-top">
          <div className="bx-table">
            <div className="bx-tr four head"><span /><span>at</span><span>distance</span><span>vs null</span></div>
            {mp.top.map(t => (
              <button key={t.id} className={`bx-tr four btn-row${sel === t.id ? ' on' : ''}`} onClick={() => setSel(t.id)} data-testid={`top-${t.id}`}>
                <span className={`bx-mark ${t.id.startsWith('D') ? 'd' : 'm'}`}>{t.id}</span><span className="mono">{t.at}</span><span className="mono">{t.d}</span><span className="mono" style={{ color: t.sig ? '#15794f' : 'var(--muted)' }}>{t.p}</span>
              </button>
            ))}
          </div>
        </BlockCard>
        <BlockCard title="Cost" testid="mp-cost">
          <Tiles items={[{ k: 'this span', v: '≈ 4 min' }, { k: 'on disk', v: '0.2 MB' }, { k: 'whole channel', v: '6.4 h', tone: 'amber' }]} />
          <Callout tone="amber" style={{ marginTop: 8 }}>whole channel exceeds the local ceiling (20 min) → HPC</Callout>
          <div className="row" style={{ justifyContent: 'space-between', marginTop: 10 }}>
            <Button icon="file" onClick={() => { if (hpcDone) { navigate('jobs'); return } const j = writeHpcJob(st.template, String(index + 1).padStart(2, '0')); actions.patch({ hpcJob: j.id }); recordDemoWrite('analyse', 'slurm-from-block', { job: j.id }); toast.push({ text: `SLURM script created · ${j.id} added to Jobs`, action: { label: 'Open in Jobs', onClick: () => navigate('jobs') } }) }} testid="mp-slurm">{hpcDone ? 'Open in Jobs' : 'SLURM script'}</Button>
            <Button variant="primary" icon="plus" onClick={insertThreshold} testid="insert-threshold">Insert threshold →</Button>
          </div>
        </BlockCard>
      </div>
    </div>
  )
}
