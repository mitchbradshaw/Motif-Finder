/* library.sequences — strips (prompt `sequences`, 2026-10-18).
 *
 * A sequence drawn as a strip: each element a block the colour of its motif family (the colours the motif atlas
 * uses — the bridge sends them), placed at its own start and end in seconds, so the gaps between blocks are drawn
 * to scale. Every strip in one list shares ONE time axis (0 … the longest sequence), so a long silence looks long
 * next to a short one. Nothing is computed here: the times, labels, gaps and colours are the bridge's.
 *
 * `SequenceTrace` is the example plot on the family page: the sequence's own decimated mV trace with its elements
 * as coloured bands behind it, on a domain measured from the trace (the app's one plot-domain rule). */
import { scaleLinear } from 'd3'
import { useMemo } from 'react'
import { useSize } from '../charts/useSize'
import { measuredDomain } from '../charts/domain'
import type { LibSeqElement, LibSeqStrip } from '../api'

const STRIP_H = 14

/** `12.3 s`, `4.1 min`, `2.0 h` — a duration as a person reads it. */
export const fmtDur = (s: number) => (!Number.isFinite(s) ? '—' : Math.abs(s) < 120 ? `${s.toFixed(s < 10 ? 1 : 0)} s` : Math.abs(s) < 7200 ? `${(s / 60).toFixed(1)} min` : `${(s / 3600).toFixed(1)} h`)

export function SequenceStrips({ strips, testid = 'sequence-strips', onOpen, maxRows = 60, showChannel = true }: {
  strips: LibSeqStrip[]; testid?: string; onOpen?: (s: LibSeqStrip) => void; maxRows?: number; showChannel?: boolean
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  const shown = strips.slice(0, maxRows)
  const longest = useMemo(() => Math.max(1e-6, ...shown.map(s => s.durationS)), [shown])
  const labelW = showChannel ? 190 : 120
  const w = Math.max(0, size.width - labelW - 70)
  const x = scaleLinear().domain([0, longest]).range([0, w])
  return (
    <div ref={ref} className="stack" style={{ gap: 4, minWidth: 0 }} data-testid={testid} data-strips={shown.length}>
      {shown.map((s, i) => (
        <div key={`${s.key}-${s.startS}-${i}`} className="row" style={{ gap: 8, alignItems: 'center', cursor: onOpen ? 'pointer' : undefined }}
          data-testid={`${testid}-row`} onClick={onOpen ? () => onOpen(s) : undefined}
          title={`${s.name} · ${s.elements.length} elements · gaps ${s.gapsS.map(g => fmtDur(g)).join(', ')} · ${fmtDur(s.durationS)} long`}>
          <span className="lib-cap" style={{ width: labelW, flex: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {showChannel ? `${s.recording} · ${s.channel} · ${s.startH.toFixed(2)} h` : `${s.startH.toFixed(2)} h · ${s.recording}`}
          </span>
          <svg width={w} height={STRIP_H} style={{ flex: 'none', overflow: 'visible' }} role="img" aria-label={`sequence ${s.name}`} data-testid={`${testid}-svg`}>
            <line x1={0} x2={x(s.durationS)} y1={STRIP_H / 2} y2={STRIP_H / 2} stroke="var(--line)" strokeWidth={1} />
            {s.elements.map((e, k) => (
              <rect key={k} x={x(e.startS)} y={1} width={Math.max(1.5, x(e.endS) - x(e.startS))} height={STRIP_H - 2} rx={2}
                fill={e.colour} data-testid={`${testid}-element`}>
                <title>{`${e.label} · ${fmtDur(e.startS)} → ${fmtDur(e.endS)}${e.verdict ? ` · ${e.verdict}` : ''}`}</title>
              </rect>
            ))}
          </svg>
          <span className="lib-cap" style={{ flex: 'none', width: 60 }}>{fmtDur(s.durationS)}</span>
        </div>
      ))}
      {strips.length > shown.length && <span className="lib-cap">… and {strips.length - shown.length} more not drawn</span>}
    </div>
  )
}

/** The colour key under a strip list: each label in the colour its family has in the motif atlas. */
export function LabelKey({ colours, labels }: { colours: Record<string, string>; labels: string[] }) {
  const uniq = [...new Set(labels)].sort()
  return (
    <div className="row" style={{ gap: 10, flexWrap: 'wrap' }} data-testid="sequence-label-key">
      {uniq.map(l => (
        <span key={l} className="row lib-cap" style={{ gap: 4, alignItems: 'center' }}>
          <i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: colours[l] ?? '#9AA0A6' }} />{l}
        </span>
      ))}
    </div>
  )
}

/** One example sequence: its trace, centred on its median, with its elements as coloured bands. */
export function SequenceTrace({ trace, durationS, bands, height = 90, testid }: { trace: number[]; durationS: number; bands: LibSeqElement[]; height?: number; testid?: string }) {
  const [ref, size] = useSize<HTMLDivElement>()
  const w = Math.max(0, size.width)
  const med = useMemo(() => { const s = [...trace].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : 0 }, [trace])
  const centred = useMemo(() => trace.map(v => v - med), [trace, med])
  const dom = measuredDomain(centred) ?? [-1, 1]
  const x = scaleLinear().domain([0, Math.max(1e-6, durationS)]).range([0, w])
  const y = scaleLinear().domain(dom).range([height - 2, 2])
  const n = centred.length
  const d = n > 1 ? centred.map((v, i) => `${i ? 'L' : 'M'}${x((i / (n - 1)) * durationS).toFixed(1)},${y(v).toFixed(1)}`).join('') : ''
  return (
    <div ref={ref} style={{ width: '100%', position: 'relative' }} data-testid={testid}>
      <svg width={w} height={height} role="img" aria-label="example sequence trace with its elements" data-plot-box>
        <rect x={0} y={0} width={w} height={height} fill="var(--surface-2, #f5f6f8)" />
        {bands.map((b, k) => (
          <rect key={k} x={x(b.startS)} y={0} width={Math.max(1, x(b.endS) - x(b.startS))} height={height} fill={b.colour} opacity={0.22}>
            <title>{b.label}</title>
          </rect>
        ))}
        {d && <path d={d} fill="none" stroke="#1f2937" strokeWidth={1.2} data-trace />}
      </svg>
      {!n && <span className="lib-cap" style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>no waveform on disk, or the unit is undeclared</span>}
      <div className="row lib-cap" style={{ justifyContent: 'space-between' }}><span>0 s</span><span>{dom[0].toFixed(2)} … {dom[1].toFixed(2)} mV, centred</span><span>{fmtDur(durationS)}</span></div>
    </div>
  )
}
