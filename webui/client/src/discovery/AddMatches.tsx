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
import { getLibraryRunMatches, postLibraryRunMatches } from '../api'
import type { DiscoveryRun } from '../api/discovery'

export function AddMatchesButton({ run }: { run: DiscoveryRun }) {
  const [includeUnjudged, setIncludeUnjudged] = useState(false)
  const [busy, setBusy] = useState(false)
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
    </span>
  )
}
