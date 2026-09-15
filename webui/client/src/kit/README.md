# kit — builders' API reference

`import { Page, SectionCard, Table, Trace, … } from '../kit'` (one import; it loads `kit.css`). Live examples of every
component: **`#/kit`** (`kit/Gallery.tsx` — copy from it). Every component takes `testid` (or `data-testid`), is
keyboard reachable, and shows a focus ring.

## Conventions (read these)

- **Page skeleton.** `<Header workspace="Models" page="Launch" subtitle="train a template across channels" demo />` then
  `<Page>…</Page>`. Pass `demo` whenever the page rendered any fixture read (`api/seam.ts` → `useSourced(...).source === 'demo'`).
- **Fixture data** comes from `fixtures/canon.ts` (names, ids, counts, `syntheticTrace`, `fmtH`/`fmtS`). Never retype canon facts.
- **Deep-linkable state** (tab, open drawer/modal, sim state): `useQueryState('tab', 'launch')`, `useQueryFlag('drawer')`,
  or `<Tabs queryKey="tab" …/>`. Defaults are not written to the URL.
- **Writes stay in memory:** `const [rows, setRows] = useDemoState('models.arms', () => FIXTURE)`; log each save/verdict/apply
  with `recordDemoWrite('models', 'register', {...})`.
- **Simulated runs:** `const run = useSim('discovery.run.r-0431'); run.start({ steps: [...], stepMs: 900 })` →
  `run.status / step / fraction / busy / cancel() / reset() / force({status:'failed'})`. Render with `ProgressBar`, `Stepper`, `Badge`.
- **No dead clicks.** Anything clickable does something visible: navigate, open a surface, write to the demo store, run a sim,
  or `const notWired = useNotWired(); notWired('upload results')` (toast). **Every disabled control carries a reason**:
  `<Button disabled disabledReason="over the 2 h local limit">`, or wrap anything in `<DisabledReason reason="…">`.
- **P8 caps:** never render more than 10 small multiples / thumbnails at once — use `SmallMultiples` (cap 10, paging, resample)
  or `usePagedList(items, 10)` + `Pager`.
- **P9:** explanations live behind `InfoTip` (ⓘ), not in paragraphs on the page.
- **Colour semantics (spec §3):** blue active/machine · green human/cached · amber attention/stale · red failed/artifact ·
  purple cluster/second algorithm · grey inactive. `Badge status=` already maps these (`STATUS_TONE`). Cluster actions use
  `Button variant="cluster"` (purple); the one primary action per area uses `variant="primary"`.
- **mV and time:** traces are mV, never normalised. Thumbnails that belong together share one `yDomain`. Time axes print hours
  since recording start (`192.40 h`, `timeUnit="h"`), event durations in seconds (`fmtS`). `fmtMv(-0.34)` → `−0.34 mV`,
  `fmtInt(1284)` → `1,284`, `fmtPct(0.27)` → `27 %`.
- Icons: `<Icon name="upload" />` — names in `kit/icons.tsx` (`IconName` is typed; an unknown name warns).

## Layout
| Component | Purpose / props |
|---|---|
| `Page` | scrolling body, centred column. `{children, maxWidth=1376, gap=12}` |
| `PageTitle` | big in-page title. `{title, subtitle?, children? (chips), actions?}` |
| `Toolbar`, `Spacer`, `DividerV` | wrapping row. `{children, card?, nowrap?}` |
| `Card` | white card. `{padding='md'\|'lg'\|'none', variant='default'\|'flat'\|'grey', tone?, selected?, onClick? (becomes button)}` |
| `SectionCard` | numbered section. `{title, number?, info? (InfoTip text), subtitle?, actions?, icon?, collapsible?, defaultOpen?, open?/onToggle?, footer?, flush?}` |
| `SplitPane` | main + rails. `{children, left?, right?, leftWidth=260, rightWidth=320, gap}` |
| `Rail` | side card. `{title?, side='right', width?, collapsible?, defaultCollapsed?, actions?}` |
| `SideNav` | settings nav. `{groups: {section?, sectionIcon?, sectionTone?, label?, items: {value,label,count?,differs?,disabled?,reason?,icon?}[]}[], value, onChange, legend?}` |

```tsx
<SplitPane right={<Rail title="Before launch"><Checklist items={checks} /></Rail>}>
  <SectionCard number={1} title="Training template" info="Comes from Analyse." subtitle="from Analyse"
    actions={<Button variant="link" icon="external" onClick={() => navigate('analyse/training')}>Open in Analyse</Button>}>
    <ChainRibbon blocks={blocks} />
  </SectionCard>
</SplitPane>
```

