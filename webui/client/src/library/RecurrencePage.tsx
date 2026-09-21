/* library.recurrence — frame library-1: families × channels grouped by recording (3 per page), members per hour
 * (or count), reviewed-coverage bars, `?` = never looked, red = cross-channel artifact kept visible; a selection
 * outlined through the matrix, totalled in the rail with the shared-ground warning, then Browse → atlas.
 *
 * Live notes (stage-3 wiring):
 *  - There is no grouping gate any more. The matrix is drawn for whichever grouping the section resolved to —
 *    `g-07`/`g-08` were fixture names and gating on them meant a live grouping never drew anything.
 *  - The fs1/fs2 mutual exclusion (B30) is read off `RecGroup.resampleOf`, and the held-out card off
 *    `RecGroup.heldOut` + `label`, instead of naming M2_aug/M4_aug.
 *  - Paging is computed from the number of recordings the payload carries, not two fixed pages of three.
 *  - §8.4 survives: `Cell.noCoverage` (the bridge sets it from `reviewed_spans`) draws `?`, a reviewed cell with
 *    no members draws empty, and an artifact cell stays visible in red — the artifact filter flags, never excludes.
 */
import { Fragment, useMemo } from 'react'
import { Button, Callout, Checkbox, EmptyState, Icon, InfoTip, KeyValue, MiniTrace, Page, Seg, fmtInt, recordDemoWrite, useQueryState } from '../kit'
import { Header } from '../shell/Header'
import { navigate } from '../state'
import { useSourced } from '../api/seam'
import { UNIT_LABEL, getOmitted, getRecurrence, getSequenceFamilies, niceMvDomain, type Cell, type RecGroup, type SequenceFamily, type Unit } from '../api/library'
import {
  GroupingBar, LoadFailed, Loading, MotifsActions, OmittedDrawer, OmittedThumb, SectionBar, useAllGroupings, useEmptyLibrary, useMotifGroupingId, useQueueToast,
  useRememberMotifsRoute, useSelection, useSequenceGroupingId,
} from './chrome'
import { EmptyMotifsPage } from './EmptyLibrary'

const RAMP = ['#e6f0ff', '#c2dcff', '#94c2ff', '#539fff', '#0a84ff']
const RECORDINGS_PER_PAGE = 3
const rampIndex = (v: number, max: number) => Math.min(4, Math.max(0, Math.floor((v / (max || 1)) * 5 - 1e-9)))
interface Row { id: string; name: string; colour: string; recordings: number; cells: Record<string, Cell>; cellsKnown: boolean; trace: number[] }

/** A sequence family's own per-channel cells, if the payload carries them. The bridge's `/sequence-families`
 *  does not build a cell map today, so this is `null` and the matrix says so rather than borrowing a motif
 *  family's cells by index — which is what it used to do, and which drew one family's counts under another
 *  family's name. */
const sequenceCells = (s: SequenceFamily): Record<string, Cell> | null =>
  (s as unknown as { cells?: Record<string, Cell> }).cells ?? null

