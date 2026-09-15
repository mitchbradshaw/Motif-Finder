/* #/kit — the component gallery: every kit component in its main states, on synthetic canon data. A dev aid and a smoke target. */
import { useMemo, useRef, useState } from 'react'
import './kit.css'
import { CLASSES, FAMILIES, FAMILY_COLOURS, JOBS, syntheticTrace } from '../fixtures/canon'
import { Header } from '../shell/Header'
import { ChainRibbon } from './ChainRibbon'
import { Badge, Button, Callout, Checklist, Chip, CodeBlock, ColourDot, DisabledReason, EmptyState, IconButton, Kbd, KeyValue, ProgressBar, StatRow, StatTile, Stepper, type BadgeStatus } from './display'
import { Checkbox, Field, NumberField, RadioCards, RangeSlider, SelectField, Slider, TextField, Toggle } from './forms'
import { BlockGlyph, GLYPH_ALIASES } from './glyphs'
import { useQueryState, usePagedList } from './hooks'
import { Card, Page, PageTitle, Rail, SectionCard, SideNav, SplitPane, Toolbar, Spacer } from './layout'
import { Breadcrumb, Pager, Seg, Tabs } from './nav'
import { useSim } from './sim'
import { recordDemoWrite, useDemoState } from './store'
import { BandStrip, Bars, Heatmap, Histogram, LineChart, MiniTrace, NullBand, Scatter, SmallMultiples, Trace } from './plots'
import { Drawer, Dropdown, InfoTip, Menu, Modal, Popover } from './surfaces'
import { Table, type Column } from './Table'
import { useNotWired } from './notWired'

const SECTIONS = [
  ['layout', 'Layout'], ['navigation', 'Navigation'], ['surfaces', 'Surfaces'], ['display', 'Data display'], ['table', 'Table'],
  ['chain', 'Chain & glyphs'], ['forms', 'Forms'], ['plots', 'Plots'],
] as const
const STATUSES: BadgeStatus[] = ['cached', 'stale', 'new', 'running', 'paused', 'failed', 'on cluster', 'invalid', 'done', 'queued', 'cancelled']

interface JobRow { id: string; title: string; kind: string; status: string; detail: string; hours: number }
const JOB_ROWS: JobRow[] = JOBS.map((j, i) => ({ id: j.id, title: j.title, kind: j.kind, status: j.status, detail: j.detail, hours: [2, 13, 3.3, 0, 6, 1][i] ?? 1 }))

const SLURM = `#!/bin/bash
#SBATCH --job-name=train_cnn_M2aug_sep14
#SBATCH --gres=gpu:1 --time=04:00:00
#SBATCH --mem=32G

python -m pipeline.train \\
  --template cnn_windows_v3@3 \\
  --sources M2_aug_fs1:CH2_A1,CH4_A2,CH7_B2 \\
  --split "blocked:test=0.2,val=0.1,gap=600" \\
  --manifest inbox/`

function Sec({ id, title, sub, children }: { id: string; title: string; sub?: string; children: React.ReactNode }) {
  return <section className="k-gal-sec" id={`kit-${id}`} data-testid={`kit-sec-${id}`}><h2>{title}{sub && <span>{sub}</span>}</h2>{children}</section>
}
function L({ children }: { children: React.ReactNode }) { return <div className="k-gal-label">{children}</div> }

