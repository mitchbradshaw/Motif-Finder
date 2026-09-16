/* Settings › Display — personal (frame settings-15 · spec §9.15).
 * How the site looks to this browser. Changes apply immediately; nothing here is recorded with runs.
 * Report figures use the profile at the foot, with a live preview. */
import { Button, ColourDot, NumberField, SectionCard, Seg, SelectField, Slider, Toggle, Trace, useNotWired } from '../kit'
import { useSourced } from '../api/seam'
import { getDisplay } from '../api/settings'
import { LoadFailed, Loading, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

const PALETTE = ['#8B5CF6', '#E85AAD', '#30B0C7', '#A2845E', '#5AC8FA', '#8E8E93', '#8B4A3B', '#F4A8C8', '#1F8A70', '#2F6FEB']

export function DisplayPage() {
  const rd = useSourced(getDisplay, [])
  return (
    <SettingsShell slug="display" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the display preferences" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
      <PersonalFoot />
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getDisplay>>['data']

export function PersonalFoot() {
  const notWired = useNotWired()
  return (
    <div className="k-card pad" style={{ display: 'flex', alignItems: 'center', gap: 8 }} data-testid="personal-foot">
      <span className="s-note">personal preferences apply immediately to this browser and are not recorded with runs</span>
      <span className="k-spacer" />
      <Button variant="link" size="sm" icon="upload" testid="export-preferences" onClick={() => notWired('download preferences.json')}>Export preferences</Button>
    </div>
  )
}

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('display')
  const seg = (id: string, options: string[]) => (
    <Seg value={s.str(id)} onChange={v => s.set(id, v)} testid={id.replace(/_/g, '-')} options={options.map(o => ({ value: o, label: o }))} />
  )

  return (
    <>
      <SectionCard title="Appearance" testid="appearance-card">
        <Row label="theme" dot={s.differs('theme')} testid="theme-row" caption="dark is not drawn yet — light and system look the same today">
          {seg('theme', ['system', 'light', 'dark'])}
        </Row>
        <Row label="density" dot={s.differs('density')} testid="density-row" caption="compact tightens table rows across every page">
          {seg('density', ['comfortable', 'compact'])}
        </Row>
      </SectionCard>

      <SectionCard title="Units and time" subtitle="every readout on every page, not only plots" testid="units-card">
        <Row label="time axis" id="f-time-axis" dot={s.differs('time_axis')} testid="time-axis-row" caption="hours since recording start is the canon readout">
          {seg('time_axis', ['hours since start', 'clock time', 'both'])}
        </Row>
        <Row label="amplitude" dot={s.differs('amplitude')} testid="amplitude-row" caption="mV is never normalised">
          {seg('amplitude', ['mV', 'µV'])}
        </Row>
        <Row label="sample indices" dot={s.differs('sample_indices')} testid="sample-indices-row" caption="indices are always into the whole recording">
          <Toggle checked={s.bool('sample_indices')} onChange={v => s.set('sample_indices', v)} label="show beside times" testid="sample-indices" />
        </Row>
      </SectionCard>

      <SectionCard title="Colours" testid="colours-card">
        <Row label="roles" testid="roles-row" wide>
          <span style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            {data.roleColours.map(r => (
              <span key={r.role} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} data-testid={`role-${r.role.replace(/\s/g, '-')}`}>
                <ColourDot colour={r.colour} size={12} /><span className="mono small">{r.role}</span>
              </span>
            ))}
          </span>
        </Row>
        <Row label="family palette" dot={s.differs('family_palette')} testid="palette-row" wide>
          <SelectField value={s.str('family_palette')} onChange={v => s.set('family_palette', v)} width={220} testid="family-palette"
            options={data.palettes.map(p => ({ value: p, label: p }))} />
          <span style={{ display: 'inline-flex', gap: 5, marginLeft: 10 }}>
            {PALETTE.slice(0, Number(s.str('family_palette').match(/(\d+)$/)?.[1] ?? 10)).map(c => <span key={c} className="s-swatch" style={{ background: c }} />)}
          </span>
        </Row>
      </SectionCard>

      <SectionCard title="View sizes" testid="sizes-card">
        <Row label="channels per page" dot={s.differs('channels_per_page')} testid="channels-row" caption="Discovery scope and where-each-run-fires">
          <NumberField value={s.num('channels_per_page')} min={1} max={10} integer width={90} onValid={v => s.set('channels_per_page', v)} testid="channels-per-page" />
        </Row>
        <Row label="Review context padding" dot={s.differs('review_padding')} testid="padding-row" caption="how much signal sits either side of a candidate">
          {seg('review_padding', ['±30 s', '±120 s', '±300 s'])}
        </Row>
        <Row label="members per page" dot={s.differs('members_per_page')} testid="members-row" caption="Library family and atlas overlays · capped at 10 (P8)">
          <NumberField value={s.num('members_per_page')} min={1} max={10} integer width={90} testid="members-per-page"
            onValid={v => { s.set('members_per_page', v); s.markInvalid('members_per_page', null) }}
            onChange={(_r, reason) => s.markInvalid('members_per_page', reason ? 'at most 10 small multiples at once (P8)' : null)} />
        </Row>
        <Row label="recurrence cells" dot={s.differs('recurrence')} testid="recurrence-row" caption="per hour keeps recordings of different length comparable">
          {seg('recurrence', ['per hour', 'count'])}
        </Row>
      </SectionCard>

      <SectionCard title="Report figure profile" subtitle="used by run reports and figure exports" testid="report-card">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <Row label="trace line width" dot={s.differs('line_width')} testid="line-width-row">
              <Slider value={s.num('line_width')} onChange={v => s.set('line_width', v)} min={0.5} max={3} step={0.1} width={150} format={v => `${v.toFixed(1)} pt`} testid="line-width" />
            </Row>
            <Row label="grid opacity" dot={s.differs('grid_opacity')} testid="grid-row">
              <Slider value={s.num('grid_opacity')} onChange={v => s.set('grid_opacity', v)} min={0} max={1} step={0.05} width={150} format={v => v.toFixed(2)} testid="grid-opacity" />
            </Row>
            <Row label="font" dot={s.differs('font')} testid="font-row">
              <SelectField value={s.str('font')} onChange={v => s.set('font', v)} width={150} testid="font"
                options={['Inter', 'Source Sans 3', 'Helvetica', 'Times New Roman'].map(f => ({ value: f, label: f }))} />
            </Row>
            <Row label="resolution" dot={s.differs('dpi')} testid="dpi-row">
              <NumberField value={s.num('dpi')} min={72} max={1200} integer unit="dpi" width={120} onValid={v => s.set('dpi', v)} testid="dpi" />
            </Row>
            <Row label="background" dot={s.differs('background')} testid="background-row">
              {seg('background', ['white', 'transparent'])}
            </Row>
          </div>
          <div className="k-card grey pad" data-testid="figure-preview">
            <span className="s-label mono">preview</span>
            <Trace values={data.preview} fs={1} t0={0} timeUnit="h" height={190} ground="white"
              stroke={s.str('background') === 'transparent' ? 'var(--trace-blue)' : undefined} />
            <span className="s-note">{s.num('line_width').toFixed(1)} pt · grid {s.num('grid_opacity').toFixed(2)} · {s.str('font')} · {s.num('dpi')} dpi · {s.str('background')}</span>
          </div>
        </div>
      </SectionCard>
    </>
  )
}
