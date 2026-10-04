/* fixup-v: what the Library knows about one PAIR of spans — the edges — drawn on the Family page.
 *
 * A grouping says "these spans cluster together under one distance"; an edge says "this span was found by searching
 * for that exemplar, and here is how far apart they are under each distance function". Three pieces here:
 *
 *  - `EdgeList`: one row per edge — distance function, value, threshold, scale factor, the run, the recipe. The
 *    threshold on a seed-search edge is the run's cut; membership was a person's accepting verdict (Q39), so a value
 *    past it is a measurement, not a contradiction, and the row says which side of it the value sits.
 *  - `MatchedMembers`: the members a seed search added (or re-found), which the grouping does not hold — groupings
 *    and edges are different facts, and this page does not fold one into the other.
 *  - `ScaleReadout`: the Q3 read-out for the exemplar. Per scale factor: matches found · judged · accepted, the same
 *    pairs' distance under the scale-invariant function beside the native-length control, and the null per length.
 *    Counts and distances only; no test of significance is run, and none is printed. */
import { useState } from 'react'
import { Button, EmptyState, Icon, InfoTip, MiniTrace } from '../kit'
import { navigate } from '../state'
import type { LibEdge, LibMatchedMember, LibReadoutRow, LibReadoutRun, LibScaleReadout, LibSpread } from '../api'
import { centreTrace } from './chrome'

/** The fields fixup-v adds to the Family read, declared here rather than widened in `fixtures/library.ts`. */
export type EdgeFamilyExtras = { exemplarEntryId?: number | null }
export type EdgeDetailExtras = { matched?: LibMatchedMember[]; scaleReadout?: LibScaleReadout | null; members?: { id: string; edges?: LibEdge[] }[] }

const fmt = (v: number | null | undefined, d = 2) => v == null ? '—' : v.toFixed(d)
const fmtScale = (s: number | null) => s == null ? '—' : `${s}×`

