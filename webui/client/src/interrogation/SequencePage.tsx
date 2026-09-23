/* analyse.interrogation.sequence — fixup-d: the steepest-slope rose compared ACROSS THE EVENTS OF ONE
 * SEQUENCE (QUESTIONS.md Q13, the rose is max slope). Sequences are the `sequences` table, not Library
 * entries (no entry has scale 'train'), so this page keys off them. Every number is the bridge's
 * (`/api/interrogation/sequences/{id}/shape` → Working/interrogation/sequences.py): per-event features
 * from `motif_features` where stored, measured from the Library snippet and flagged where not, and the
 * rose from gradients.rose_data split by the sequence key. The page writes nothing — a comparison is a view. */
import { useEffect, useMemo, useState } from 'react'
import { getSequenceShape, getSequences, type FeatureTable as FeatureTableT, type SequenceRow, type SequenceShape } from '../api'
import { FeatureTable, RoseFan, RulesList } from '../analyse/EventFeatures'
import { Header } from '../shell/Header'
import { navigate, setQuery, useApp } from '../state'

const SCALES = ['raw', 'recording', 'pooled', 'event'] as const
const COLS = ['polarity', 'event_amplitude_mv', 'event_width_s', 'fwhm_s', 'recovery_time_s', 'duration_s', 'max_slope_mv_s',
  'onset_slope_mv_s', 'chord_slope_mv_s', 'peakedness', 'precursor_height_mv']

export function SequencePage() {
  const { route } = useApp()
  const idQ = route.query.id !== undefined ? Number(route.query.id) : NaN
  const scaleQ = (route.query.scale ?? 'raw') as typeof SCALES[number]
  const [list, setList] = useState<SequenceRow[] | null>(null)
  const [listErr, setListErr] = useState<string | null>(null)
  const [shape, setShape] = useState<SequenceShape | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => { getSequences().then(r => setList(r.sequences), e => setListErr(String(e?.message ?? e))) }, [])
  const id = Number.isFinite(idQ) ? idQ : list?.[0]?.id ?? null
  useEffect(() => {
    if (id === null) return
    setShape(null); setErr(null)
    getSequenceShape(id, scaleQ).then(setShape, e => setErr(String(e?.message ?? e)))
  }, [id, scaleQ])

  const table: FeatureTableT | null = useMemo(() => {
    if (!shape) return null
    const cols = ['gap_before_s', ...COLS, 'detector_drop_depth_mv']
    const matrix = shape.events.map(e => cols.map(c => c === 'gap_before_s' ? e.gap_before_s
      : c === 'detector_drop_depth_mv' ? (e.detector?.drop_depth_mv ?? null) : (e.features?.[c] ?? null)))
    return { n_columns: cols.length, columns: cols, matrix }
  }, [shape])

  return (
    <>
      <Header workspace="Analyse" page="Sequence · slope rose" subtitle={shape ? `${shape.sequence.sequence_key} · ${shape.sequence.n_members} events · ${shape.sequence.source_file ?? 'no recording'}` : 'the steepest slope of every event in one sequence'} />
      <div className="page"><div className="page-inner" data-testid="interrogation-sequence" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="an-toolbar">
          <button className="btn ghost" onClick={() => navigate('analyse/interrogation')}>‹ Interrogation</button>
          <label className="muted small" htmlFor="seq-pick">sequence</label>
          <select id="seq-pick" data-testid="sequence-picker" value={id ?? ''} onChange={e => setQuery({ id: e.target.value })} style={{ maxWidth: 420 }}>
            {(list ?? []).map(s => <option key={s.id} value={s.id}>{s.sequence_key} · {s.n_members} events · {s.origin} · {s.source_file ?? '—'}</option>)}
          </select>
          <label className="muted small" htmlFor="seq-scale">45° means</label>
          <select id="seq-scale" data-testid="rose-scale" value={scaleQ} onChange={e => setQuery({ scale: e.target.value })}>
            {SCALES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {listErr && <div className="error-card" data-testid="sequences-failed"><h3>could not list the sequences</h3><div className="mono small">{listErr}</div></div>}
        {list && list.length === 0 && <div className="muted" data-testid="no-sequences">No sequence has member rows in this database yet.</div>}
        {err && <div className="error-card" data-testid="sequence-failed"><h3>could not measure sequence {id}</h3><div className="mono small">{err}</div></div>}
        {!shape && !err && id !== null && <div className="muted mono small" data-testid="sequence-loading">measuring the events of sequence {id}…</div>}
        {shape && (
          <>
            {shape.unit_note && <div className="small" data-testid="sequence-unit-note" style={{ padding: '6px 10px', background: '#fff7e6', borderRadius: 6 }}>{shape.unit_note}</div>}
            <div className="card card-pad" data-testid="sequence-rose-card">
              <div className="bp-card-title"><h3>Each event&apos;s steepest slope, as one angle</h3><span className="sg">{shape.rose.n} of {shape.sequence.n_members} events have a measured fall</span></div>
              <RoseFan rose={shape.rose} />
            </div>
            <div className="card card-pad" data-testid="sequence-events-card">
              <div className="bp-card-title"><h3>The events, in order</h3>
                <span className="sg">{shape.sequence.n_stored} of {shape.sequence.n_members} from motif_features · the rest measured now from the Library snippet and not stored</span></div>
              {table && <FeatureTable table={table} rowLabel={i => `${shape.events[i].position + 1}${shape.events[i].stored ? '' : '*'}`} testid="sequence-feature-table" />}
              <div className="muted small" style={{ marginTop: 4 }}>* measured now, not stored · gap before = seconds from the previous event&apos;s onset, as the sequence records it · detector drop depth = the detector&apos;s own number, carried beside ours</div>
            </div>
            <RulesList rules={shape.rules} />
          </>
        )}
      </div></div>
    </>
  )
}
