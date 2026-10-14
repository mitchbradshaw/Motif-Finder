/* fixup-v: Discovery › Runs › *Add N matches to E-xxxx*. A seed run's matches become members of the Library entry
 * it searched for — only those a person accepted (`interesting` / `seed`, Q39), with *include unjudged* a flag that
 * is off — and each pair gets an edge per distance function (scale-invariant, symbolic, native-length). A rejected
 * match keeps its distance on its own detection row and nothing else. The act is explicit and idempotent: a second
 * press writes nothing and says so. */
import { useState } from 'react'
import { Button, Checkbox, InfoTip } from '../kit'
import { useToast } from '../shell/Toast'
import { navigate } from '../state'
import { live, useSourced } from '../api/seam'
import { getLibraryRunMatches, postLibraryRunMatches, type LibEdgeRefusal } from '../api'
import type { DiscoveryRun } from '../api/discovery'

/** W3-D / W3-F: the pairs a distance could not compare (MPdist refuses a member shorter than its sub-window, or one
 *  holding NaN or a flat stretch), as a NEUTRAL line under the button — a measurement that could not be taken, not
 *  an error and not a verdict. One row per refused pair; an entry with no detection is the exemplar refusing every
 *  pair, shown once with its pair count. */
function MatchRefusals({ summary, rows }: { summary: string; rows: LibEdgeRefusal[] }) {
  const exemplar = rows.find(r => r.detection_id == null)
  const pairs = rows.filter(r => r.detection_id != null)
  return (
    <details className="mono small" style={{ color: 'var(--text-2)' }} data-testid="matches-refused">
      <summary style={{ cursor: 'pointer' }}>{summary}</summary>
      {exemplar && <div data-testid="matches-refused-exemplar">the exemplar · {exemplar.function} · {exemplar.reason}{exemplar.pairs != null ? ` · ${exemplar.pairs} pairs` : ''}</div>}
      {pairs.map((r, i) => <div key={i} data-testid="matches-refused-row">m-{r.member_id} · detection {r.detection_id} · {r.function} · {r.reason}</div>)}
    </details>
  )
}

export function AddMatchesButton({ run }: { run: DiscoveryRun }) {
  const [includeUnjudged, setIncludeUnjudged] = useState(false)
  const [busy, setBusy] = useState(false)
  const [refused, setRefused] = useState<{ summary: string; rows: LibEdgeRefusal[] } | null>(null)
  const toast = useToast()
  const summary = useSourced(() => live(getLibraryRunMatches(run.key, includeUnjudged)), [run.key, run.status, run.found, includeUnjudged])
  if (run.kind !== 'seed') return null
  const s = summary.data
  const entry = s?.entryLabel ?? (run.entryId ? `E-${String(run.entryId).padStart(4, '0')}` : 'the entry')
  const n = s?.eligible ?? 0
  const reason = summary.error ? `could not read the run's matches: ${summary.error.message}`
    : !s ? 'reading the run\'s matches' : s.reason ?? (n === 0 ? 'nothing to add' : null)
  const add = () => {
    if (!s || reason) return
    setBusy(true)
    postLibraryRunMatches(run.key, includeUnjudged)
      .then(r => {
        summary.reload()
        setRefused(r.refusalSummary ? { summary: r.refusalSummary, rows: r.edgesRefused ?? [] } : null)
        const fam = r.summary.family
        toast.push({
          text: `${r.membersNew + r.membersResolved} matches added to ${r.entryLabel} · ${r.membersNew} new member${r.membersNew === 1 ? '' : 's'}`
            + `${r.membersResolved ? ` · ${r.membersResolved} re-found` : ''} · ${r.edgesNew} edges (one per distance function)`,
          action: fam ? { label: 'Open in Library', onClick: () => navigate(`library/family/${encodeURIComponent(fam)}`) } : undefined,
        })
      })
      .catch(e => toast.push({ text: `could not add the matches: ${e.message}` }))
      .finally(() => setBusy(false))
  }
  return (
    <span className="row" style={{ gap: 6, alignItems: 'center' }} data-testid="add-matches">
      <Button icon="plus" onClick={add} disabled={!!reason || busy} disabledReason={busy ? 'adding' : reason ?? undefined} testid="add-matches-btn">
        Add {n} match{n === 1 ? '' : 'es'} to {entry}
      </Button>
      <InfoTip title="Add matches to the Library">
        {s ? `${s.accepted} accepted (${s.acceptingVerdicts.join(' · ')}) · ${s.rejected} rejected · ${s.unjudged} unjudged`
          + `${s.already ? ` · ${s.already} already in the Library` : ''}. `
          : ''}
        A match becomes a member of {entry} only with an accepting verdict; each pair gets an edge per distance function
        (scale-invariant, symbolic, native-length), so the three numbers sit side by side on the same pair. A rejected
        match keeps its distance on its detection row.
      </InfoTip>
      <Checkbox label="include unjudged" checked={includeUnjudged} onChange={setIncludeUnjudged} testid="add-matches-unjudged" />
      {refused && <MatchRefusals summary={refused.summary} rows={refused.rows} />}
    </span>
  )
}