export function EdgeList({ edges, testid = 'edge-list', limit }: { edges: LibEdge[]; testid?: string; limit?: number }) {
  const [all, setAll] = useState(false)
  if (!edges.length) return <span className="lib-cap" data-testid={`${testid}-none`}>no edges · nothing has measured this span against another yet</span>
  const shown = all || !limit ? edges : edges.slice(0, limit)
  return (
    <div data-testid={testid}>
      <table className="lib-scores" style={{ width: '100%' }}>
        <thead><tr><th>distance</th><th>value</th><th>threshold</th><th>scale</th><th>to</th><th>run · recipe</th></tr></thead>
        <tbody>
          {shown.map(e => (
            <tr key={e.id} data-testid={`edge-${e.id}`} data-function={e.function}>
              <td>{e.functionLabel}</td>
              <td className="mono" style={{ color: e.within ? undefined : 'var(--purple)' }}>{fmt(e.value, 3)}</td>
              <td className="mono" title={String((e.recipe?.threshold_is as string | undefined) ?? '')}>{e.threshold == null ? '—' : `${e.within ? '≤' : '>'} ${fmt(e.threshold)}`}</td>
              <td className="mono">{fmtScale(e.scale)}</td>
              <td className="mono">{e.other}</td>
              <td className="mono small">
                {e.runKey
                  ? <button type="button" className="lib-plain mono" style={{ color: 'var(--blue-600)', fontSize: 11 }} onClick={() => navigate(`discovery/runs?run=${encodeURIComponent(e.runKey!)}`)}>{e.run}</button>
                  : e.run}
                {' · '}<span title={e.recipe ? JSON.stringify(e.recipe, null, 1) : 'no recipe stored on this edge'}>{e.recipeHash.slice(0, 10)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {limit && edges.length > limit && <Button variant="link" size="sm" onClick={() => setAll(!all)} testid={`${testid}-more`}>{all ? 'fewer' : `all ${edges.length} edges`}</Button>}
    </div>
  )
}

export function MatchedMembers({ matched, entryLabel }: { matched: LibMatchedMember[]; entryLabel: string | null }) {
  const [open, setOpen] = useState<string | null>(null)
  if (!matched.length) return null
  const sel = matched.find(m => m.id === open) ?? null
  return (
    <section className="k-card" style={{ padding: 12 }} data-testid="matched-members" aria-label="Members found by seed search">
      <div className="row" style={{ gap: 8 }}>
        <b style={{ fontSize: 13 }}>Found by seed search · {matched.length} member{matched.length === 1 ? '' : 's'}</b>
        <InfoTip title="Members found by seed search">
          These spans were found by searching for {entryLabel ?? 'the exemplar'} and accepted by a person. Each carries an
          edge per distance function. They are not members of this grouping: a grouping is recomputed from the whole
          Library, and an edge is evidence about one pair — the page keeps the two apart.
        </InfoTip>
      </div>
      <div className="lib-member-grid" style={{ marginTop: 8 }}>
        {matched.map(m => (
          <button key={m.id} type="button" className="lib-plain" onClick={() => setOpen(open === m.id ? null : m.id)} data-testid={`matched-${m.id}`}
            style={{ border: `1px solid ${open === m.id ? 'var(--purple)' : 'var(--border)'}`, borderRadius: 6, padding: 6, textAlign: 'left', display: 'grid', gap: 2 }}>
            <span className="row mono small" style={{ justifyContent: 'space-between' }}><b>{m.id}</b><span className="muted">{m.scales.map(s => `${s}×`).join(' ')}</span></span>
            {m.trace.length
              ? <MiniTrace values={centreTrace(m.trace.filter((v): v is number => v != null))} width={140} height={34} ground="white" stroke="#374151" />
              : <span className="lib-cap">no waveform on disk</span>}
            <span className="lib-cap">{m.channel} · {m.onsetH.toFixed(2)} h · {m.durationS} s · {m.verdict}</span>
            <span className="lib-cap">{m.entry} · {m.edges.length} edges</span>
          </button>
        ))}
      </div>
      {sel && <div style={{ marginTop: 8 }}><div className="lib-cap" style={{ marginBottom: 4 }}>{sel.id} · found by {sel.foundBy}</div><EdgeList edges={sel.edges} testid="matched-edges" /></div>}
    </section>
  )
}

const spreadCell = (s: LibSpread | undefined) => !s || !s.n ? <span className="muted">—</span>
  : <span title={`n ${s.n} · range ${fmt(s.min)}–${fmt(s.max)} · ${s.within} of ${s.n} at or under the run's cut ${fmt(s.threshold)}`}>{fmt(s.median)} <span className="muted">({s.within}/{s.n} ≤ cut)</span></span>

function ReadoutTable({ run }: { run: LibReadoutRun }) {
  return (
    <table className="lib-scores" style={{ width: '100%' }} data-testid="scale-readout-table">
      <thead><tr>
        <th>scale</th><th>found</th><th>judged</th><th>accepted</th><th>members</th>
        <th>scale-invariant d <InfoTip title="scale-invariant">Both spans resampled to one length, z-normalised, Euclidean — shape independent of duration. Median over the accepted pairs, and how many sit at or under the run's cut.</InfoTip></th>
        <th>native-length d <InfoTip title="native-length control">z-normalised Euclidean at native length, no resampling: a pair identical in shape but differing in duration is far apart under it. The control.</InfoTip></th>
        <th>symbolic d</th>
        <th>null per draw <InfoTip title="the null per length">The paired null runs' spans at this length, per draw ({run.nullDraws} draws per channel). Beside the counts, not tested against them.</InfoTip></th>
      </tr></thead>
      <tbody>
        {run.rows.map((r: LibReadoutRow) => (
          <tr key={r.scale} data-testid={`readout-row-${r.scale}`}>
            <td className="mono">{r.scale}×</td><td>{r.found}</td><td>{r.judged}</td><td>{r.accepted}</td><td>{r.members}</td>
            <td className="mono">{spreadCell(r.scale_invariant)}</td>
            <td className="mono">{spreadCell(r.native_length)}</td>
            <td className="mono">{spreadCell(r.symbolic_sax)}</td>
            <td className="mono">{r.nullPerDraw == null ? 'no null drawn' : r.nullPerDraw.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function ScaleReadout({ readout }: { readout: LibScaleReadout | null | undefined }) {
  const [pick, setPick] = useState(0)
  if (!readout) return null
  const run = readout.runs[Math.min(pick, Math.max(0, readout.runs.length - 1))] ?? null
  const sharkfin = readout.shape === 'sharkfin' || /sharkfin/.test(readout.morphology)
  return (
    <section className="k-card" style={{ padding: 12 }} data-testid="scale-readout" aria-label="Identity under scale">
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <b style={{ fontSize: 13 }}>Does {readout.entry} keep its identity at other scales?</b>
        <InfoTip title="The scale read-out (Q3)">
          Search for the exemplar at lengths it was never defined at (Discovery › Seed search, scale bank), judge the
          matches in Review, add the accepted ones here. Then, per length: how many were found, judged and accepted, and
          the same pairs' distance under the scale-invariant function beside the native-length control. If identity
          survives scale, the scale-invariant distance stays small off 1× while the control grows. Nothing here is a
          test of significance.
        </InfoTip>
        <span className="k-spacer" />
        <Button size="sm" icon="target" iconRight="arrow-right" onClick={() => navigate(`discovery/seed?entry=${readout.entryId}`)} testid="readout-seed-search">Seed search in Discovery</Button>
      </div>
      <div className="lib-cap" style={{ marginTop: 4, color: sharkfin ? 'var(--amber-700, #b76a00)' : undefined }} data-testid="scale-readout-caveat">
        <Icon name="alert-triangle" size={11} style={{ verticalAlign: -1 }} /> exemplar morphology: <b>{readout.morphology}</b> · {readout.caveat}
      </div>
      {!readout.runs.length
        ? <EmptyState size="sm" icon="target" title="No seed search has been run for this exemplar" caption="run one with the scale bank, judge its matches, then Add N matches to this entry in Discovery › Runs" testid="scale-readout-empty" />
        : (
          <div style={{ marginTop: 8 }}>
            {readout.runs.length > 1 && (
              <div className="row" style={{ gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
                {readout.runs.map((r, i) => <Button key={r.runKey} size="sm" variant={i === pick ? 'subtle' : 'default'} onClick={() => setPick(i)} testid={`readout-run-${r.runKey}`}>{r.label}</Button>)}
              </div>
            )}
            {run && <>
              <div className="lib-cap" style={{ marginBottom: 4 }}>{run.label} · bank {run.bank.map(s => `${s}×`).join(' ')} · cut {run.cut == null ? 'none chosen' : `d ≤ ${run.cut}`}</div>
              <ReadoutTable run={run} />
              <div className="lib-cap" style={{ marginTop: 4 }}>{run.note}</div>
            </>}
          </div>
        )}
    </section>
  )
}

/** A member's edges as the bridge served them on the Family read (the page's own `Member` mapping drops the field). */
export const memberEdges = (detail: unknown, id: string): LibEdge[] =>
  ((detail as { members?: { id: string; edges?: LibEdge[] }[] }).members ?? []).find(x => x.id === id)?.edges ?? []