export function RecurrencePage() {
  useRememberMotifsRoute()
  const [empty] = useEmptyLibrary()
  const groupings = useAllGroupings()
  const [gidMotifs] = useMotifGroupingId()
  const [gidSeq] = useSequenceGroupingId()
  const [unitQ, setUnitQ] = useQueryState<string>('unit', 'motifs')
  const unit: Unit = unitQ === 'sequences' ? 'sequences' : 'motifs'
  const gid = unit === 'sequences' ? gidSeq : gidMotifs
  const data = useSourced(() => getRecurrence(gidMotifs || undefined), [gidMotifs])
  const seqs = useSourced(() => getSequenceFamilies(gidSeq || undefined), [gidSeq])
  const grouping = groupings.all.find(g => g.id === gid) ?? null
  const noneOfUnit = !groupings.loading && !groupings.error && !groupings.all.some(g => g.unit === unit)
  const rows: Row[] = useMemo(() => unit === 'sequences'
    ? (seqs.data ?? []).map(s => {
      const cells = sequenceCells(s)
      return { id: s.id, name: s.name, colour: s.colour, recordings: s.recordings, cells: cells ?? {}, cellsKnown: !!cells, trace: s.exemplarTrace }
    })
    : (data.data?.families ?? []).map(f => ({ id: f.id, name: f.name, colour: f.colour, recordings: f.recordings, cells: f.cells, cellsKnown: true, trace: f.exemplarTrace })),
  [unit, seqs.data, data.data])
  if (empty) return <EmptyMotifsPage />
  const loading = data.loading || seqs.loading || groupings.loading
  const error = data.error ?? seqs.error ?? groupings.error
  return (
    <>
      <Header workspace="Library" page="Motifs" subtitle={`recurrence${gid ? ` · grouping ${gid}` : ''}${unit === 'sequences' ? ' · sequences' : ''}`} search="Search spans, runs, families" demo={data.source === 'demo'} />
      <Page testid="recurrence-page">
        <SectionBar section="motifs" crumbs={[{ label: 'Recurrence' }]} actions={<MotifsActions />} />
        <GroupingBar unit={unit} grouping={grouping} from="recurrence" onUnit={u => setUnitQ(u === 'motifs' ? null : u)} />
        {error && <LoadFailed what="the recurrence matrix" error={error} onRetry={() => { data.reload(); seqs.reload(); groupings.reload() }} />}
        {loading && !error && <Loading height={640} testid="recurrence-loading" />}
        {!loading && !error && !grouping && (
          <div className="k-card" style={{ padding: 20 }} data-testid="recurrence-no-grouping">
            <EmptyState icon="grid" title={noneOfUnit ? `No grouping of ${UNIT_LABEL[unit]} yet` : `Grouping ${gid} is not among the saved groupings`}
              caption={noneOfUnit ? 'nothing has been grouped at this unit — compute one from Edit grouping' : 'pick one from the grouping bar, or compute a new one'} />
          </div>
        )}
        {!loading && !error && data.data && grouping && (
          <Recurrence recordings={data.data.recordings} rows={rows} coverage={data.data.coverage} sharedGround={data.data.sharedGround}
            unit={unit} groupingId={grouping.id} omittedCount={grouping.omitted} />
        )}
      </Page>
      {grouping && <OmittedDrawer groupingId={grouping.id} unit={unit} />}
    </>
  )
}

