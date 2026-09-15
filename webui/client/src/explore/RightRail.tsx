/* Corpus right rail (frame explore-1): a filter/options list, not a legend. Show and Verdict are live
   (the Verdict ticks refetch coverage with `verdicts=`); reviewed coverage, unreviewed only, Detections
   from and Morphology tag have no bridge endpoint and are demo-backed (§0 canon, marked `demo`). The foot
   reads "matching N spans / across K of M channels" — live, or the demo tag count when a tag is ticked. */
import type { Coverage } from '../api'
import type { CorpusDemo } from '../api/explore'
import { Checkbox, fmtInt } from '../kit'
import { DemoTag, MultiPick, SectionHead } from './bits'
import { VERDICT_COLOUR, VERDICTS } from './util'

export interface ShowState { annotations: boolean; detections: boolean; reviewed: boolean; unreviewedOnly: boolean }
export interface DemoFilters { runs: string[] | null; methods: string[] | null; tags: string[] }

export function RightRail({ cov, demo, show, setShow, verdicts, setVerdicts, filters, setFilters, matching }: {
  cov: Coverage | null; demo: CorpusDemo | null
  show: ShowState; setShow: (s: ShowState) => void
  verdicts: string[]; setVerdicts: (v: string[]) => void
  filters: DemoFilters; setFilters: (f: DemoFilters) => void
  matching: { spans: number; channels: number; total: number; demo: boolean; note?: string }
}) {
  const toggleVerdict = (v: string) => setVerdicts(verdicts.includes(v) ? verdicts.filter(x => x !== v) : VERDICTS.filter(x => x === v || verdicts.includes(x)))
  const counts = cov?.verdict_counts ?? {}
  const toggleTag = (t: string) => setFilters({ ...filters, tags: filters.tags.includes(t) ? filters.tags.filter(x => x !== t) : [...filters.tags, t] })
  const runsTotal = demo?.runs.length ?? 0
  return (
    <aside className="card ex-rail" data-testid="corpus-rail">
      <div className="sec">
        <SectionHead title="Show" info="What the map counts. Reviewed coverage shades bins someone has looked at." />
        <Checkbox checked={show.annotations} onChange={v => setShow({ ...show, annotations: v })} label="annotations" dimWhenOff testid="show-annotations" />
        <Checkbox checked={show.detections} onChange={v => setShow({ ...show, detections: v })} label="detections" dimWhenOff testid="show-detections" />
        <Checkbox checked={show.reviewed} onChange={v => setShow({ ...show, reviewed: v })} label={<>reviewed coverage <DemoTag /></>} dimWhenOff testid="show-reviewed" />
        <Checkbox checked={show.unreviewedOnly} onChange={v => setShow({ ...show, unreviewedOnly: v })} label={<>unreviewed only <DemoTag /></>} dimWhenOff testid="show-unreviewed" />
      </div>
      <div className="sec">
        <SectionHead title="Detections from" info="Only detections from these runs and methods are counted." extra={<DemoTag />} />
        <div className="ex-rail-picks">
          <MultiPick prefix="runs" allLabel={`all · ${runsTotal}`} value={filters.runs} onChange={runs => setFilters({ ...filters, runs })} testid="det-runs" title="Runs on this recording"
            options={(demo?.runs ?? []).map(r => ({ value: r.id, label: `${r.name} ${r.id}`, sub: r.method }))} />
          <MultiPick prefix="method" allLabel={`any · ${demo?.methods.length ?? 0}`} value={filters.methods} onChange={methods => setFilters({ ...filters, methods })} testid="det-method" title="Detection methods"
            options={(demo?.methods ?? []).map(m => ({ value: m, label: m }))} />
        </div>
      </div>
      <div className="sec">
        <SectionHead title="Verdict" info="Annotations with these verdicts are counted. Verdicts are given in Review." />
        {VERDICTS.map(v => (
          <Checkbox key={v} checked={verdicts.includes(v)} onChange={() => toggleVerdict(v)} dot={VERDICT_COLOUR[v]} label={v} dimWhenOff
            count={cov ? fmtInt(counts[v] ?? 0) : '—'} testid={`verdict-${v}`} />
        ))}
      </div>
      <div className="sec">
        <SectionHead title="Morphology tag" info="A tag that clusters on a few channels is a lead. This database has no tags yet: the counts are §0 demo canon." extra={<DemoTag />} />
        {(demo?.tags ?? []).map(t => (
          <Checkbox key={t} checked={filters.tags.includes(t)} onChange={() => toggleTag(t)} label={t} dimWhenOff testid={`tag-${t}`}
            count={demo ? fmtInt(demo.channels.reduce((s, c) => s + (c.tagCounts[t] ?? 0), 0)) : undefined} />
        ))}
        <div className="muted small mono" style={{ marginTop: 4 }} data-testid="tags-caption">no tags in this database · demo counts</div>
      </div>
      <div className="sec foot" data-testid="rail-matching" data-demo={matching.demo ? '1' : '0'}>
        <div className="row between">
          <SectionHead title={<span className="k">matching</span>} info="Spans that pass every filter, and how many channels they fall on." extra={matching.demo ? <DemoTag /> : undefined} />
          <b data-testid="matching-spans">{fmtInt(matching.spans)} spans</b>
        </div>
        <div className="muted small mono">across {matching.channels} of {matching.total} channels</div>
        {matching.note && <div className="ex-note-amber" data-testid="matching-note">{matching.note}</div>}
      </div>
    </aside>
  )
}
