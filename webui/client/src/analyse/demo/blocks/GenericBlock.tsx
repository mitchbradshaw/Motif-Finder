/* Any other demo block (a block inserted from the modal that has no template page yet): the shared shell with the
 * output drawn at full size by the row renderer, its defaults as editable parameters, and an explicit null declaration
 * (§6.8: "either a parameter-vs-null plot or an explicit no-null declaration with the reason"). */
import { Callout, EmptyState, Field, TextField } from '../../../kit'
import { blockByName } from '../../../api/analyse'
import { makeX } from '../../../charts/scale'
import { renderByType } from '../../Renderer'
import { payloadFor } from '../chainState'
import { useSize } from '../../../charts/useSize'
import { BlockCard, ParamsCard, type BlockProps } from './common'

export function GenericBlock({ step, draft, setDraft, bundle, st, index, running }: BlockProps) {
  const b = blockByName(step.block)
  const payload = st.status[step.uid] === 'cached' || st.status[step.uid] === 'stale' ? payloadFor(bundle, st.steps, index) : null
  const t0 = bundle.source.t0_s, t1 = bundle.source.t1_s
  return (
    <div className="bx-grid">
      <BlockCard title={<><span className="mono muted" style={{ fontWeight: 400, fontSize: 12 }}>{String(index + 1).padStart(2, '0')}</span> {b?.page_name ?? step.block} <span className="sig">{b?.signature}</span></>} info={b?.description} testid="block-process">
        {payload ? (
          <GenericPlot payload={payload} t0={t0} t1={t1} />
        ) : <EmptyState icon="layers" title="No result yet" caption="run the chain from this block to see its output here" bordered testid="generic-empty" />}
        <Callout tone="grey" style={{ marginTop: 10 }}>this block has no process template yet · the output is shown at full size by the row renderer (§6.8 table)</Callout>
      </BlockCard>
      <ParamsCard note="">
        {Object.entries(draft).map(([k, v]) => (
          <Field key={k} label={k.replace(/_/g, ' ')}>
            <TextField value={String(v)} onChange={val => setDraft(k, typeof v === 'number' && val.trim() !== '' && Number.isFinite(Number(val)) ? Number(val) : val)} invalid={typeof v === 'number' && !Number.isFinite(Number(draft[k]))} disabled={running} disabledReason="wait for the run" testid={`param-${k}`} />
          </Field>
        ))}
        {!Object.keys(draft).length && <div className="mono muted small">this block has no parameters</div>}
        <div style={{ gridColumn: '1 / -1' }}>
          <Callout tone={b?.has_null ? 'green' : 'grey'}>{b?.has_null ? 'surrogate-compatible · its output is measured against the chain\'s surrogate' : 'no null for this block · it does not change what is detected, only its form'}</Callout>
        </div>
      </ParamsCard>
    </div>
  )
}

function GenericPlot({ payload, t0, t1 }: { payload: NonNullable<ReturnType<typeof payloadFor>>; t0: number; t1: number }) {
  const [ref, size] = useSize<HTMLDivElement>()
  return <div ref={ref} className="bx-plot" style={{ height: 200, position: 'relative' }} data-testid="generic-plot">{size.width > 0 && renderByType(payload, { x: makeX(t0, t1, size.width), width: size.width, height: 200, t0, t1 })}</div>
}
