/* tq-grouping (2026-10-25): the grouping editor's tree panel and the read behind it, split out of GroupingPage.tsx.
 * The editor owns the read (`useGroupingTree`) so it can decide the automatic build itself; the panel only draws.
 *
 * fixup-an: the current grouping's kept Ward tree, drawn with Analyse's dendrogram (one component, not a second). The
 * amber line IS the draft's cut: dragging it writes the cut field (and the address), typing the field moves the line.
 * Every move asks the bridge for the families at that cut from the kept tree (`GET /groupings/{id}/cut`) — no job,
 * nothing refitted, nothing written — and draws a card per family (its medoid and a few members). *Compute and apply*
 * is the regroup at that cut, which reuses the tree when the catalogue and the fit settings have not changed. */
import { useEffect, useRef, useState } from 'react'
import { Button, Callout, Icon, InfoTip, fmtInt } from '../kit'
import { getLibraryGroupingCut, getLibraryGroupingTree, type LibCutPreview, type LibGroupingTree } from '../api'
import { Dendrogram, Spark, heightFor, kAt } from '../analyse/views/TreePage'
import { OMIT_REASON_LABEL } from './chrome'
import { errText } from './useGroupingJob'

const MAX_TREE_CARDS = 40

export interface TreeRead { tree: LibGroupingTree | null; error: string | null }
/** The kept tree of grouping `gid` (or, ux-1018, the one a regroup job just built under `builtKey`, before Apply saves
 *  it). Null while it is read; the answer is tagged with what was asked, so a stale answer never stands for a new gid. */
export function useGroupingTree(gid: string | null, builtKey: string | null): TreeRead {
  const ask = `${gid}|${builtKey}`
  const [read, setRead] = useState<TreeRead & { ask: string }>({ ask: '', tree: null, error: null })
  useEffect(() => {
    if (!gid) return
    let alive = true
    getLibraryGroupingTree(gid, builtKey).then(t => { if (alive) setRead({ ask, tree: t, error: null }) })
      .catch(e => { if (alive) { console.error('the grouping tree did not load', e); setRead({ ask, tree: null, error: errText(e) }) } })
    return () => { alive = false }
  }, [gid, builtKey]) // eslint-disable-line react-hooks/exhaustive-deps
  return read.ask === ask ? read : { tree: null, error: null }
}