## Navigation
| Component | Purpose / props |
|---|---|
| `Tabs` | tab bar. `{items: {value,label,icon?,count?,disabled?,reason?}[], value?, onChange?, queryKey?, variant='pill'\|'track'\|'soft'\|'underline'}` — pill = Models tabs, track = Library "Motifs 1,402", soft = drawer tabs |
| `Seg` | segmented control. `{options: {value,label,disabled?,reason?}[], value, onChange, size?, label?}` |
| `Breadcrumb` | `{items: {label, onClick?\|href?}[], links?}` — last item is current |
| `Pager` | `{page (1-based), pageCount, onPage, format='index'\|'range', total?, pageSize?}` — "‹ 233 / 344 ›" or "1–10 of 112 ‹ ›" |

```tsx
<Tabs queryKey="tab" items={[{ value: 'launch', label: 'Launch', icon: 'rocket' }, { value: 'results', label: 'Results', icon: 'bar-chart' }]} />
<Seg label="padding" options={[{ value: '30', label: '±30 s' }, { value: '120', label: '±120 s' }]} value={pad} onChange={setPad} />
```

## Surfaces (Escape / outside click go to the topmost surface; focus returns to the opener)
| Component | Purpose / props |
|---|---|
| `Modal` | dialog. `{open, onClose, title, subtitle?, children, footer?, footerNote?, size='sm'\|'md'\|'lg'\|'xl', width?, headerExtra?, flushBody?, closeOnBackdrop=true}` |
| `Drawer` | `{open, onClose, title, side='right'\|'bottom', mode='overlay'\|'inline', width?, height?, tabs?, tab?, onTab?, actions?}` |
| `Popover` | anchored, flips. `{open, onClose, anchorRef, placement='bottom-start', title?, subtitle?, width?, flush?}` |
| `PopoverButton` | button + popover. `{label, icon?, children: close => node, title?, width?}` |
| `Menu` | action list. `{trigger: props => <Button {...props}/>, items: MenuItem[], onSelect}` |
| `Dropdown` | select-like button. `{value, onChange, options: MenuItem[], prefix?, placeholder?, variant='grey'\|'outline', active?, block?, width?}` |
| `InfoTip` | ⓘ popover. `{children, title?}` |
| `Tooltip` | hover/focus tooltip. `{content, children, placement?}` |

`MenuItem = {value, label, description?, hint?, icon?, disabled?, reason?, danger?, group?}`

```tsx
const [open, setOpen] = useQueryFlag('add')
<Button variant="primary" icon="plus" onClick={() => setOpen(true)}>Add runs</Button>
<Modal open={open} onClose={() => setOpen(false)} title="Add runs" size="lg" footerNote="2 selected × 3 channels"
  footer={<><Button onClick={() => setOpen(false)}>Cancel</Button><Button variant="primary" onClick={add}>Add 2 runs</Button></>}>…</Modal>
<Dropdown prefix="test" value={test} onChange={setTest} options={[{ value: '20', label: '20 %' }]} />
<Menu trigger={p => <Button {...p} iconRight="chevron-down">Mark…</Button>} items={[{ value: 'done', label: 'Mark finished' }]} onSelect={mark} />
```
For a custom trigger, keep a ref: `const ref = useRef<HTMLButtonElement>(null); <Button ref={ref} onClick={() => setOpen(o => !o)} /> <Popover anchorRef={ref} …/>`.

