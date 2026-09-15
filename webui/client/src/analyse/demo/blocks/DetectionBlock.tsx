/* 04 Drop detection (frame chain-4): detections in context coloured by shape family, the dropped candidates as
 * outlines, what dedupe and the floors removed, parameters with recommended markers, each kept detection as a card on a
 * shared y (≤ 10, P8), and the hand-offs a SpanSet allows (§6.5). */
import { useState } from 'react'
import { EnvelopePath, TimeAxis } from '../../../charts/primitives'
import { makeX, makeY } from '../../../charts/scale'
import { Button, Callout, Checkbox, Chip, Dropdown, Field, Icon, InfoTip, Legend, MiniTrace, Pager, TextField, recordDemoWrite, usePagedList, useNotWired } from '../../../kit'
import { FAMILY_COLOURS } from '../../../fixtures/canon'
import { navigate } from '../../../state'
import { useToast } from '../../../shell/Toast'
import { demoStepError } from '../../../api/analyse'
import { nameProblem } from '../parts'
import { BlockCard, ParamSelect, ParamSlider, ParamsCard, PlotBox, Tiles, num, str, type BlockProps } from './common'

const famFill = (f: string | null) => (f ? `${FAMILY_COLOURS[f]}55` : 'rgba(156,163,175,0.35)')