export function TreePanel({ gid, read, cut, minGroup, omitSmall, nearest, onCut, onBuild, busy, building, builtKey }: {
  gid: string; read: TreeRead; cut: number; minGroup: number; omitSmall: boolean; nearest: number
  onCut: (c: number) => void; onBuild: () => void; busy: boolean
  /** night-review: the editor is building this missing tree on its own (once per editor, motif shape trees only) —
   *  the panel says so instead of offering the button */
  building: boolean
  /** ux-1018: the tree the regroup job just built for this grouping's settings — drawn and cut by its key until
   *  Apply saves it. Build the tree used to run the job and change nothing here, because the panel read only the
   *  row, which records no tree until a save (the researcher, 2026-10-18: "build the tree not working"). */
  builtKey: string | null
}) {
  const { tree, error: treeErr } = read
  const has = !!tree?.tree
  const [pv, setPv] = useState<LibCutPreview | null>(null)
  const [pvErr, setPvErr] = useState<string | null>(null)
  /* fix round: at most one cut request in flight. A move while one is out waits as `pending` (a newer move replaces
   * it), and is sent when the one in flight lands — so a drag costs the server two or three cuts, not one per pixel */
  const mounted = useRef(true)
  useEffect(() => () => { mounted.current = false }, [])
  const inFlight = useRef(false)
  const pending = useRef<(() => void) | null>(null)
  useEffect(() => {
    if (!has || !(cut > 0)) return
    const go = () => {
      inFlight.current = true
      getLibraryGroupingCut(gid, cut, { min_group: omitSmall ? minGroup : 1, omit_d: nearest, samples: 5, ...(builtKey ? { key: builtKey } : {}) })
        .then(p => { if (mounted.current) { setPv(p); setPvErr(null) } })
        .catch(e => { console.error('the cut preview failed', e); if (mounted.current) setPvErr(errText(e)) })
        .finally(() => { inFlight.current = false; const next = pending.current; pending.current = null; if (next) next() })
    }
    const h = window.setTimeout(() => { if (inFlight.current) pending.current = go; else go() }, 180)
    return () => window.clearTimeout(h)
  }, [gid, has, cut, minGroup, omitSmall, nearest, builtKey])

  const head = (
    <h4 className="row" style={{ gap: 6 }}>0&nbsp; The tree behind {gid}
      <InfoTip title="what the tree is">The two most alike shapes join first, then the next pair, until everything is one trunk; the height of a join is how different the two sides were. Cutting the tree at a height gives the families: a lower cut gives more, smaller families, a higher cut fewer, bigger ones. The tree was kept when {gid} was computed; dragging the line reads it again and re-runs nothing. Compute and apply then groups the catalogue at this cut (reusing the kept tree when the catalogue and settings have not changed) and saves it as a new grouping — {gid} stays saved, and hand edits are re-applied as on every regroup.</InfoTip>
    </h4>
  )
  if (treeErr) return <section className="lib-ge-sec" data-testid="ge-tree">{head}<Callout tone="red" title="The tree did not load" testid="tree-load-failed">{treeErr}</Callout></section>
  if (!tree) return <section className="lib-ge-sec" data-testid="ge-tree">{head}<span className="mono small muted" data-testid="tree-loading">reading the tree…</span></section>
  if (!tree.tree && building) {
    return (
      <section className="lib-ge-sec" data-testid="ge-tree">{head}
        <span className="mono small" data-testid="tree-building"><Icon name="clock" size={11} style={{ verticalAlign: -1 }} /> building the tree at {gid}'s settings. The regroup saves nothing; the tree is drawn here when it lands, and Apply saves it with a new grouping.</span>
      </section>
    )
  }
  if (!tree.tree) {
    return (
      <section className="lib-ge-sec" data-testid="ge-tree">{head}
        <Callout tone="amber" title="No tree to draw" testid="tree-missing" action={tree.canBuild
          ? <Button variant="primary" size="sm" icon="play" testid="tree-build" disabled={busy} disabledReason="a regroup is running" onClick={onBuild}>Build the tree</Button> : undefined}>
          {tree.reason}{tree.canBuild ? ' — it computes the grouping again at the settings below and keeps its tree; Apply saves it as a new grouping.' : ''}
        </Callout>
      </section>
    )
  }
  const d = tree.tree.dendrogram
  const k = kAt(d.heights, cut)
  return (
    <section className="lib-ge-sec" data-testid="ge-tree" data-key={tree.tree.key} data-saved={tree.saved === false ? '0' : '1'}>
      {head}
      {tree.saved === false && (
        <span className="mono small" style={{ color: 'var(--blue-600)' }} data-testid="tree-unsaved">
          <Icon name="info" size={11} style={{ verticalAlign: -1 }} /> built by the regroup just run and kept on disk — not saved to {gid}. Apply saves it with the new grouping; {gid} stays as it is.
        </span>
      )}
      <span className="lib-cap row" style={{ gap: 4 }}>drag the amber line to cut <InfoTip title="Cutting the tree">Drag the amber line to cut the tree somewhere else; the families below follow at once, read from the kept tree.</InfoTip></span>
      <Dendrogram t={{ dendrogram: d }} k={k} cutHeight={cut} leafWord="members" heightScale="sqrt"
        cutLabel={`cut ${fmtCut(cut)} · ${k} branch${k === 1 ? '' : 'es'} before the size and distance rules · drag`}
        onK={kk => onCut(+heightFor(d.heights, d.max_height, kk).toFixed(4))} />
      {pvErr && <Callout tone="red" title={`The families at cut ${cut} did not load`} testid="tree-cut-failed">{pvErr}</Callout>}
      {pv && (
        <div className="stack" style={{ gap: 6, opacity: pv.cut === cut ? 1 : 0.6 }} data-testid="tree-cut-preview" data-families={pv.nFamilies} data-cut={pv.cut}>
          <span className="mono small">
            cut {fmtCut(pv.cut)} · <b data-testid="tree-cut-families">{fmtInt(pv.nFamilies)}</b> famil{pv.nFamilies === 1 ? 'y' : 'ies'} · {fmtInt(pv.nAssigned)} members · <span style={{ color: '#c27400' }}>{fmtInt(pv.nOmitted)} omitted</span>
            {pv.smallFamilies.count > 0 && <> · {fmtInt(pv.smallFamilies.count)} group{pv.smallFamilies.count === 1 ? '' : 's'} under {pv.smallFamilies.minGroup} dissolved ({fmtInt(pv.smallFamilies.members)} members)</>}
            {' · '}<span data-testid="tree-cut-moved">{pv.change.sameFamilies ? `the same families as ${gid}` : `${fmtInt(pv.change.moved)} move family against ${gid} (${pv.change.currentFamilies} families) · ${fmtInt(pv.change.newlyOmitted)} newly omitted · ${fmtInt(pv.change.newlyAssigned)} newly in a family`}</span>
            <InfoTip title="how moves are counted">{pv.change.rule}</InfoTip>
          </span>
          {Object.keys(pv.omittedByReason).length > 0 && <span className="mono small" style={{ color: '#c27400' }}>{Object.entries(pv.omittedByReason).map(([r, n]) => `${fmtInt(n)} ${OMIT_REASON_LABEL[r] ?? r}`).join(' · ')}</span>}
          <span className="lib-cap">a card per family: its medoid (brown, the most typical member) and a few more <InfoTip title="which members">{pv.sampleRule}</InfoTip>{pv.families.length > MAX_TREE_CARDS ? ` · the ${MAX_TREE_CARDS} largest of ${pv.families.length} shown` : ''}</span>
          <div className="sh-cards" data-testid="tree-cut-cards" data-n={Math.min(pv.families.length, MAX_TREE_CARDS)}>
            {[...pv.families].sort((a, b) => b.size - a.size).slice(0, MAX_TREE_CARDS).map(f => (
              <div key={f.label} className="sh-card-one" style={{ cursor: 'default' }} data-testid={`tree-cut-card-${f.label}`}>
                <div className="cap"><b>{f.label}</b> · {fmtInt(f.size)} members</div>
                {f.samples[0]?.trace.length ? <Spark v={f.samples[0].trace} w={150} h={46} colour="#b35900" /> : <div className="lib-cap">medoid: {f.samples[0]?.missing ?? 'no trace (its recording declares no unit, or its channel is not on disk)'}</div>}
                <div className="mini-row">{f.samples.slice(1).map(s => s.trace.length ? <Spark key={s.ref} v={s.trace} w={34} h={22} colour="var(--text)" /> : <span key={s.ref} className="lib-cap" title={s.missing ?? 'no trace'}>·</span>)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      {!pv && !pvErr && <span className="mono small muted" data-testid="tree-cut-loading">reading the families at cut {fmtCut(cut)}…</span>}
    </section>
  )
}
const fmtCut = (c: number) => (Math.abs(c) >= 10 ? c.toFixed(1) : c.toFixed(3).replace(/0+$/, '').replace(/\.$/, ''))