## Data display
| Component | Purpose / props |
|---|---|
| `Button` | `{variant='default'\|'primary'\|'cluster'\|'success'\|'danger'\|'danger-solid'\|'ghost'\|'subtle'\|'link', size='sm'\|'md'\|'lg', icon?, iconRight?, loading?, disabled?, disabledReason?, block?, ref?}` + button attrs |
| `IconButton` | `{icon, label (required), active?, bordered?, disabledReason?}` |
| `DisabledReason` | `{reason, children, disabled=true, block?}` — tooltip + title on a disabled control |
| `Chip` | pill. `{tone='outline'\|'blue'\|'grey'\|'green'\|'amber'\|'red'\|'purple'\|'demo', size?, icon?, dot? (colour), prefix?, onClick?, onRemove?, selected?}` |
| `Badge` | status. `{status?: cached\|stale\|new\|running\|paused\|failed\|on cluster\|invalid\|done\|finished\|queued\|cancelled\|waiting\|blind\|template\|seed\|detection\|…, tone?, children? (label), dot?, size?}` |
| `StatTile`, `StatRow` | `{label, value, caption?, tone?, variant='fill'\|'flat'\|'card', size?, info?}`; `StatRow {columns?}` |
| `KeyValue` | `{items: {k, v, tone?, strong?, info?}[], align='left'\|'right', dense?, lines?, labelWidth?}` |
| `EmptyState` | `{icon?, title, caption?, action?, size?, bordered?}` |
| `ProgressBar` | `{value 0–1, indeterminate?, label?, eta?, tone?, size?, labelPosition='right'\|'top'\|'none', width?}` |
| `CodeBlock` | dark block with Copy (clipboard + toast) and Save (not-wired toast). `{code, title?, filename='script.sh', lineNumbers?, highlight? (1-based), copy?, save?, onSave?, maxHeight?}` |
| `Callout` | tinted strip. `{tone='amber', icon? (null hides), title?, children, action?, outlined?, stacked?}` |
| `Stepper` | `{steps: {label, detail?, state: done\|current\|running\|todo\|failed\|paused}[], variant='pills'\|'numbered', orientation?, onSelect?}` |
| `Checklist` | `{items: {label, state: pass\|warn\|fail\|pending}[], columns?}` |
| `ColourDot`, `Kbd` | `{colour, size=8, ring?, title?}`; `{children, size?, dark?}` |

```tsx
<Callout tone="amber" icon="hourglass">over the 2 h local limit · Train locally is off</Callout>
<StatRow><StatTile label="local" value="≈ 5.6 h" caption="3 arms + 5 model nulls" tone="amber" /><StatTile label="disk" value="3.9 GB" /></StatRow>
<CodeBlock title="SLURM script" code={script} filename="train.sh" />
```

## Table
`Table<T>` `{columns: Column<T>[], rows, rowKey, selection='none'|'single'|'multi', selected?, onSelectionChange?, onRowClick?, highlighted?,
rowTone? (row => 'amber'|'red'|'dim'), groupBy?, groupLabel?, groupIcon?, sort?/onSortChange?/defaultSort?, empty?, stickyHeader=true, dense?, maxHeight?, footer?}`
`Column<T> = {key, header, render?(row,i), sortValue?(row), width?, align?}`. In cells, `className="primary-text"` / `"sub-text"` give the two-line job cell.

```tsx
<Table rows={jobs} rowKey={j => j.id} selection="multi" selected={sel} onSelectionChange={setSel} highlighted={openId} onRowClick={j => setOpenId(j.id)}
  groupBy={j => j.group} columns={[{ key: 'id', header: 'id', sortValue: j => j.id }, { key: 'status', header: 'status', render: j => <Badge status={j.status} /> }]}
  empty={<EmptyState size="sm" title="No jobs match" caption="clear a filter" />} />
```

## Chain & glyphs
| Component | Purpose / props |
|---|---|
| `ChainRibbon` | `{blocks: {id, label, glyph?, index?, signature?, status?, disabled?, reason?}[], current?, onSelect?, variant='tiles'\|'chips'\|'thumbs', trailing?}` |
| `BlockGlyph` | `{name (alias from GLYPH_ALIASES or registry name), input?, output?, width=44, height=26}` — `SourceGlyph` for the source tile |
| `Glyph` | the analyse registry component (`adapter={name,input_kind,output_kind}`), re-exported |

Aliases: baseline, bandpass, highpass, lowpass, noise_floor, surrogate, sax, symbol_smoothing, gramian, image_encode, stft,
matrix_profile, seeded_search, threshold, drop_detection, spike, rupture, model_stage, sliding_windows, window_matrix, cluster, classifier, model.