export function KitGallery() {
  const notWired = useNotWired()
  const [nav, setNav] = useState<string>('layout')
  const [tab, setTab] = useQueryState<string>('tab', 'launch')
  const [seg, setSeg] = useState('120')
  const [page, setPage] = useState(233)
  const [modal, setModal] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [drawerTab, setDrawerTab] = useState('annotations')
  const [pop, setPop] = useState(false)
  const popAnchor = useRef<HTMLButtonElement>(null)
  const [dd, setDd] = useState<string | null>('20')
  const [ddFilter, setDdFilter] = useState<string | null>('interesting')
  const [selected, setSelected] = useState<string[]>(['j-0214'])
  const [hl, setHl] = useState<string | null>('r-0431')
  const [text, setText] = useState('module load cuda/12.1')
  const [num, setNum] = useState<number | null>(20)
  const [bad, setBad] = useState<number | null>(20)
  const [sel, setSel] = useState('gpu-single')
  const [toggle, setToggle] = useState(true)
  const [checks, setChecks] = useState<Record<string, boolean>>({ seed: true, interesting: true, artifact: false })
  const [slider, setSlider] = useState(0.42)
  const [range, setRange] = useState<[number, number]>([112, 286])
  const [radio, setRadio] = useState<string>('channels')
  const [block, setBlock] = useState('mp')
  const [notes, setNotes] = useDemoState('kit.notes', () => 0)
  const sim = useSim('kit.gallery.run')

  const trace = useMemo(() => syntheticTrace({ n: 600, seed: 11, noise: 0.03, events: [{ at: 250, depth: 0.35, width: 40, shape: 'spike' }, { at: 300, depth: 0.32, width: 40, shape: 'spike' }] }), [])
  const medoid = useMemo(() => syntheticTrace({ n: 600, seed: 12, noise: 0.01, events: [{ at: 254, depth: 0.3, width: 44, shape: 'spike' }, { at: 304, depth: 0.3, width: 44, shape: 'spike' }] }), [])
  const members = useMemo(() => Array.from({ length: 44 }, (_, i) => syntheticTrace({ n: 120, seed: 100 + i, noise: 0.02, events: [{ at: 40 + (i % 7), depth: 0.2 + (i % 5) * 0.04, width: 30 }] })), [])
  const shared: [number, number] = [-0.45, 0.2]
  const nullDraws = useMemo(() => { const r = syntheticTrace({ n: 200, seed: 5, noise: 0.08 }); return r.map(v => 0.26 + v) }, [])
  const paged = usePagedList(JOB_ROWS, 4)

  const columns: Column<JobRow>[] = [
    { key: 'id', header: 'id', width: 80, sortValue: r => r.id, render: r => <b>{r.id}</b> },
    { key: 'title', header: 'job', sortValue: r => r.title, render: r => <div><div className="primary-text">{r.title}</div><div className="sub-text">{r.detail}</div></div> },
    { key: 'kind', header: 'where', render: r => r.kind === 'cluster' ? 'hpc-1 · cpu-array' : 'this machine' },
    { key: 'status', header: 'status', render: r => <Badge status={(r.status === 'finished' ? 'done' : r.status === 'queue' ? 'queued' : r.status) as BadgeStatus} /> },
    { key: 'hours', header: 'time', align: 'right', sortValue: r => r.hours, render: r => r.hours ? `${r.hours} h` : '—' },
  ]

  return (
    <>
      <Header workspace="Kit" page="component gallery" subtitle="every kit component in its main states · synthetic canon data" demo />
      <Page testid="kit-gallery">
        <div className="k-gal">
          <div className="k-gal-nav">
            <Card padding="md">
              <SideNav value={nav} onChange={v => { setNav(v); document.getElementById(`kit-${v}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}
                groups={[{ section: 'KIT · components', sectionIcon: 'grid', items: SECTIONS.map(([v, l]) => ({ value: v, label: l, differs: v === 'plots' })) }]} testid="kit-nav" />
            </Card>
          </div>
          <div className="stack" style={{ gap: 20, minWidth: 0 }}>
            {/* ---------------- layout ---------------- */}
            <Sec id="layout" title="Layout" sub="Page · PageTitle · Toolbar · Card · SectionCard · SplitPane · Rail · SideNav">
              <PageTitle title="Compute & HPC" actions={<Button variant="link" icon="refresh" onClick={() => notWired('reset page to defaults')}>Reset page to defaults</Button>}><Chip tone="blue" size="sm">project · recorded with runs</Chip></PageTitle>
              <Toolbar card>
                <Chip tone="outline" icon="pencil">train_cnn_M2aug_sep14</Chip><Chip tone="grey" size="sm">unsaved</Chip>
                <Spacer />
                <Chip tone="amber" icon="hourglass">≈ 5.6 h local above 2 h limit</Chip>
                <Button icon="play" disabled disabledReason="over the 2 h local limit · Train locally is off">Train locally</Button>
                <Button variant="cluster" icon="file" onClick={() => notWired('create SLURM script')}>Create SLURM script</Button>
              </Toolbar>
              <SplitPane right={<Rail title="Before launch" collapsible width={300} testid="kit-rail"><Checklist items={[{ label: 'test block never seen in training', state: 'pass' }, { label: 'burst class: 31 test windows (≥ 50 recommended)', state: 'warn' }, { label: 'human verification · 33 of 40', state: 'pending' }]} /></Rail>}>
                <div className="stack" style={{ gap: 12 }}>
                  <SectionCard number={1} title="Training template" info="The template comes from Analyse; its stages decide what the sources must be." subtitle="from Analyse" actions={<Button variant="link" icon="external" onClick={() => notWired('open in Analyse')}>Open in Analyse</Button>} testid="kit-section">
                    <ChainRibbon blocks={[{ id: 's', label: 'Source', glyph: 'source' }, { id: 'w', index: 1, label: 'Sliding windows', glyph: 'sliding_windows' }, { id: 'm', index: 2, label: 'Window matrix', glyph: 'window_matrix' }, { id: 'c', index: 3, label: 'Cluster', glyph: 'cluster' }, { id: 'e', index: 4, label: 'Image encode', glyph: 'gramian' }, { id: 'n', index: 5, label: 'CNN classifier', glyph: 'classifier' }]} />
                  </SectionCard>
                  <SectionCard number={2} title="Options" collapsible defaultOpen={false} subtitle="collapsible, starts closed">
                    <div className="muted mono small">hidden until opened</div>
                  </SectionCard>
                </div>
              </SplitPane>
            </Sec>

            {/* ---------------- navigation ---------------- */}
            <Sec id="navigation" title="Navigation" sub="Tabs (query-bound ?tab=) · Seg · Breadcrumb · Pager">
              <Card>
                <div className="stack" style={{ gap: 12 }}>
                  <Tabs items={[{ value: 'launch', label: 'Launch', icon: 'rocket' }, { value: 'results', label: 'Results', icon: 'bar-chart' }, { value: 'compare', label: 'Compare', icon: 'compare' }, { value: 'registry', label: 'Registry', icon: 'library', disabled: true, reason: 'nothing registered yet' }]} value={tab} onChange={setTab} testid="kit-tabs" />
                  <Tabs variant="track" items={[{ value: 'motifs', label: 'Motifs', icon: 'target', count: '1,402' }, { value: 'ws', label: 'Window sets', icon: 'grid', count: 6 }, { value: 'tpl', label: 'Templates', icon: 'file', count: 14 }]} value="motifs" onChange={v => notWired(`library tab ${v}`)} />
                  <div className="k-gal-row">
                    <Seg label="padding" options={[{ value: '30', label: '±30 s' }, { value: '120', label: '±120 s' }, { value: '300', label: '±300 s' }, { value: '900', label: '±900 s', disabled: true, reason: 'beyond the recording end' }]} value={seg} onChange={setSeg} testid="kit-seg" />
                    <Breadcrumb items={[{ label: 'Corpus', onClick: () => notWired('back to corpus') }, { label: 'M2_aug_concat_fs1.mat', onClick: () => notWired('open recording') }, { label: 'CH4_A2' }]} />
                    <Pager page={page} pageCount={344} onPage={setPage} testid="kit-pager" />
                    <Pager format="range" page={paged.page} pageCount={paged.pageCount} total={paged.total} pageSize={4} onPage={paged.setPage} />
                  </div>
                </div>
              </Card>
            </Sec>

            {/* ---------------- surfaces ---------------- */}
            <Sec id="surfaces" title="Surfaces" sub="Modal · Popover · Drawer · Dropdown · Menu · InfoTip · Tooltip (DisabledReason)">
              <Card>
                <div className="k-gal-row">
                  <Button variant="primary" icon="plus" onClick={() => setModal(true)} testid="kit-open-modal">Open modal</Button>
                  <Button ref={popAnchor} icon="clock" iconRight="chevron-down" onClick={() => setPop(o => !o)} aria-expanded={pop} testid="kit-open-popover">History</Button>
                  <Button icon="panel-right" onClick={() => setDrawer(d => !d)} aria-expanded={drawer} testid="kit-open-drawer">{drawer ? 'Close drawer' : 'Open drawer'}</Button>
                  <Dropdown prefix="test" value={dd} onChange={setDd} options={[{ value: '10', label: '10 %' }, { value: '20', label: '20 %' }, { value: '30', label: '30 %' }, { value: '50', label: '50 %', disabled: true, reason: 'leaves too few training windows' }]} testid="kit-dropdown" />
                  <Dropdown prefix="verdict" active={!!ddFilter} value={ddFilter} onChange={setDdFilter} options={['seed', 'interesting', 'not_interesting', 'artifact', 'unsure'].map(v => ({ value: v, label: v }))} />
                  <Menu trigger={p => <Button {...p} icon="more" iconRight="chevron-down">Mark…</Button>} onSelect={v => notWired(`mark job ${v}`)} testid="kit-menu"
                    items={[{ value: 'submitted', label: 'Mark submitted', icon: 'upload' }, { value: 'running', label: 'Mark running', icon: 'play' }, { value: 'finished', label: 'Mark finished', icon: 'check' }, { value: 'failed', label: 'Mark failed', icon: 'x', danger: true }, { value: 'import', label: 'Import results', disabled: true, reason: 'nothing in the manifest inbox' }]} />
                  <span className="row">explanation <InfoTip title="Local limits" testid="kit-infotip">Above a limit the work goes to the cluster: the stage offers Create SLURM script and downstream stages wait.</InfoTip></span>
                  <DisabledReason reason="needs at least one selected row"><Button>Send to Review</Button></DisabledReason>
                </div>
              </Card>
              <Popover open={pop} onClose={() => setPop(false)} anchorRef={popAnchor} title="Run history" subtitle="4 runs · recording 385" width={360} testid="kit-popover">
                <div className="stack" style={{ gap: 6 }}>
                  {['#128 drop_motifs9', '#131 drop_motifs9 · 6σ floor', '#97 banded_sax_lp'].map(r => <div key={r} className="row between mono small"><span>{r}</span><Button size="sm" onClick={() => { setPop(false); notWired(`apply ${r}`) }}>Apply</Button></div>)}
                </div>
              </Popover>
              <Modal open={modal} onClose={() => setModal(false)} title="Add runs" subtitle="apply a template across channels" size="lg" testid="kit-modal"
                headerExtra={<Seg size="sm" options={[{ value: 'tpl', label: 'Apply template' }, { value: 'seed', label: 'Seed search' }]} value="tpl" onChange={() => notWired('seed search tab')} />}
                footerNote="2 templates selected × 3 channels"
                footer={<><Button onClick={() => setModal(false)}>Cancel</Button><Button icon="plus" onClick={() => { recordDemoWrite('kit', 'add runs', { n: 2 }); setNotes(n => n + 1); setModal(false) }} testid="kit-modal-add">Add 2 runs</Button><Button variant="cluster" icon="file" onClick={() => notWired('create SLURM script')}>Create SLURM script</Button></>}>
                <div className="stack" style={{ gap: 10 }}>
                  <TextField icon="search" value={text} onChange={setText} placeholder="Search templates" width={260} />
                  <Callout tone="grey" icon="info" action={<Button variant="link" icon="external" onClick={() => notWired('open Analyse')}>Open Analyse</Button>}>Models run inside detection templates — add a Model stage in Analyse</Callout>
                  <StatRow><StatTile label="compute" value="≈ 6.4 h" caption="O(n²) per channel" tone="amber" /><StatTile label="disk" value="0.6 GB" caption="scores kept" /><StatTile label="null" value="200×" caption="circular shift" /></StatRow>
                </div>
              </Modal>
              <Drawer open={drawer} onClose={() => setDrawer(false)} title="Spans" side="right" width={460} tabs={[{ value: 'annotations', label: 'Annotations', count: 708 }, { value: 'detections', label: 'Detections', count: '1,284' }, { value: 'shortcuts', label: 'Shortcuts' }]} tab={drawerTab} onTab={setDrawerTab} testid="kit-drawer">
                <EmptyState icon="list" title={`${drawerTab} list`} caption="drawer body — Escape or ✕ closes and focus returns to the opener" size="sm" />
              </Drawer>
              <div className="muted mono small" data-testid="kit-demo-writes">in-memory writes from the modal: {notes}</div>
            </Sec>

            {/* ---------------- display ---------------- */}
            <Sec id="display" title="Data display" sub="Button · Chip · Badge · StatTile · KeyValue · EmptyState · ProgressBar · CodeBlock · Callout · Stepper · Checklist · ColourDot · Kbd">
              <Card>
                <L>Button variants</L>
                <div className="k-gal-row">
                  <Button>Default</Button><Button variant="primary" iconRight="arrow-right">Primary</Button><Button variant="cluster" icon="file">Cluster</Button><Button variant="danger" icon="x">Cancel run</Button>
                  <Button variant="subtle">Subtle</Button><Button variant="ghost" icon="refresh">Ghost</Button><Button variant="link" iconRight="arrow-right">Link</Button><Button size="sm">Small</Button>
                  <Button loading>Loading</Button><Button disabled disabledReason="~6 h · over the 20 min limit" icon="cpu">Run stage 3 locally</Button><IconButton icon="settings" label="settings" onClick={() => notWired('settings')} bordered />
                </div>
                <L>Chips</L>
                <div className="k-gal-row">
                  {(['blue', 'grey', 'green', 'amber', 'red', 'purple', 'outline', 'demo'] as const).map(t => <Chip key={t} tone={t}>{t}</Chip>)}
                  <Chip tone="blue" onRemove={() => notWired('remove scope chip')}>M2_aug fs1 · CH3_A2</Chip>
                  <Chip tone="outline" dot="var(--green)" prefix="status">unadjudicated</Chip>
                  <Chip tone="blue" size="sm" onClick={() => notWired('filter by recording')}>3 rec</Chip>
                </div>
                <L>Badges</L>
                <div className="k-gal-row">{STATUSES.map(s => <Badge key={s} status={s} />)}<Badge status="running">running · marked 11:40</Badge></div>
                <L>Stat tiles · KeyValue</L>
                <div className="k-gal-grid2">
                  <StatRow><StatTile label="local" value="≈ 5.6 h" caption="3 arms + 5 model nulls" tone="amber" /><StatTile label="disk" value="3.9 GB" caption="images + window set" /><StatTile label="HPC" value="≈ 1.4 h" caption="1 GPU node" /></StatRow>
                  <KeyValue align="right" items={[{ k: 'duration', v: '21 s ± 4' }, { k: 'mean member d', v: '0.24' }, { k: 'judged', v: '44 of 112', tone: 'amber' }, { k: 'edges', v: 'z-norm Euclid · cut 0.42' }]} />
                </div>
                <StatRow columns={4} style={{ marginTop: 10 }}><StatTile variant="flat" label="macro F1 · test" value="0.71" tone="green" caption="0.66–0.75 · bootstrap" /><StatTile variant="flat" label="balanced accuracy" value="0.70" caption="4 classes" /><StatTile variant="flat" label="RF baseline F1" value="0.58" caption="same windows" /><StatTile variant="flat" label="test windows" value="432" caption="scored once" /></StatRow>
                <L>Progress · Stepper · Checklist · Kbd · ColourDot</L>
                <div className="k-gal-grid3">
                  <div className="stack">
                    <ProgressBar value={0.62} eta="4 min left" />
                    <ProgressBar value={0.27} tone="green" label="27 %" />
                    <ProgressBar indeterminate eta="queued on hpc-1" tone="purple" />
                    <div className="row"><Button size="sm" variant="primary" icon="play" disabled={sim.busy} disabledReason="already running" onClick={() => sim.start({ steps: ['Baseline', 'Matrix profile', 'Threshold'], stepMs: 700 })} testid="kit-sim-start">Simulate run</Button><Badge status={sim.status === 'idle' ? 'new' : sim.status === 'done' ? 'done' : sim.status === 'cancelled' ? 'cancelled' : sim.status === 'failed' ? 'failed' : 'running'}>{sim.status}</Badge></div>
                    {sim.status !== 'idle' && <ProgressBar value={sim.fraction} label={`${Math.round(sim.fraction * 100)} % · ${sim.steps[sim.step] ?? ''}`} />}
                  </div>
                  <Stepper steps={[{ label: 'Source', state: 'done' }, { label: 'Bandpass filter', detail: 'cached', state: 'done' }, { label: 'Matrix profile', detail: 'sent to cluster', state: 'current' }, { label: 'Threshold to spans', detail: 'waits', state: 'todo' }]} />
                  <div className="stack">
                    <Stepper variant="numbered" steps={[{ label: 'Scope', state: 'done' }, { label: 'Template', state: 'current' }, { label: 'Launch', state: 'todo' }]} />
                    <Checklist items={[{ label: 'beats label-shuffle null', state: 'pass' }, { label: 'burst ECE 0.11', state: 'warn' }, { label: 'import failed', state: 'fail' }]} />
                    <div className="row"><Kbd>S</Kbd> seed <Kbd>Ctrl Z</Kbd> undo {CLASSES.map(c => <ColourDot key={c.key} colour={c.colour} title={c.name} />)}</div>
                  </div>
                </div>
                <L>Callouts · EmptyState</L>
                <div className="k-gal-grid2">
                  <div className="stack">
                    <Callout tone="amber" icon="hourglass">over the 2 h local limit · Train locally is off</Callout>
                    <Callout tone="red" title="Matrix profile failed" action={<Button size="sm" onClick={() => notWired('open run log')}>Run log</Button>}>MemoryError at step 2 · 3 stages left</Callout>
                    <Callout tone="blue">used as the recommended value in Threshold to spans</Callout>
                    <Callout tone="amber" stacked title="CH3_A2 + CH4_A2 share ground for F-03" action={<Button icon="minus" onClick={() => notWired('deselect CH4_A2')}>Deselect CH4_A2</Button>}>Browsing both double-counts that family.</Callout>
                  </div>
                  <EmptyState icon="inbox" title="No runs yet" caption="apply a saved template or a seed search to this scope" bordered action={<Button variant="primary" icon="plus" onClick={() => setModal(true)}>Add runs</Button>} />
                </div>
                <L>CodeBlock</L>
                <CodeBlock code={SLURM} title="SLURM script" filename="train_cnn.sh" highlight={[2]} testid="kit-code" />
              </Card>
            </Sec>

            {/* ---------------- table ---------------- */}
            <Sec id="table" title="Table" sub="sortable · multi-select · highlighted row · groups · empty state">
              <SectionCard title="All jobs" subtitle="sorted by what needs you first" flush actions={<span className="mono small muted">{selected.length} selected</span>}>
                <Table columns={columns} rows={JOB_ROWS} rowKey={r => r.id} selection="multi" selected={selected} onSelectionChange={setSelected} highlighted={hl} onRowClick={r => setHl(r.id)}
                  groupBy={r => r.kind === 'cluster' ? 'Cluster jobs · status marked by hand' : 'Paused and local'} groupIcon={g => g.startsWith('Cluster') ? 'server' : 'pause'} testid="kit-table"
                  footer={<><span>{selected.length} selected</span><Button size="sm" icon="tag" disabled={!selected.length} disabledReason="select rows first" onClick={() => notWired('add tag')}>Add tag</Button><Spacer /><Pager format="range" page={1} pageCount={1} total={JOB_ROWS.length} pageSize={10} onPage={() => undefined} /></>} />
              </SectionCard>
              <Card padding="none"><Table columns={columns} rows={[]} rowKey={r => r.id} dense empty={<EmptyState size="sm" icon="search" title="No jobs match" caption="clear a filter to see more" />} /></Card>
            </Sec>

            {/* ---------------- chain ---------------- */}
            <Sec id="chain" title="Chain & glyphs" sub="ChainRibbon (tiles · chips · thumbs) · BlockGlyph registry">
              <Card>
                <ChainRibbon variant="chips" current={block} onSelect={setBlock} testid="kit-ribbon" blocks={[
                  { id: 'base', index: 1, label: 'Baseline removal', signature: 'Signal → Signal', status: 'cached' },
                  { id: 'mp', index: 2, label: 'Matrix profile', signature: 'Signal → Scores', status: 'running' },
                  { id: 'thr', index: 3, label: 'Threshold to spans', signature: 'Scores → SpanSet', status: 'stale' },
                  { id: 'x', index: 4, label: 'Drop detection', signature: 'Encoding → SpanSet', status: 'invalid', disabled: true, reason: 'expects Encoding, receives SpanSet' },
                ]} />
                <div style={{ height: 12 }} />
                <div className="k-gal-row"><ChainRibbon variant="thumbs" blocks={[{ id: 'a', label: 'Baseline', glyph: 'baseline' }, { id: 'b', label: 'Matrix profile', glyph: 'matrix_profile' }, { id: 'c', label: 'Threshold', glyph: 'threshold' }]} /><span className="muted mono small">thumbs</span></div>
                <L>glyph aliases</L>
                <div className="k-gal-row">{Object.keys(GLYPH_ALIASES).map(k => <span key={k} className="stack" style={{ gap: 2, alignItems: 'center' }}><BlockGlyph name={k} /><span className="mono" style={{ fontSize: 9.5, color: 'var(--muted)' }}>{k}</span></span>)}</div>
              </Card>
            </Sec>

            {/* ---------------- forms ---------------- */}
            <Sec id="forms" title="Forms" sub="Field · TextField · NumberField (validates) · SelectField · Toggle · Checkbox · Slider · RangeSlider · RadioCards">
              <Card>
                <div className="k-gal-grid2">
                  <div className="stack" style={{ gap: 4 }}>
                    <Field inline label="environment setup" hint="runs before every job"><TextField value={text} onChange={setText} width={190} testid="kit-text" /></Field>
                    <Field inline label="run locally up to" info="Above this the stage offers Create SLURM script." hint={num != null ? `saved ${num} min` : ''}><NumberField value={num} onValid={setNum} min={1} max={120} unit="min" testid="kit-number" /></Field>
                    <Field inline label="local jobs at once" hint="invalid example: 1–16"><NumberField value={bad} onValid={setBad} min={1} max={16} integer testid="kit-number-invalid" /></Field>
                    <Field inline label="profile"><SelectField value={sel} onChange={setSel} options={[{ value: 'gpu-single', label: 'gpu-single' }, { value: 'cpu-array', label: 'cpu-array' }, { value: 'gpu-multinode', label: 'gpu-multinode', disabled: true, reason: 'check the job can use 2 nodes' }]} testid="kit-select" /></Field>
                    <Field inline label="email on finish"><Toggle checked={toggle} onChange={setToggle} testid="kit-toggle" /></Field>
                    <Field inline label="M4_aug"><Toggle checked={false} onChange={() => undefined} label="locked" disabled disabledReason="held out · Settings › Datasets" /></Field>
                  </div>
                  <div className="stack">
                    <Field label="verdict">{(['seed', 'interesting', 'artifact'] as const).map(v => <Checkbox key={v} checked={!!checks[v]} onChange={c => setChecks(s => ({ ...s, [v]: c }))} label={v} dot={v === 'seed' ? '#0A84FF' : v === 'interesting' ? '#22A06B' : '#E5484D'} count={{ seed: 12, interesting: 412, artifact: 38 }[v]} dimWhenOff />)}<Checkbox checked={false} onChange={() => undefined} label="reviewed coverage" disabled disabledReason="no reviews in this database" /></Field>
                    <Field label="cut" aside={slider.toFixed(2)}><Slider value={slider} onChange={setSlider} min={0} max={1} step={0.01} format={v => v.toFixed(2)} showValue={false} marks={[{ value: 0, label: '0' }, { value: 0.42, label: '0.42' }, { value: 1, label: '1' }]} ariaLabel="cut" testid="kit-slider" /></Field>
                    <Field label="channel section (h)"><RangeSlider value={range} onChange={setRange} min={0} max={721} format={v => `${v} h`} ariaLabel="section" testid="kit-range" /></Field>
                    <RadioCards value={radio} onChange={setRadio} ariaLabel="sources" options={[{ value: 'channels', title: 'Channels', description: 'each channel is a source', icon: 'wave' }, { value: 'ws', title: 'Saved window set', description: 'ws_M2aug_3ch_600s v1', icon: 'grid' }, { value: 'heldout', title: 'M4_aug', description: 'held-out recording', icon: 'lock', disabled: true, reason: 'held out (D6)' }]} testid="kit-radio" />
                  </div>
                </div>
              </Card>
            </Sec>

            {/* ---------------- plots ---------------- */}
            <Sec id="plots" title="Plots" sub="Trace · MiniTrace · LineChart · Histogram · Bars · Scatter · Heatmap · BandStrip · NullBand · SmallMultiples">
              <SectionCard title="Candidate in context" subtitle="Trace · hours axis · band · overlay" testid="kit-trace">
                <Trace values={trace} fs={1} t0={192.338 * 3600} height={170} bands={[{ start_s: 192.338 * 3600 + 230, end_s: 192.338 * 3600 + 340, kind: 'detected', label: 'c-0343 · 35.0 s' }]} />
              </SectionCard>
              <div className="k-gal-grid2">
                <SectionCard title="Shape vs F-03 medoid · mV" subtitle="Trace · seconds axis">
                  <Trace values={trace.slice(200, 360)} timeUnit="s" overlays={[{ values: medoid.slice(200, 360), stroke: 'var(--purple)', label: 'F-03 medoid' }]} stroke="var(--blue)" height={150} />
                </SectionCard>
                <SectionCard title="Against baseline and null" subtitle="Histogram · markers · CI band · dots">
                  <Histogram values={nullDraws} domain={[0, 1]} nBins={40} markers={[{ x: 0.58, label: 'RF 0.58', colour: 'var(--text)' }, { x: 0.71, label: 'A 0.71', colour: 'var(--green)', band: [0.66, 0.75] }]} dots={[{ x: 0.24 }, { x: 0.26 }, { x: 0.27 }, { x: 0.29 }]} height={170} showCounts={false} />
                </SectionCard>
              </div>
              <div className="k-gal-grid2">
                <SectionCard title="Confusion" subtitle="Heatmap · green ramp">
                  <Heatmap rows={['spike-train', 'plateau', 'burst', 'slow-drift']} cols={['s-tr', 'plat', 'burst', 's-dr']} values={[[0.78, 0.08, 0.04, 0.1], [0.12, 0.66, 0.01, 0.2], [0.16, 0.03, 0.52, 0.29], [0.04, 0.07, 0.03, 0.86]]} ramp="green" format={v => v.toFixed(2)} legendLabel="row-normalised" cellHeight={34} />
                </SectionCard>
                <SectionCard title="Where each family occurs" subtitle="Heatmap · nulls, flagged, selected column">
                  <Heatmap rows={FAMILIES.map(f => `${f.id} ${f.name}`)} cols={['CH1_A1', 'CH2_A1', 'CH3_A2', 'CH4_A2', 'CH2']} values={[[0.7, 0.94, 0.21, 0.6, null], [null, 0.18, 0.21, 0.16, 0.68], [0.82, 0.61, 0.61, 0.8, 0.23], [0.88, 0.6, 0.79, 0.75, null]]} flagged={(r, c) => r === 2 && (c === 1 || c === 2)} selectedCols={[3]} onCellClick={(r, c) => notWired(`open family ${r} on channel ${c}`)} legendLabel="members / h" />
                </SectionCard>
              </div>
              <div className="k-gal-grid3">
                <SectionCard title="Training curves" subtitle="LineChart"><LineChart height={160} markers={[{ x: 21, label: 'early stop · epoch 21' }]} series={[{ label: 'train', colour: 'var(--blue)', points: Array.from({ length: 30 }, (_, i) => [i + 1, 0.3 + 1.2 * Math.exp(-i / 7)] as [number, number]) }, { label: 'validation', colour: 'var(--trace-orange)', points: Array.from({ length: 30 }, (_, i) => [i + 1, 0.45 + 1.1 * Math.exp(-i / 6) + (i > 21 ? (i - 21) * 0.01 : 0)] as [number, number]) }]} /></SectionCard>
                <SectionCard title="Windows per class" subtitle="Bars · stacked"><Bars height={160} mode="stacked" categories={CLASSES.slice(0, 4).map(c => c.name)} series={[{ key: 'train', label: 'train', colour: '#a8c1ec', values: [412, 268, 190, 620] }, { key: 'val', label: 'val', colour: '#fdc77e', values: [61, 38, 27, 92] }, { key: 'test', label: 'test', colour: '#86d69e', values: [118, 74, 31, 209] }]} /></SectionCard>
                <SectionCard title="Calibration" subtitle="Scatter · diagonal · click selects"><ScatterDemo /></SectionCard>
              </div>
              <div className="k-gal-grid2">
                <SectionCard title="Evaluation blocks" subtitle="BandStrip">
                  <BandStrip domain={[0, 721 * 3600]} timeUnit="h" rows={['CH2_A1', 'CH4_A2', 'CH7_B2'].map((ch, r) => ({ label: ch, segments: Array.from({ length: 10 }, (_, i) => ({ start: i * 72.1 * 3600, end: (i + 1) * 72.1 * 3600, kind: ((i + r) % 5 === 3 ? 'test' : (i + r * 2) % 7 === 5 ? 'validation' : 'train') as 'train' | 'validation' | 'test' })) }))}
                    legend={[{ label: 'train', colour: '#a8c1ec' }, { label: 'validation', colour: '#fdc77e' }, { label: 'test — scored once, after training', colour: '#86d69e' }]} />
                </SectionCard>
                <SectionCard title="Spans vs cut" subtitle="NullBand">
                  <NullBand x={Array.from({ length: 40 }, (_, i) => i * 0.25)} values={Array.from({ length: 40 }, (_, i) => 40 * Math.exp(-i / 9) + 3)} p5={Array.from({ length: 40 }, (_, i) => 10 * Math.exp(-i / 6))} p95={Array.from({ length: 40 }, (_, i) => 22 * Math.exp(-i / 7) + 2)} threshold={{ value: 8, label: 'threshold 8' }} xLabel="σ" height={150} />
                </SectionCard>
              </div>
              <SectionCard title="F-03 sharkfin members" subtitle="SmallMultiples · cap 10 · shared y · MiniTrace">
                <SmallMultiples items={members} getValues={v => v} cap={10} columns={5} testid="kit-sm"
                  render={(v, ctx) => <MiniTrace values={v} yDomain={ctx.yDomain} width="100%" height={48} overlays={[{ values: members[0], stroke: FAMILY_COLOURS['F-03'] }]} title={`member ${ctx.index + 1}`} />} />
                <div className="k-gal-row" style={{ marginTop: 10 }}>{FAMILIES.map((f, i) => <span key={f.id} className="row mono small"><MiniTrace values={members[i * 3]} yDomain={shared} width={90} height={30} stroke={f.colour} />{f.id}</span>)}</div>
              </SectionCard>
            </Sec>
          </div>
        </div>
      </Page>
    </>
  )
}

function ScatterDemo() {
  const [sel, setSel] = useState<string[]>([])
  const pts = useMemo(() => Array.from({ length: 30 }, (_, i) => ({ id: `p${i}`, x: i / 29, y: Math.min(1, Math.max(0, i / 29 + Math.sin(i) * 0.08)), category: CLASSES[i % 4].name })), [])
  return <Scatter points={pts} xDomain={[0, 1]} yDomain={[0, 1]} height={160} diagonal colours={Object.fromEntries(CLASSES.map(c => [c.name, c.colour]))} selected={sel} onSelect={id => setSel(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])} xLabel="score" legend={false} testid="kit-scatter" />
}
