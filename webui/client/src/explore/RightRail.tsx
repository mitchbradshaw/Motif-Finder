/* Corpus right rail (frame explore-1): a filter/options list, not a legend.

   Everything in this rail is LIVE. `getCorpusLive` reads the run and method lists from
   GET /api/corpus/{file}/runs and the tag vocabulary, per-channel tag counts and reviewed coverage
   from GET /api/channels/{id}/tags, for every channel, and returns `source: 'live'`.

   Until fixup-a item 13 this rail asserted the opposite in four places at once — a `demo` chip beside
   "Morphology tag", the info text "This database has no tags yet", the caption "no tags in this
   database · demo counts", and the docstring you are reading. All four were false: verified read-only
   against DATA/db/annotations.sqlite on 2026-09-22, `tag_vocabulary` holds 36 terms across 8
   categories and `annotation_tags` 11,319 rows. The foot reads "matching N spans / across K of M
   channels", live, whether or not a tag is ticked. */
import type { Coverage } from '../api'
import type { CorpusDemo } from '../api/explore'
import { Checkbox, fmtInt } from '../kit'
import { MultiPick, SectionHead } from './bits'
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
  const runsTotal = demo?.runs.length ?? 0
  /* One `MultiPick` over the whole vocabulary rather than one Checkbox per term:
   * 36 checkboxes is what prompted "make it a dropdown", and the rail already
   * uses this control for Runs and Methods (fixup-a item 14). A flat sorted
   * list — `MultiPick` has no grouping and adding one is not this fix. */
  const tagCount = (t: string) => (demo?.channels ?? []).reduce((s, c) => s + (c.tagCounts[t] ?? 0), 0)
  const tagTotal = demo?.tags.length ?? 0
  const taggedSpans = (demo?.tags ?? []).reduce((s, t) => s + tagCount(t), 0)
  return (
    <aside className="card ex-rail" data-testid="corpus-rail">
      <div className="sec">
        <SectionHead title="Show" info="What the map counts. Reviewed coverage shades bins someone has looked at." />
        <Checkbox checked={show.annotations} onChange={v => setShow({ ...show, annotations: v })} label="annotations" dimWhenOff testid="show-annotations" />
        <Checkbox checked={show.detections} onChange={v => setShow({ ...show, detections: v })} label="detections" dimWhenOff testid="show-detections" />
        <Checkbox checked={show.reviewed} onChange={v => setShow({ ...show, reviewed: v })} label="reviewed coverage" dimWhenOff testid="show-reviewed" />
        <Checkbox checked={show.unreviewedOnly} onChange={v => setShow({ ...show, unreviewedOnly: v })} label="unreviewed only" dimWhenOff testid="show-unreviewed" />
      </div>
      <div className="sec">
        <SectionHead title="Detections from" info="Only detections from these runs and methods are counted. The runs and methods are this recording's own, from GET /api/corpus/{file}/runs." />
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
        <SectionHead title="Morphology tag" info="A tag that clusters on a few channels is a lead. The terms are this database's own tag vocabulary; the counts are the annotations carrying each term on the channels below." />
        <div className="ex-rail-picks">
          <MultiPick prefix="tag" allLabel={`any · ${tagTotal}`} value={filters.tags.length ? filters.tags : null}
            onChange={tags => setFilters({ ...filters, tags: tags ?? [] })} testid="rail-tags" title="Morphology tags"
            options={(demo?.tags ?? []).map(t => ({ value: t, label: t, count: fmtInt(tagCount(t)) }))} />
        </div>
        <div className="muted small mono" style={{ marginTop: 4 }} data-testid="tags-caption">
          {tagTotal ? `${tagTotal} terms · ${fmtInt(taggedSpans)} tagged spans on these channels` : 'no tags on these channels'}
        </div>
      </div>
      <div className="sec foot" data-testid="rail-matching" data-demo={matching.demo ? '1' : '0'}>
        <div className="row between">
          <SectionHead title={<span className="k">matching</span>} info="Spans that pass every filter, and how many channels they fall on." />
          <b data-testid="matching-spans">{fmtInt(matching.spans)} spans</b>
        </div>
        <div className="muted small mono">across {matching.channels} of {matching.total} channels</div>
        {matching.note && <div className="ex-note-amber" data-testid="matching-note">{matching.note}</div>}
      </div>
    </aside>
  )
}
