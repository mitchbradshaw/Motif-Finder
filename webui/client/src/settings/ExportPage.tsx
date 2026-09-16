/* Settings › Export (frame settings-12 · spec §9.12).
 * What leaves the tool. An export that cannot be traced to a repository state is not evidence. */
import type { ReactNode } from 'react'
import { Chip, SectionCard, Seg, Toggle } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getExport } from '../api/settings'
import { LoadFailed, Loading, LockedChip, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function ExportPage() {
  const rd = useSourced(getExport, [])
  return (
    <SettingsShell slug="export" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the export defaults" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getExport>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('export')

  /** A row of chips that toggle in and out of a list value. */
  const ChipRow = ({ id, options, caption, label, minOne = true }: { id: string; options: string[]; caption?: ReactNode; label: string; minOne?: boolean }) => {
    const on = s.list(id)
    return (
      <Row label={label} dot={s.differs(id)} unsaved={s.dirty(id)} testid={`${id.replace(/\./g, '-')}-row`} caption={caption} wide>
        <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {options.map(o => {
            const isOn = on.includes(o)
            const last = minOne && isOn && on.length === 1
            return (
              <Chip key={o} tone={isOn ? 'blue' : 'outline'} selected={isOn} icon={isOn ? 'check' : undefined}
                testid={`${id.replace(/\./g, '-')}-${o.replace(/\s/g, '-')}`}
                onClick={last ? undefined : () => s.set(id, isOn ? on.filter(x => x !== o) : [...on, o])}
                title={last ? 'at least one must stay on' : undefined}>{o}</Chip>
            )
          })}
        </span>
      </Row>
    )
  }

  return (
    <>
      <SectionCard title="Always included" subtitle="not optional" testid="always-card">
        <Row label="every export carries" testid="always-row" wide>
          <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {data.always.map(a => <LockedChip key={a} reason="an export that cannot be traced to a repository state is not evidence" testid={`always-${a.replace(/\s/g, '-')}`}>{a}</LockedChip>)}
          </span>
        </Row>
      </SectionCard>

      <SectionCard title="Motifs and families" subtitle="Library" testid="motifs-card">
        <ChipRow id="motifs.formats" label="formats" options={data.motifFormats} caption="one file per format" />
        <ChipRow id="motifs.include" label="include" options={data.motifInclude} caption="hand edits and the omitted list make the grouping readable" minOne={false} />
        <Row label="layout" dot={s.differs('motifs.layout')} unsaved={s.dirty('motifs.layout')} testid="motifs-layout-row" wide>
          <Seg value={s.str('motifs.layout')} onChange={v => s.set('motifs.layout', v)} testid="motifs-layout"
            options={[{ value: 'one workbook, a sheet per family', label: 'one workbook, a sheet per family' }, { value: 'a file per family', label: 'a file per family' }]} />
        </Row>
      </SectionCard>

      <SectionCard title="Window sets" subtitle="Library" testid="windowsets-card">
        <Row label="format" dot={s.differs('ws.format')} unsaved={s.dirty('ws.format')} testid="ws-format-row" wide>
          <Seg value={s.str('ws.format')} onChange={v => s.set('ws.format', v)} testid="ws-format"
            options={[{ value: 'npz + JSON manifest', label: 'npz + JSON manifest' }, { value: 'parquet + JSON manifest', label: 'parquet + JSON manifest' }]} />
        </Row>
        <ChipRow id="ws.include" label="include" options={data.windowSetInclude} caption="the split plan is what makes a window set reusable" minOne={false} />
      </SectionCard>

      <SectionCard title="Templates" subtitle="Library" testid="templates-card">
        <Row label="format" testid="templates-format-row" wide>
          <LockedChip reason="templates are JSON so a diff is readable" testid="templates-format">JSON</LockedChip>
        </Row>
        <Row label="carry exemplars with seed templates" dot={s.differs('templates.carry_exemplars')} unsaved={s.dirty('templates.carry_exemplars')}
          testid="carry-exemplars-row" caption="a rebind template never carries one" wide>
          <Toggle checked={s.bool('templates.carry_exemplars')} onChange={v => s.set('templates.carry_exemplars', v)} testid="carry-exemplars" />
        </Row>
      </SectionCard>

      <SectionCard title="Models" subtitle="Models › Registry" testid="models-card">
        <Row label="weights" dot={s.differs('models.weights')} unsaved={s.dirty('models.weights')} testid="weights-row" wide>
          <Seg value={s.str('models.weights')} onChange={v => s.set('models.weights', v)} testid="weights"
            options={[{ value: 'PyTorch', label: 'PyTorch' }, { value: 'ONNX', label: 'ONNX' }]} />
        </Row>
        <Row label="model card" testid="model-card-row" caption="held-out checks, calibration, verification sample, sign-off" wide>
          <Toggle checked disabled disabledReason="a model without its card cannot be read later" onChange={() => undefined} testid="model-card" />
          <LockedChip reason="the card travels with every model export (P19)">always</LockedChip>
        </Row>
      </SectionCard>

      <SectionCard title="Run reports" testid="reports-card">
        <Row label="layout" dot={s.differs('reports.layout')} unsaved={s.dirty('reports.layout')} testid="reports-layout-row" wide>
          <Seg value={s.str('reports.layout')} onChange={v => s.set('reports.layout', v)} testid="reports-layout"
            options={[{ value: 'one document, stages in order', label: 'one document, stages in order' }, { value: 'a file per stage', label: 'a file per stage' }]} />
        </Row>
        <Row label="figures use the report profile" testid="report-profile-row" wide
          caption={<>set in <button type="button" className="k-link" onClick={() => navigate('settings/display')}>Display · personal</button></>}>
          <LockedChip reason="a plot without its parameters cannot be read later" testid="params-printed">parameters printed beneath each plot</LockedChip>
        </Row>
      </SectionCard>

      <SectionCard title="Reproducibility bundle" testid="bundle-card">
        <ChipRow id="bundle.contents" label="bundle contents" options={data.bundle} caption="one zip per run or template" minOne={false} />
      </SectionCard>
    </>
  )
}