## Forms
| Component | Purpose / props |
|---|---|
| `Field` | `{label?, hint?, error?, info?, required?, aside?, inline? (settings row: label · control · hint), labelWidth?, children}` |
| `TextField` | `{value, onChange, placeholder?, prefix?, suffix?, icon?, width?, block?, invalid?, variant='grey'\|'outline', multiline?, onEnter?, disabled?, disabledReason?}` |
| `NumberField` | validates while typing; red + inline reason; `onValid` fires only with valid numbers. `{value, onValid, onChange?(raw, reason), min?, max?, step?, integer?, unit?, validate?, changed?, width?}`; `validateNumber(raw, opts)` |
| `SelectField` | native select. `{value, onChange, options: {value,label,disabled?,reason?}[], width?, variant?}` |
| `Toggle` | switch. `{checked, onChange, label?, disabled?, disabledReason?, tone='green'\|'blue', size?}` |
| `Checkbox` | `{checked, onChange, label?, dot?, count?, indeterminate?, dimWhenOff?, disabled?, disabledReason?}` |
| `Slider` | `{value, onChange, min, max, step?, marks?: {value,label}[], format?, showValue?}` |
| `RangeSlider` | `{value: [lo, hi], onChange, min, max, step?, marks?, format?}` |
| `RadioCards` | `{options: {value,title,description?,icon?,badge?,disabled?,reason?}[], value, onChange, columns=2}` |

```tsx
<Field inline label="run locally up to" hint="above the limit the work goes to the cluster">
  <NumberField value={limit} onValid={setLimit} min={1} max={120} integer unit="min" />
</Field>
```

## Plots (all fluid-width unless `width` is set)
| Component | Purpose / props |
|---|---|
| `Trace` | mV series. `{values, fs=1, t0=0 (s), timeUnit='h'\|'s'\|'none', yDomain?, height=140, stroke?, overlays?: {values,stroke,label?}[], bands?: {start_s,end_s,kind: detected\|annotated\|selected\|artifact\|grey,label?}[], markers?: {t,label?,colour?}[], onBandClick?, ground='white'\|'grey', crosshair=true}` |
| `MiniTrace` | thumbnail. `{values, yDomain (required, shared), width=120 \| '100%', height=36, stroke?, overlays?, band?: [i0,i1], ground='grey'}` |
| `LineChart` | `{series: {label,colour,points:[x,y][],dashed?,dots?}[], xDomain?, yDomain?, markers?, hLines?, diagonal?, xLabel?, yLabel?, legend=true}` |
| `Histogram` | `{values? \| bins?, nBins=20, domain?, overlay?, threshold?: {value,label?}, markers?: {x,label?,colour?,band?}[], dots?, highlightBin?, showCounts=true}`; `binValues()` |
| `Bars` | `{categories, series: {key,label,colour,values}[], mode='grouped'\|'stacked', yMax?, valueLabels=true, highlight?, onBarClick?}` |
| `Scatter` | `{points: {x,y,id,category?,label?}[], colours?, xDomain?, yDomain?, selected?, onSelect?, diagonal?, r=3}` |
| `Heatmap` | tiles. `{rows, cols, values: (number\|null)[][], domain=[0,1], ramp='blue'\|'green'\|'amber'\|'purple'\|'diverging'\|string[], showValues, format, cellHeight=30, flagged?(r,c), selectedCols?, selectedRows?, onCellClick?, legendLabel?}` |
| `BandStrip` | `{rows: {label, segments: {start,end,kind?: train\|validation\|test\|gap\|BandKind, colour?, label?}[]}[], domain [s0,s1], timeUnit='none'\|'h'\|'s', legend?}` |
| `NullBand` | `{values, p5, p95, p50?, x?, threshold?, xLabel?, yLabel?, labels?}` |
| `SmallMultiples` | `{items, render(item, {yDomain, index}), getValues? \| yDomain?, cap=10, columns=5, title?, onSelect?, selectedIndex?}` — pages "1–10 of 112", seeded "resample" |
| `Legend` | `{items: {label, colour, shape?: 'box'\|'line'\|'dot'}[]}` |

```tsx
<Trace values={trace} t0={192.338 * 3600} bands={[{ start_s, end_s, kind: 'detected', label: 'c-0343 · 35.0 s' }]} />
<SmallMultiples items={members} getValues={m => m.values} cap={10}
  render={(m, { yDomain }) => <MiniTrace values={m.values} yDomain={yDomain} width="100%" height={48} />} />
```

## Hooks / helpers
`useQueryState(key, default)` · `useQueryFlag(key)` · `usePagedList(items, pageSize=10)` → `{items, page, pageCount, setPage, next, prev, label, total, from, to}` ·
`copyToClipboard(text): Promise<boolean>` · `fmtInt` `fmtMv` `fmtPct` · `useControllable` · `sampleIndices(n, k, seed)` · `cx(...classes)` ·
re-exported: `useDemoState` `recordDemoWrite` `useDemoWrites` `useSim` `useNotWired`.