function Recurrence({ recordings, rows, coverage, sharedGround, unit, groupingId, omittedCount }: {
  recordings: RecGroup[]; rows: Row[]; coverage: Record<string, number>; sharedGround: { pair: [string, string]; family: string }[]
  unit: Unit; groupingId: string; omittedCount: number
}) {
  const [sel, setSel] = useSelection()
  const [cell, setCell] = useQueryState<'hour' | 'count'>('cell', 'hour')
  const [recQ, setRecQ] = useQueryState('rec', '1')
  const [, setDrawer] = useQueryState('drawer', '')
  const queue = useQueueToast()
  const omitted = useSourced(() => getOmitted(groupingId), [groupingId])
  const pageCount = Math.max(1, Math.ceil(recordings.length / RECORDINGS_PER_PAGE))
  const page = Math.min(pageCount, Math.max(1, Number(recQ) || 1))
  const groups = recordings.slice((page - 1) * RECORDINGS_PER_PAGE, page * RECORDINGS_PER_PAGE)
  const firstShown = recordings.length ? (page - 1) * RECORDINGS_PER_PAGE + 1 : 0
  const lastShown = Math.min(recordings.length, page * RECORDINGS_PER_PAGE)
  const yDomain = useMemo(() => niceMvDomain(rows.map(r => r.trace)), [rows])
  const keyOf = (r: RecGroup, ch: string) => `${r.key}:${ch}`
  const recLabel = (key: string) => recordings.find(r => r.key === key)?.label ?? key
  const selectedRecKeys = new Set(sel.map(k => k.split(':')[0]))
  /** B30: a scope never mixes a recording and a resample of it. Which rows those are is `RecGroup.resampleOf`,
   *  not a pair of recording names. */
  const disabledReason = (r: RecGroup): string | null => {
    if (r.resampleOf && selectedRecKeys.has(r.resampleOf)) return `${r.label} resamples ${recLabel(r.resampleOf)} — already selectable there (B30: a scope never mixes a recording and its resample)`
    const child = recordings.find(o => o.resampleOf === r.key && selectedRecKeys.has(o.key))
    if (child) return `${child.label} channels are selected — a scope never mixes a recording and its resample (B30)`
    return null
  }
  const setSelection = (next: string[]) => { setSel(next); recordDemoWrite('library', 'selection', { channels: next.length }) }
  const toggle = (k: string) => setSelection(sel.includes(k) ? sel.filter(x => x !== k) : [...sel, k])
  const maxCount = Math.max(1, ...rows.flatMap(row => groups.flatMap(g => g.channels.map(ch => row.cells[keyOf(g, ch)]?.count ?? 0))))
  const pageKeys = groups.filter(g => !g.heldOut && !disabledReason(g)).flatMap(g => g.channels.map(ch => keyOf(g, ch)))
  const cellsUnknown = rows.length > 0 && rows.every(r => !r.cellsKnown)

  // rail totals
  const recs = [...new Set(sel.map(k => k.split(':')[0]))]
  const hoursOf = (key: string) => recordings.find(r => r.key === key)?.hours ?? 0
  const channelHours = sel.reduce((s, k) => s + hoursOf(k.split(':')[0]), 0)
  const members = sel.reduce((s, k) => s + rows.reduce((t, row) => t + (row.cells[k]?.count ?? 0), 0), 0)
  const reviewed = channelHours ? sel.reduce((s, k) => s + hoursOf(k.split(':')[0]) * (coverage[k] ?? 0), 0) / channelHours : 0
  const channelsText = recs.map(r => `${recLabel(r)} ${sel.filter(k => k.startsWith(`${r}:`)).map(k => k.split(':')[1]).join(', ')}`).join(' · ')
  const warnings = sharedGround.filter(w => sel.includes(w.pair[0]) && sel.includes(w.pair[1]))
  const lastRow = rows.length - 1

  return (
    <div className="lib-split">
      <div className="stack" style={{ gap: 12, minWidth: 0 }}>
        <div className="k-card" style={{ padding: '12px 14px' }} data-testid="recurrence-matrix-card">
          <div className="row" style={{ marginBottom: 10 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>Where each family occurs</span>
            <InfoTip title="reading the matrix">Cells are members per hour of recording (toggle to count). A `?` means nobody has reviewed that channel and nothing was found, so “absent” and “never looked” differ. Red cells are cross-channel artifacts; they stay visible (flagged, not excluded). Dark in one recording and empty in the others is a property of that recording, not of the organism.</InfoTip>
            <span style={{ marginLeft: 'auto' }} />
            <Seg size="sm" ariaLabel="cell value" testid="cell-mode" value={cell} onChange={v => setCell(v)} options={[{ value: 'hour', label: 'per hour' }, { value: 'count', label: 'count' }]} />
            <span className="row lib-cap" style={{ gap: 6, fontSize: 11 }}>
              <button type="button" className="lib-pg" style={{ width: 24, height: 24 }} disabled={page <= 1} title={page <= 1 ? 'first page' : 'previous recordings'} aria-label="previous recordings" data-testid="rec-prev" onClick={() => setRecQ(page - 1 <= 1 ? null : String(page - 1))}><Icon name="chevron-left" size={12} /></button>
              <span data-testid="rec-page-label">recordings {firstShown}–{lastShown} of {recordings.length}</span>
              <button type="button" className="lib-pg" style={{ width: 24, height: 24 }} disabled={page >= pageCount} title={page >= pageCount ? 'last page' : 'next recordings'} aria-label="next recordings" data-testid="rec-next" onClick={() => setRecQ(String(page + 1))}><Icon name="chevron-right" size={12} /></button>
            </span>
          </div>
          {cellsUnknown ? (
            <Callout tone="amber" stacked testid="recurrence-no-cells" title={`No per-channel counts for ${unit === 'sequences' ? 'sequence families' : 'these families'}`}>
              This read carries the families and their traces but no `cells` map, so where each one occurs is not
              known here and no matrix is drawn. Nothing is guessed and nothing is borrowed from another family.
            </Callout>
          ) : (
          <div className="lib-matrix" data-testid="recurrence-matrix">
            <table>
              <thead>
                <tr>
                  <th />
                  {groups.map((g, gi) => {
                    const keys = g.channels.map(ch => keyOf(g, ch))
                    const n = keys.filter(k => sel.includes(k)).length
                    const reason = disabledReason(g)
                    return (
                      <Fragment key={g.key}>
                        {gi > 0 && <th className="lib-gapcol" />}
                        <th className="lib-rec-head" colSpan={Math.max(1, g.channels.length)} data-testid={`rec-head-${g.key}`}>
                          {g.heldOut ? <span className="row" style={{ gap: 6 }}><Icon name="lock" size={12} />{g.label}</span> : (
                            <Checkbox label={<span className="mono b">{g.label}</span>} checked={n > 0 && n === keys.length} indeterminate={n > 0 && n < keys.length} testid={`rec-check-${g.key}`}
                              disabled={!!reason} disabledReason={reason ?? undefined}
                              onChange={v => setSelection(v ? [...new Set([...sel, ...keys])] : sel.filter(k => !keys.includes(k)))} />
                          )}
                          <div className="lib-rec-sub">{g.hours} h · {g.heldOut ? 'held out' : `${g.reviewedPct}% reviewed`}{g.hiddenChannels && !g.heldOut ? <span title={`${g.hiddenChannels} more channels have no members and no reviewed coverage in this grouping`}> · +{g.hiddenChannels} ch</span> : ''}{g.fsNote ? <span title={`sampling rate ${g.fsNote}`}> · fs?</span> : ''}</div>
                        </th>
                      </Fragment>
                    )
                  })}
                </tr>
                <tr>
                  <th />
                  {groups.map((g, gi) => (
                    <Fragment key={g.key}>
                      {gi > 0 && <th className="lib-gapcol" />}
                      {g.heldOut ? <th /> : g.channels.map(ch => {
                        const k = keyOf(g, ch), on = sel.includes(k), reason = disabledReason(g)
                        return (
                          <th key={k} className={`lib-ch-head${on ? ' on lib-sel-top' : ''}`} data-testid={`ch-head-${k}`}>
                            <div className="inner">
                              <div className="row" style={{ gap: 3 }}>
                                <Checkbox checked={on} onChange={() => toggle(k)} ariaLabel={`select ${g.label} ${ch}`} testid={`ch-check-${k}`} disabled={!!reason} disabledReason={reason ?? undefined} />
                                <span className="nm" title={ch}>{ch}</span>
                              </div>
                              <span className="lib-cov" title={`${Math.round((coverage[k] ?? 0) * 100)} % of channel-hours reviewed`}><i style={{ width: `${(coverage[k] ?? 0) * 100}%` }} /></span>
                            </div>
                          </th>
                        )
                      })}
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, ri) => (
                  <tr key={row.id}>
                    <td>
                      <button type="button" className="lib-rowlabel" data-testid={`row-label-${row.id}`} title={`open ${row.id} in the atlas`} onClick={() => navigate(`library/atlas?${unit === 'sequences' ? 'unit=sequences&' : ''}family=${row.id}`)}>
                        <MiniTrace values={row.trace} yDomain={yDomain} width={36} height={24} ground="none" zeroLine={false} strokeWidth={1.4} />
                        <span className="stack" style={{ gap: 0 }}>
                          <span className="row" style={{ gap: 6 }}><span className="id" style={{ color: row.colour }}>{row.id}</span><span className="nm" title={row.name}>{row.name}</span></span>
                          <span className="sub">{row.recordings} recording{row.recordings === 1 ? '' : 's'}</span>
                        </span>
                      </button>
                    </td>
                    {groups.map((g, gi) => (
                      <Fragment key={g.key}>
                        {gi > 0 && <td className="lib-gapcol" />}
                        {g.heldOut && ri === 0 && <td rowSpan={rows.length} style={{ verticalAlign: 'top' }}><div className="lib-locked" data-testid="held-out-block"><span className="row" style={{ gap: 6, color: 'var(--text-2)' }}><Icon name="lock" size={13} /><b>{g.label} is held out</b></span><span>locked in Settings › Datasets (D6) · never shown in the Library</span><Button size="sm" variant="link" onClick={() => navigate('settings/datasets')}>Settings › Datasets</Button></div></td>}
                        {!g.heldOut && g.channels.map(ch => {
                          const k = keyOf(g, ch), c = row.cells[k], on = sel.includes(k), reason = disabledReason(g)
                          const empty = !c || (c.perHour == null)
                          const value = cell === 'count' ? c?.count ?? 0 : c?.perHour ?? 0
                          const idx = cell === 'count' ? rampIndex(value, maxCount) : rampIndex(value, 1)
                          const cls = c?.noCoverage ? 'q' : empty ? 'none' : c.artifact ? 'art' : ''
                          const text = c?.noCoverage ? '?' : empty ? '' : `${c.artifact ? '! ' : ''}${cell === 'count' ? fmtInt(c.count) : c.perHour!.toFixed(2)}`
                          const tip = c?.noCoverage ? `no reviewed coverage on ${ch} · no members found` : empty ? `${row.id} · ${g.label} · ${ch} · reviewed, no members` : `${row.id} · ${g.label} · ${ch} · ${c.count} members · ${c.perHour!.toFixed(2)} / h${c.artifact ? ' · cross-channel artifact (flagged)' : ''}`
                          return (
                            <td key={k} className={`lib-cell${on ? (ri === lastRow ? ' on lib-sel-bottom' : ' on lib-sel-lr') : ''}`}>
                              <button type="button" className={cls} title={reason ? `${tip} · ${reason}` : tip} data-testid={`cell-${row.id}-${k}`} disabled={!!reason}
                                style={cls === '' ? { background: RAMP[idx], color: idx >= 3 ? '#fff' : 'var(--text-2)' } : undefined} onClick={() => toggle(k)}>{text}</button>
                            </td>
                          )
                        })}
                      </Fragment>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
          {!rows.length && <EmptyState icon="grid" title="No families in this grouping" caption="nothing was assigned a family, so there is nothing to draw" bordered />}
          <div className="lib-legend" style={{ marginTop: 14 }} data-testid="recurrence-legend">
            <span className="row" style={{ gap: 4 }}>{cell === 'count' ? 'members' : 'members / h'} {RAMP.map(c => <span key={c} className="lib-swatch" style={{ background: c }} />)} 0 → {cell === 'count' ? fmtInt(maxCount) : '1.0'}</span>
            <span className="row" style={{ gap: 5 }}><span className="lib-swatch" style={{ background: '#fff', border: '1px solid var(--border-strong)', textAlign: 'center', fontSize: 9, lineHeight: '11px' }}>?</span>no reviewed coverage</span>
            <span className="row" style={{ gap: 5 }}><span className="lib-swatch" style={{ background: '#fde2e2', border: '1px solid var(--red)' }} />cross-channel artifact, kept visible</span>
            <span className="row" style={{ gap: 5 }}><span className="lib-swatch" style={{ border: '1.5px dashed var(--blue)' }} />selected</span>
          </div>
          <div className="lib-cap" style={{ marginTop: 6 }}><Icon name="info" size={11} style={{ verticalAlign: -1 }} /> dark in one recording and empty in the others → a property of that recording, not of the organism</div>
        </div>

        <div className="k-card" style={{ padding: '12px 14px' }} data-testid="omitted-strip">
          <div className="row" style={{ marginBottom: 10 }}>
            <Icon name="flag" size={14} style={{ color: 'var(--amber)' }} />
            <b style={{ fontSize: 13, whiteSpace: 'nowrap' }}>{unit === 'sequences' ? `${fmtInt(omittedCount)} left out of this round` : `${fmtInt(omittedCount)} motifs fit no family in this grouping`}</b>
            <span className="lib-cap" style={{ fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>{unit === 'sequences' ? 'motifs in no sequence and sequences past the cut · not deleted' : 'past the grouping cut · left out of counts, not deleted'}</span>
            <span style={{ marginLeft: 'auto' }} />
            <Button variant="link" testid="omitted-send-queue" onClick={() => queue(`Library · ${groupingId} omitted`, omittedCount)}>Send to Review as a queue</Button>
            <Button variant="link" testid="omitted-show-all" onClick={() => setDrawer('omitted')}>Show all {fmtInt(omittedCount)}</Button>
          </div>
          {omitted.error && <LoadFailed what="omitted motifs" error={omitted.error} onRetry={omitted.reload} />}
          {omitted.data && <button type="button" className="lib-thumbrow lib-plain" style={{ width: '100%' }} onClick={() => setDrawer('omitted')} title="open the omitted drawer">
            {omitted.data.singles.slice(0, 12).map(e => <OmittedThumb key={e.id} e={e} yDomain={[-0.45, 0.45]} width={66} height={44} />)}
          </button>}
        </div>
      </div>

      <aside className="k-card lib-rail" data-testid="recurrence-rail">
        <div className="row"><Icon name="layers" size={14} /><b style={{ fontSize: 13 }}>This grouping</b><span className="lib-cap" style={{ marginLeft: 'auto' }}>{groupingId}</span></div>
        <RailGrouping groupingId={groupingId} />
        <div className="lib-hr" />
        <div className="row"><Icon name="circle-dashed" size={14} /><b style={{ fontSize: 13 }}>Selection</b></div>
        {sel.length ? (
          <KeyValue align="right" dense testid="selection-kv" items={[
            { k: 'recordings', v: recs.length },
            { k: 'channels', v: <span title={channelsText}>{channelsText}</span> },
            { k: 'channel-hours', v: `${fmtInt(channelHours)} h`, info: <InfoTip title="channel-hours">the sum of recording length over the selected channels</InfoTip> },
            { k: 'members', v: fmtInt(members), strong: true },
            { k: 'reviewed', v: `${Math.round(reviewed * 100)} %` },
          ]} />
        ) : <div className="lib-cap" data-testid="selection-empty" style={{ padding: '6px 0' }}>Tick channels or recordings to build a selection</div>}
        {warnings.map(w => (
          <Callout key={w.pair.join()} tone="amber" stacked testid="shared-ground-warning" title={`${w.pair[0].split(':')[1]} + ${w.pair[1].split(':')[1]} share ground for ${w.family}`}
            action={<Button icon="minus" testid="deselect-shared" onClick={() => setSelection(sel.filter(k => k !== w.pair[1]))}>Deselect {w.pair[1].split(':')[1]}</Button>}>
            Browsing both double-counts that family.
          </Callout>
        ))}
        <div className="lib-rail-actions">
          <Button variant="primary" iconRight="arrow-right" testid="browse-channels" disabled={!sel.length} disabledReason="select at least one channel" onClick={() => navigate(`library/atlas${unit === 'sequences' ? '?unit=sequences' : ''}`)}>Browse {sel.length} channel{sel.length === 1 ? '' : 's'}</Button>
          <span className="row" style={{ gap: 14 }}>
            <Button variant="link" testid="select-all-channels" disabled={!pageKeys.length} disabledReason="no selectable channels on this page" onClick={() => setSelection([...new Set([...sel, ...pageKeys])])}>Select all channels</Button>
            <Button variant="link" testid="clear-selection" disabled={!sel.length} disabledReason="nothing selected" onClick={() => setSelection([])}>Clear</Button>
          </span>
        </div>
      </aside>
    </div>
  )
}

function RailGrouping({ groupingId }: { groupingId: string }) {
  const { all } = useAllGroupings()
  const g = all.find(x => x.id === groupingId)
  if (!g) return null
  const [basis, linkage] = g.basisLabel.split(' · ')
  return (
    <KeyValue align="right" dense testid="grouping-kv" items={[
      { k: 'unit', v: UNIT_LABEL[g.unit] ?? g.unit },
      { k: 'basis', v: linkage ? `${basis} · ${linkage}` : basis },
      { k: g.params.startsWith('cut') ? 'cut' : 'params', v: g.params.replace(/^cut /, '') },
      { k: 'computed', v: `${g.computed} · ${fmtInt(g.motifs)} motifs` },
      { k: 'families', v: g.families, strong: true },
      { k: 'omitted', v: <span className="row" style={{ gap: 6, justifyContent: 'flex-end' }}><span className="k-badge t-amber">flagged</span><span style={{ color: '#c27400' }}>{fmtInt(g.omitted)}</span></span> },
      { k: 'hand edits', v: <span className="row" style={{ gap: 6, justifyContent: 'flex-end' }}><span className="k-badge t-purple">hand</span>{g.handEditsKept} kept</span> },
    ]} />
  )
}
