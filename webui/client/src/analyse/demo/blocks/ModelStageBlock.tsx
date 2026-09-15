/* Model stage (frame chain-8, Model + WindowSet → Scores, B13): windows scored over the signal per class, the model card
 * (registered models only), one class's scores against a label-shuffle null with the calibration cut, the top windows,
 * parameters, output and what Scores allow next — including inserting a Threshold with the calibration as its cut. */
import { useState } from 'react'
import { EnvelopePath } from '../../../charts/primitives'
import { makeX, makeY } from '../../../charts/scale'
import { scaleLinear } from 'd3'
import { Button, KeyValue, recordDemoWrite } from '../../../kit'
import { MODELS } from '../../../fixtures/canon'
import { navigate } from '../../../state'
import { useToast } from '../../../shell/Toast'
import { BlockCard, ParamSelect, ParamsCard, PlotBox, str, type BlockProps } from './common'

const H = 3600
export function ModelStageBlock({ fx, draft, setDraft, bundle, running, st, index, actions }: BlockProps) {
  const toast = useToast()
  const md = fx.model
  const [cls, setCls] = useState(str(draft.pass_class, 'spike-train'))
  const ci = Math.max(0, md.classes.findIndex(c => c.name === cls))
  const t0 = bundle.source.t0_s, t1 = bundle.source.t1_s
  const model = str(draft.model, 'cnn_windows_v2 · manual · v2')
  const cal = [0.62, 0.71, 0.4, 0.55][ci]
  const above = md.tracks[ci].filter(v => v >= cal).length
  const insertThreshold = () => {
    const next = st.steps[index + 1]
    if (next?.block === 'demo.threshold') actions.setParam(next.uid, 'cut', cal)
    else actions.insert(index + 1, 'demo.threshold')
    recordDemoWrite('analyse', 'insert-threshold-from-calibration', { cut: cal, class: cls })
    toast.push({ text: `Threshold ${String(index + 2).padStart(2, '0')} · cut ${cal} from ${cls} calibration` })
    navigate(`analyse/chain?template=${st.template}`)
  }
  return (
    <div className="bx-grid">
      <div className="bx-col">
        <BlockCard title="Windows scored over the signal" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>72 windows · 600 s · stride 300 s · 6–12 h of CH4_A2</span>} testid="block-process">
          <PlotBox height={200} testid="model-tracks">
            {(w, h) => {
              const x = makeX(t0, t1, w, 70, 10)
              const sig = fx.mp.signal
              const ys = makeY(-0.6, 0.45, 36, 2, 2)
              const starts = Array.from({ length: 72 }, (_, i) => t0 + i * 300 + 300)
              return (
                <>
                  <EnvelopePath t={sig.t} v={sig.v} x={x} y={ys} stroke="var(--text)" />
                  <text x={0} y={44} style={{ fontSize: 10, fill: 'var(--muted)' }}>signal</text>
                  {starts.map((s, i) => <line key={i} x1={x(s)} x2={x(s)} y1={46} y2={50} stroke="var(--muted-2)" />)}
                  {md.classes.map((c, k) => {
                    const top = 58 + k * 34; const y = scaleLinear().domain([0, 1]).range([top + 26, top])
                    return <g key={c.name} opacity={cls === c.name ? 1 : 0.55} onClick={() => setCls(c.name)} style={{ cursor: 'pointer' }} data-testid={`track-${c.name}`}><path d={md.tracks[k].map((v, i) => `${i ? 'L' : 'M'}${x(starts[i]).toFixed(1)} ${y(v).toFixed(1)}`).join('')} fill="none" stroke={c.colour} strokeWidth={cls === c.name ? 1.8 : 1.2} /><text x={0} y={top + 22} style={{ fontSize: 10, fill: c.colour }}>{c.name}</text></g>
                  })}
                  {[6, 7.5, 9, 10.5, 12].map(v => <text key={v} x={x(v * H)} y={h - 2} textAnchor="middle" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v} h</text>)}
                </>
              )
            }}
          </PlotBox>
        </BlockCard>
        <div className="bx-row2">
          <BlockCard title="Model" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>registered only · picked in Parameters</span>} testid="model-card">
            <KeyValue dense items={md.card.map(([k, v]) => ({ k, v: k === 'name' ? model : v }))} labelWidth={96} />
            <Button variant="link" icon="external" onClick={() => navigate('models/registry')} testid="open-in-models">Open in Models</Button>
          </BlockCard>
          <BlockCard title={`${cls} scores vs null`} sub={<span className="mono muted" style={{ fontSize: 10.5 }}>label-shuffle model, same windows</span>} testid="model-null">
            <PlotBox height={140}>
              {(w, h) => {
                const bw = (w - 20) / md.hist.length; const y = scaleLinear().domain([0, 48]).range([h - 26, 8]); const x = scaleLinear().domain([0, 1]).range([10, w - 10])
                return <>{md.hist.map((c, i) => <g key={i}><rect x={10 + i * bw + 1} y={y(c)} width={bw - 2} height={y(0) - y(c)} fill="#b9b4f0" /><line x1={10 + i * bw + 1} x2={10 + (i + 1) * bw - 1} y1={y(md.nullHist[i])} y2={y(md.nullHist[i])} stroke="var(--text-2)" /></g>)}<line x1={x(cal)} x2={x(cal)} y1={4} y2={h - 26} stroke="var(--amber)" strokeWidth={1.6} /><text x={x(cal) + 4} y={14} style={{ fontSize: 10, fill: '#b45309' }}>{cal}</text><text x={10} y={h - 8} style={{ fontSize: 10, fill: 'var(--text-2)' }}>above {cal} · {above} windows · null expects 0.3 · score 0 → 1</text></>
              }}
            </PlotBox>
          </BlockCard>
        </div>
        <BlockCard title="Top windows" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>by {cls} score</span>} testid="top-windows">
          <div className="bx-table">
            <div className="bx-tr five head"><span>window</span><span>time</span><span>top class</span><span>score</span><span>2nd</span></div>
            {md.top.map(r => <div key={r[0]} className="bx-tr five"><span className="mono">{r[0]}</span><span className="mono">{r[1]}</span><span>{r[2]}</span><span className="mono">{r[3]}</span><span className="mono">{r[4]}</span></div>)}
          </div>
        </BlockCard>
      </div>
      <div className="bx-col">
        <ParamsCard note="">
          <ParamSelect wide label="model" info="Only registered models can be used for detection (Models › Registry)." value={model} options={MODELS.registered.map(m => `${m.name} · v${m.version}`)} onChange={v => setDraft('model', v)} testid="param-model" disabled={running} />
          <div className="bx-param wide" style={{ gridColumn: '1 / -1' }}><div className="lab"><span>windows from</span></div><div className="bx-static">01 Sliding windows · 600 s · stride 300 s</div></div>
          <ParamSelect wide label="class to pass on" info="The class whose score track the next stage thresholds; all tracks are kept." value={cls} options={md.classes.map(c => c.name)} onChange={v => { setCls(v); setDraft('pass_class', v) }} testid="param-pass_class" disabled={running} />
          <ParamSelect label="batch · device" info="Windows per batch on this machine." value={str(draft.batch_device, '64 · this machine')} options={['64 · this machine', '128 · this machine', '32 · this machine']} onChange={v => setDraft('batch_device', v)} disabled={running} />
          <div className="bx-param"><div className="lab"><span>recommended cut for {String(index + 2).padStart(2, '0')}</span></div><div className="bx-static">{cal} · from calibration</div></div>
        </ParamsCard>
        <BlockCard title="Output" sub={<span className="mono muted">Scores</span>} testid="model-output">
          <KeyValue items={[{ k: 'tracks', v: '4 classes · 72 windows', strong: true }, { k: 'estimate', v: '≈ 40 s local · under 20 min', strong: true }, { k: 'disk', v: '0.1 MB scores', strong: true }, { k: 'null', v: 'label shuffle 200×', strong: true }]} lines />
        </BlockCard>
        <BlockCard title="Next" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>Scores allows</span>} testid="next-card">
          <div className="bx-next">
            <Button block onClick={() => { actions.save(st.name, 'v2'); toast.push({ text: `${st.name} saved (in memory)` }) }}>Save template</Button>
            <Button block icon="external" onClick={() => navigate('models/registry')}>Open model in Models</Button>
            <Button block variant="primary" onClick={insertThreshold} testid="insert-threshold-cal">Insert Threshold · {cal} →</Button>
          </div>
        </BlockCard>
      </div>
    </div>
  )
}