export function DetectionBlock({ fx, draft, setDraft, st, step, bundle, running, actions }: BlockProps) {
  const toast = useToast()
  const notWired = useNotWired()
  const [showDropped, setShowDropped] = useState(true)
  const [colourBy, setColourBy] = useState('shape family')
  const [sort, setSort] = useState('match score')
  const [selected, setSelected] = useState<string | null>('M15')
  const [tplName, setTplName] = useState(st.name)
  const minDepth = num(draft.min_depth_mv, 0.1), minDur = num(draft.min_duration_s, 0.6), merge = num(draft.merge_window_s, 2), tol = num(draft.trough_tol_sigma, 0.5)
  const trough = +(1.2 / tol).toFixed(1)
  const kept = fx.kept.filter(d => d.depth >= minDepth && d.dur >= minDur)
  const sorted = [...kept].sort((a, b) => sort === 'time' ? a.at - b.at : sort === 'depth' ? b.depth - a.depth : b.score - a.score)
  const pg = usePagedList(sorted, 10)
  const t0 = bundle.source.t0_s, t1 = bundle.source.t1_s
  const tr = fx.detection
  const err = demoStepError({ ...step, params: draft })
  const failedHere = st.failure?.uid === step.uid
  const problem = nameProblem(tplName)
  const removed = [{ ...fx.removed[0], n: kept.length, label: `${kept.length} kept` }, ...fx.removed.slice(1)]
  const total = removed.reduce((a, r) => a + r.n, 0)

  const handoff = (what: string) => { recordDemoWrite('analyse', what, { template: st.name, spans: kept.length }); }
  return (
    <div className="bx-grid">
      <BlockCard title={<><span className="mono muted" style={{ fontWeight: 400, fontSize: 12 }}>04</span> Drop detection <span className="sig">Encoding → SpanSet</span></>} testid="block-process" info="Every kept detection in context on the detrended signal; outlined boxes are the candidates dedupe and the floors removed."
        actions={<span className="row" style={{ gap: 8 }}><Checkbox checked={showDropped} onChange={setShowDropped} label={`show dropped (${fx.dropped.length})`} testid="show-dropped" /><Dropdown prefix="colour" value={colourBy} onChange={setColourBy} options={[{ value: 'shape family', label: 'shape family' }, { value: 'match score', label: 'match score' }, { value: 'none', label: 'none' }]} testid="colour-by" /></span>}>
        {(failedHere || err) && <Callout tone="red" style={{ marginBottom: 8 }} testid="detection-error" action={err ? <Button size="sm" onClick={() => setDraft('merge_window_s', trough)} testid="fix-merge">Set merge window to {trough} s</Button> : undefined}>{failedHere && st.failure ? `${st.failure.run} failed here · ` : 'this would fail · '}{err ?? st.failure?.message}</Callout>}
        <PlotBox height={210} testid="detection-context">
          {(w, h) => {
            const x = makeX(t0, t1, w, 40, 8)
            const y = makeY(-0.45, 0.25, h - 22, 8, 4)
            return (
              <>
                {[0.2, 0, -0.2, -0.4].map(v => <g key={v}><line x1={40} x2={w - 8} y1={y(v)} y2={y(v)} stroke={v === 0 ? 'var(--grey-200)' : 'transparent'} /><text x={34} y={y(v) + 3} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>{v > 0 ? '+' : v < 0 ? '−' : ''}{Math.abs(v).toFixed(1)}</text></g>)}
                <text x={34} y={10} textAnchor="end" style={{ fontSize: 10, fill: 'var(--muted)' }}>mV</text>
                {showDropped && fx.dropped.map(([a, d], i) => <rect key={i} x={x(t0 + a)} y={y(0.22)} width={Math.max(3, x(t0 + a + d) - x(t0 + a))} height={y(-0.42) - y(0.22)} fill="none" stroke="var(--text-2)" strokeWidth={0.8} />)}
                {kept.map(d => {
                  const fill = colourBy === 'none' ? 'rgba(10,132,255,0.15)' : colourBy === 'match score' ? `rgba(10,132,255,${(d.score - 0.5).toFixed(2)})` : famFill(d.family)
                  const cap = colourBy === 'shape family' ? (d.family ? FAMILY_COLOURS[d.family] : '#9ca3af') : 'var(--blue)'
                  const on = selected === d.id
                  return (
                    <g key={d.id} onClick={() => setSelected(d.id)} style={{ cursor: 'pointer' }} data-testid={`kept-band-${d.id}`}>
                      <rect x={x(t0 + d.at - 0.3)} y={y(0.22)} width={x(t0 + d.at + d.dur + 0.3) - x(t0 + d.at - 0.3)} height={y(-0.42) - y(0.22)} fill={fill} stroke={on ? 'var(--blue)' : 'none'} strokeWidth={on ? 2 : 0} />
                      <rect x={x(t0 + d.at - 0.3)} y={y(0.22) - 3} width={x(t0 + d.at + d.dur + 0.3) - x(t0 + d.at - 0.3)} height={3} fill={cap} />
                      <text x={x(t0 + d.at - 0.2)} y={y(0.22) + 11} style={{ fontSize: 9.5, fill: 'var(--text-2)' }}>{d.id}</text>
                    </g>
                  )
                })}
                <EnvelopePath t={tr.t} v={tr.out} x={x} y={y} stroke="var(--text)" width={1.2} />
                <TimeAxis x={x} y={h - 20} t0={t0} t1={t1} n={5} ends />
              </>
            )
          }}
        </PlotBox>
        <Legend items={[{ label: 'F-03 sharkfin', colour: `${FAMILY_COLOURS['F-03']}88` }, { label: 'F-07 slow drift', colour: `${FAMILY_COLOURS['F-07']}88` }, { label: 'no family yet', colour: 'rgba(156,163,175,0.5)' }, { label: 'dropped', colour: '#fff', shape: 'box' }]} />
        <div className="bx-removed" data-testid="removed-breakdown">
          <div className="row" style={{ gap: 6 }}><b>{total} raw → {kept.length} kept</b><span className="mono muted" style={{ fontSize: 10.5 }}>what was removed</span><InfoTip title="What was removed">Dedupe is the parameter that most changes the count: 11 of the 23 raw detections were shifted copies of a better-framed drop.</InfoTip></div>
          <div className="bar">{removed.map(r => <i key={r.label} style={{ flex: r.n, background: r.colour }} title={r.label} />)}</div>
          <Legend items={removed.map(r => ({ label: r.label, colour: r.colour }))} />
        </div>
      </BlockCard>

      <ParamsCard note={<><span className="bx-rec-bar" /> recommended</>}>
        <ParamSlider label="minimum depth" info="A drop shallower than this is not kept. The recommended value is the recording's noise floor." value={minDepth} onChange={v => setDraft('min_depth_mv', v)} min={0.02} max={0.4} step={0.01} unit="mV" format={v => `${v.toFixed(2)} mV`} rec={0.1} recNote="recording noise floor" testid="param-min_depth_mv" disabled={running} />
        <ParamSlider label="minimum duration" info="Shorter drops are dropped." value={minDur} onChange={v => setDraft('min_duration_s', v)} min={0.2} max={3} step={0.1} unit="s" rec={0.6} testid="param-min_duration_s" disabled={running} />
        <ParamSlider label="merge window" info="Candidates closer than this merge into one. It must be at least one trough-tolerance window, or the adapter refuses the run." value={merge} onChange={v => setDraft('merge_window_s', v)} min={0.5} max={5} step={0.1} unit="s" rec={trough} recNote="≥ trough window" tone={merge < trough ? 'red' : undefined} testid="param-merge_window_s" disabled={running} />
        <ParamSlider label="trough tolerance" info="How far (in σ) the trough may sit from the steepest segment." value={tol} onChange={v => setDraft('trough_tol_sigma', v)} min={0.1} max={1} step={0.1} unit="σ" rec={0.5} testid="param-trough_tol_sigma" disabled={running} />
        <ParamSelect label="dedupe" info="Which copy survives when candidates overlap." value={str(draft.dedupe, 'keep best-framed')} options={['keep best-framed', 'keep deepest', 'keep first', 'off']} onChange={v => setDraft('dedupe', v)} testid="param-dedupe" disabled={running} />
        <ParamSelect label="onset rule" info="Where a drop starts." value={str(draft.onset, 'walk back from steepest')} options={['walk back from steepest', 'first d segment', 'threshold crossing']} onChange={v => setDraft('onset', v)} testid="param-onset" disabled={running} />
        <div className="bx-rule" style={{ gridColumn: '1 / -1' }}><Icon name="link" size={12} /> matching rule IoU ≥ 0.50 · onset ± 0.25 × duration <Button variant="link" size="sm" onClick={() => navigate('settings/analysis-defaults')} testid="matching-settings">Settings</Button></div>
        <div style={{ gridColumn: '1 / -1' }}><Tiles items={[{ k: 'kept', v: kept.length }, { k: 'surrogate', v: st.surrogate ? '2.1 [0–5]' : 'off' }, { k: 'vs chance', v: st.surrogate ? `${(kept.length / 2.1).toFixed(1)}×` : '—', tone: 'green' }]} /></div>
      </ParamsCard>

      <BlockCard className="span2" title="Each kept detection" sub={<span className="mono muted" style={{ fontSize: 10.5 }}>click one to centre it above · shared y · ±0.4 mV, depth to scale</span>}
        actions={<span className="row" style={{ gap: 8 }}><Dropdown prefix="sort" value={sort} onChange={setSort} options={[{ value: 'match score', label: 'match score' }, { value: 'time', label: 'time' }, { value: 'depth', label: 'depth' }]} testid="kept-sort" /><Pager page={pg.page} pageCount={pg.pageCount} onPage={pg.setPage} format="range" total={pg.total} pageSize={10} /></span>} testid="kept-cards">
        {kept.length ? (
          <div className="bx-kept">
            {pg.items.map(d => {
              const i0 = Math.max(0, Math.round((d.at - 1.5) * 5)), i1 = Math.min(tr.out.length, Math.round((d.at + d.dur + 1.5) * 5))
              return (
                <button key={d.id} className={`bx-kept-card${selected === d.id ? ' on' : ''}`} onClick={() => setSelected(d.id)} data-testid={`kept-${d.id}`}>
                  <div className="r1"><b>{d.id}</b><Chip size="sm" tone={d.family ? 'outline' : 'grey'} dot={d.family ? FAMILY_COLOURS[d.family] : undefined}>{d.family ?? '—'}</Chip><span className="mono muted">score {d.score.toFixed(2)}</span></div>
                  <MiniTrace values={tr.out.slice(i0, i1)} yDomain={[-0.45, 0.2]} width="100%" height={52} stroke={d.family ? FAMILY_COLOURS[d.family] : 'var(--text-2)'} />
                  <div className="mono" style={{ fontSize: 11 }}>{d.depth.toFixed(2)} mV · {d.dur.toFixed(1)} s</div>
                  <div className="mono" style={{ fontSize: 10.5, color: d.judged ? '#15794f' : '#a05e00' }}>● {d.judged ?? 'unadjudicated'}</div>
                </button>
              )
            })}
          </div>
        ) : <div className="mono muted small">no detection passes these floors · lower the minimum depth or duration</div>}
      </BlockCard>

      <BlockCard className="span2" title="Save as a detection template" info="A SpanSet terminal saves as a detection template; it populates Discovery's template picker. Templates store no recording or span." testid="save-detection-template">
        <div className="row" style={{ gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <Field label="name" error={problem ?? undefined}><TextField value={tplName} onChange={setTplName} invalid={!!problem} width={220} testid="tpl-name" /></Field>
          <Field label="version"><TextField value={tplName === 'drop_motifs9' ? 'v4 (was v3)' : 'v1'} onChange={() => {}} disabled disabledReason="the version follows the name" width={130} /></Field>
          <Field label="kind"><TextField value="detection · from terminal" onChange={() => {}} disabled disabledReason="the terminal type decides the kind (§6.1)" width={200} /></Field>
          <span style={{ flex: 1 }} />
          <Button icon="save" disabled={!!problem} disabledReason={problem ?? undefined} onClick={() => { actions.save(tplName, tplName === 'drop_motifs9' ? 'v4' : 'v1'); toast.push({ text: `${tplName} saved as a detection template (in memory)` }) }} testid="tpl-save">Save template</Button>
          <Button icon="upload" onClick={() => notWired('export the run report (recipe, per-stage hashes, the 6 kept spans)')} testid="export-run">Export run</Button>
          <Button icon="arrow-right" onClick={() => { handoff('analyse-events'); navigate('analyse/interrogation') }} testid="analyse-events">Analyse events</Button>
          <Button variant="primary" icon="arrow-right" disabled={!kept.length} disabledReason="no kept detections" onClick={() => { handoff('pass-to-review'); toast.push({ text: `${kept.length} spans passed to Review (in memory)` }); navigate('review/queue/q-12') }} testid="pass-to-review">Pass {kept.length} to Review</Button>
        </div>
      </BlockCard>
    </div>
  )
}
