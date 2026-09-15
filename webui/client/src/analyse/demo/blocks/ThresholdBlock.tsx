/* Threshold to spans in a demo chain (frame chain-7b, Scores → SpanSet, B10): the scores with a draggable cut and the
 * spans it makes, the scores over the null, spans vs cut for real and null, the spans produced, parameters, output and
 * what a SpanSet allows next. (The live threshold block page — against the bridge — is BlockPage.tsx.) */
import { EnvelopePath } from '../../../charts/primitives'
import { makeX, makeY } from '../../../charts/scale'
import { scaleLinear } from 'd3'
import { Button, KeyValue, recordDemoWrite, useNotWired } from '../../../kit'
import { navigate } from '../../../state'
import { useToast } from '../../../shell/Toast'
import { BlockCard, DragH, DragV, ParamSelect, ParamSlider, ParamsCard, PlotBox, num, str, type BlockProps } from './common'

const H = 3600
export function ThresholdBlock({ fx, draft, setDraft, bundle, running, st, actions }: BlockProps) {
  const toast = useToast()
  const notWired = useNotWired()
  const cut = num(draft.cut_sigma, 2.5)
  const sc = fx.threshold.scores
  const t0 = bundle.source.t0_s, t1 = bundle.source.t1_s
  const spans = sc.peaks.filter(p => 0.9 + 2.2 > cut + 0.1 * (p - 6)).map(p => ({ s: (p - 0.02) * H, e: (p + 0.02) * H }))
  const nSpans = Math.max(0, Math.round(5 * Math.exp(-(cut - 2.5) * 0.9)))
  const nullSpans = +(0.4 * Math.exp(-(cut - 2.5) * 1.6)).toFixed(1)
  const setCut = (v: number) => setDraft('cut_sigma', Math.max(1, Math.min(4, Math.round(v * 20) / 20)))
  const shown = fx.threshold.spans.slice(0, nSpans)
  return (
    <div className="bx-grid">
      <div className="bx-col">
        <BlockCard title="Scores with the cut" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>matrix profile discords · 6–12 h of CH4_A2 · drag the line</span>} testid="block-process">
          <PlotBox height={190} testid="threshold-scores">
            {(w, h) => {
              const x = makeX(t0, t1, w, 10, 10); const y = makeY(0, 3.6, 150, 6, 4)
              const ticks = scaleLinear().domain([6, 12]).ticks(4)
              return (
                <>
                  <EnvelopePath t={sc.t} v={sc.v} x={x} y={y} stroke="var(--text)" />
                  <DragH y={y(cut)} width={w} onValue={setCut} toValue={py => y.invert(py)} colour="var(--amber)" label={`${cut}σ${cut === 2.5 ? ' · recommended' : ''} · drag`} testid="threshold-line" />
                  {spans.slice(0, nSpans).map((s, i) => <rect key={i} x={x(s.s)} y={158} width={Math.max(5, x(s.e) - x(s.s))} height={7} fill="var(--green)" />)}
                  <text x={10} y={165} style={{ fontSize: 10, fill: 'var(--muted)' }}>spans</text>
                  {ticks.map(v => <text key={v} x={x(v * H)} y={h - 2} textAnchor="middle" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v} h</text>)}
                </>
              )
            }}
          </PlotBox>
        </BlockCard>
        <div className="bx-row2">
          <BlockCard title="Scores over the null" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>real vs 200 circular shifts</span>} testid="threshold-null">
            <PlotBox height={140}>
              {(w, h) => {
                const bins = 18; const x = scaleLinear().domain([0, 4.5]).range([10, w - 10]); const bw = (w - 20) / bins
                const real = Array.from({ length: bins }, (_, i) => { const c = (i + 0.5) * 4.5 / bins; return 100 * Math.exp(-(((c - 1) / 0.45) ** 2)) + (c > 2.6 ? 8 : 0) })
                const nul = Array.from({ length: bins }, (_, i) => { const c = (i + 0.5) * 4.5 / bins; return 98 * Math.exp(-(((c - 1) / 0.5) ** 2)) + 1 })
                const y = scaleLinear().domain([0, 110]).range([h - 26, 6])
                return <>{real.map((r, i) => <g key={i}><rect x={10 + i * bw + 1} y={y(r)} width={bw - 2} height={y(0) - y(r)} fill="#9db8e8" /><line x1={10 + i * bw + 2} x2={10 + (i + 1) * bw - 2} y1={y(nul[i])} y2={y(nul[i])} stroke="var(--text-2)" /></g>)}<DragV x={x(cut)} height={h - 26} onValue={setCut} toValue={px => x.invert(px)} colour="var(--amber)" label={`cut ${cut}σ`} testid="threshold-null-cut" /><text x={10} y={h - 8} style={{ fontSize: 10, fill: 'var(--text-2)' }}>expected false spans at this cut · {nullSpans} per run (null)</text></>
              }}
            </PlotBox>
          </BlockCard>
          <BlockCard title="Spans vs cut" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>each point is a full run of this stage</span>} testid="threshold-curve">
            <PlotBox height={140}>
              {(w, h) => {
                const x = scaleLinear().domain([1, 4]).range([10, w - 10]); const y = scaleLinear().domain([0, 40]).range([h - 26, 6])
                const cs = Array.from({ length: 31 }, (_, i) => 1 + i * 0.1)
                const line = (f: (c: number) => number) => cs.map((c, i) => `${i ? 'L' : 'M'}${x(c).toFixed(1)} ${y(f(c)).toFixed(1)}`).join('')
                return <><path d={line(c => 5 * Math.exp(-(c - 2.5) * 0.9))} fill="none" stroke="var(--blue)" strokeWidth={1.6} /><path d={line(c => 0.4 * Math.exp(-(c - 2.5) * 1.6))} fill="none" stroke="var(--muted)" /><DragV x={x(cut)} height={h - 26} onValue={setCut} toValue={px => x.invert(px)} colour="var(--amber)" label="" testid="threshold-curve-cut" /><text x={10} y={h - 8} style={{ fontSize: 10, fill: 'var(--text-2)' }}>{nSpans} spans · null {nullSpans} [0–2] · {nullSpans ? Math.round(nSpans / nullSpans) : '—'}× null · cut 1σ → 4σ</text></>
              }}
            </PlotBox>
          </BlockCard>
        </div>
        <BlockCard title="Spans produced" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>{nSpans} · after min duration and merge</span>} testid="spans-table">
          <div className="bx-table">
            <div className="bx-tr four eq head"><span>start</span><span>duration</span><span>peak score</span><span>merged from</span></div>
            {shown.map((r, i) => <div key={i} className="bx-tr four eq"><span className="mono">{r.start}</span><span className="mono">{r.duration}</span><span className="mono">{r.peak}</span><span className="mono">{r.merged}</span></div>)}
            {!shown.length && <div className="mono muted small">no span crosses {cut}σ</div>}
          </div>
          <div className="mono muted" style={{ fontSize: 10.5, marginTop: 6 }}>1–{shown.length} of {nSpans}</div>
        </BlockCard>
      </div>
      <div className="bx-col">
        <ParamsCard note="">
          <ParamSelect wide label="keep scores" info="Spans are where the score is above (discords) or below (motifs) the cut." value={str(draft.keep, 'above the cut')} options={['above the cut', 'below the cut']} onChange={v => setDraft('keep', v)} testid="param-keep" disabled={running} />
          <ParamSlider wide label="cut" info="In σ of this run's scores. The recommended value comes from Settings › Analysis defaults." value={cut} onChange={setCut} min={1} max={4} step={0.05} unit="σ" rec={2.5} recNote="recommended (Settings › Analysis defaults)" testid="param-cut_sigma" disabled={running} />
          <ParamSlider label="min duration" info="Shorter crossings are not spans." value={num(draft.min_duration_s, 60)} onChange={v => setDraft('min_duration_s', v)} min={0} max={300} step={10} unit="s" rec={60} testid="param-min_duration_s" disabled={running} />
          <ParamSlider label="merge gap" info="Spans closer than this merge." value={num(draft.merge_gap_s, 30)} onChange={v => setDraft('merge_gap_s', v)} min={0} max={120} step={5} unit="s" rec={30} testid="param-merge_gap_s" disabled={running} />
          <ParamSelect wide label="score scale" info="The unit the cut is expressed in." value={str(draft.scale, "σ of this run's scores")} options={["σ of this run's scores", 'raw distance']} onChange={v => setDraft('scale', v)} disabled={running} />
        </ParamsCard>
        <BlockCard title="Output" sub={<span className="mono muted">{nSpans}</span>} testid="threshold-output">
          <KeyValue items={[{ k: 'spans', v: String(nSpans), strong: true }, { k: 'null', v: `${nullSpans} [0–2]`, strong: true }, { k: '× null', v: nullSpans ? `${Math.round(nSpans / nullSpans)}×` : '—', strong: true }, { k: 'coverage', v: `${(nSpans * 0.02).toFixed(1)} h of 6 h`, strong: true }]} lines />
        </BlockCard>
        <BlockCard title="Next" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>SpanSet allows</span>} testid="next-card">
          <div className="bx-next">
            <Button block onClick={() => { actions.save(st.name, 'v2'); toast.push({ text: `${st.name} saved as a detection template (in memory)` }) }} testid="next-save-template">Save template</Button>
            <Button block onClick={() => { recordDemoWrite('analyse', 'analyse-events', { spans: nSpans }); navigate('analyse/interrogation') }} testid="next-analyse-events">Analyse events →</Button>
            <Button block variant="primary" disabled={!nSpans} disabledReason="no spans at this cut" onClick={() => { recordDemoWrite('analyse', 'pass-to-review', { spans: nSpans }); toast.push({ text: `${nSpans} spans passed to Review (in memory)` }); navigate('review/queue/q-12') }} testid="next-pass-review">Pass {nSpans} to Review →</Button>
            <Button block variant="ghost" onClick={() => notWired('export the spans as CSV')}>Export spans</Button>
          </div>
        </BlockCard>
      </div>
    </div>
  )
}
