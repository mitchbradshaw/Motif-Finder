/* Algorithm glyphs (spec §6.8): a static thumbnail of *the algorithm*. Since critique r1 each
   registered block has its own glyph (BY_NAME); the type-signature glyph (BY_SIG) is only the
   fallback for a block the map does not know — a new adapter file gets a signature glyph until
   it registers its own. Colour key: grey input/context · blue what the block emits · green
   found/kept · amber cut/threshold · red discord/excluded · purple exemplar/second input.
   Drawn in a 44 × 26 box; 44×26 on cards, 272×96 in the detail panel. */
import type { ReactElement } from 'react'
import type { AdapterCard, TypeKind } from '../api'

const G = '#9ca3af', B = '#0a84ff', GR = '#22a06b', AM = '#e8900c', RD = '#e5484d', PU = '#8e5cf7', BL = '#bfdcff', GL = '#e5e7eb'

function wave(y: number, amp: number, stroke: string, w = 1.2, x0 = 2, x1 = 42) {
  const pts: string[] = []
  for (let x = x0; x <= x1; x += 2) pts.push(`${x},${(y + Math.sin(x / 3.1) * amp + Math.sin(x / 1.3) * amp * 0.35).toFixed(1)}`)
  return <polyline points={pts.join(' ')} fill="none" stroke={stroke} strokeWidth={w} strokeLinejoin="round" />
}
function smooth(y: number, amp: number, stroke: string, w = 1.4, x0 = 2, x1 = 42, phase = 0) {
  const pts: string[] = []
  for (let x = x0; x <= x1; x += 2) pts.push(`${x},${(y + Math.sin(x / 3.1 + phase) * amp).toFixed(1)}`)
  return <polyline points={pts.join(' ')} fill="none" stroke={stroke} strokeWidth={w} strokeLinejoin="round" />
}
function blocks(y: number, h: number, colours: string[], x0 = 2, w = 4.6, gap = 0.6) {
  return <g>{colours.map((c, i) => <rect key={i} x={x0 + i * (w + gap)} y={y} width={w} height={h} fill={c} rx={0.6} />)}</g>
}
/** An n×n matrix at (x0,y0) with `cell` px cells, coloured by a (row, col) → colour function. */
function matrix(x0: number, y0: number, n: number, cell: number, colour: (r: number, c: number) => string) {
  const out: ReactElement[] = []
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) out.push(<rect key={`${r}-${c}`} x={x0 + c * cell} y={y0 + r * cell} width={cell - 0.4} height={cell - 0.4} fill={colour(r, c)} />)
  return <g>{out}</g>
}
const blues = ['#e6f1ff', '#bfdcff', '#7fb8ff', '#3d97ff', '#0a84ff', '#0066d6']
const shade = (u: number) => blues[Math.max(0, Math.min(blues.length - 1, Math.round(u * (blues.length - 1))))]
/** A filter response: grey outside the passband, blue inside, amber ticks at the cut-offs. */
function response(kind: 'low' | 'high' | 'band') {
  const y0 = 22, y1 = 6
  const d = kind === 'low' ? `M2 ${y1} H22 C27 ${y1} 28 ${y0} 34 ${y0} H42` : kind === 'high' ? `M2 ${y0} H10 C16 ${y0} 17 ${y1} 22 ${y1} H42` : `M2 ${y0} H8 C13 ${y0} 14 ${y1} 18 ${y1} H26 C30 ${y1} 31 ${y0} 36 ${y0} H42`
  const cuts = kind === 'low' ? [26] : kind === 'high' ? [16] : [14, 30]
  const pass = kind === 'low' ? [2, 24] : kind === 'high' ? [18, 42] : [16, 28]
  return (
    <g>
      <rect x={pass[0]} y={3} width={pass[1] - pass[0]} height={20} fill={BL} opacity={0.6} />
      <path d={d} fill="none" stroke={G} strokeWidth={1.2} />
      <path d={d} fill="none" stroke={B} strokeWidth={1.4} strokeDasharray={kind === 'low' ? '24 100' : kind === 'high' ? '0 20 40' : '0 13 16 100'} />
      {cuts.map(x => <line key={x} x1={x} x2={x} y1={3} y2={23} stroke={AM} strokeWidth={1} strokeDasharray="2 1.5" />)}
    </g>
  )
}
const spikes = (colour: string) => <polyline points="2,18 7,18 9,17 11,18 14,18 15,5 16,18 21,18 23,17 26,18 28,7 29,18 34,18 36,17 39,18 42,18" fill="none" stroke={colour} strokeWidth={1.2} strokeLinejoin="round" />

const BY_NAME: Record<string, () => ReactElement> = {
  /* ---- Signal → Signal (the five filters) ---- */
  'preprocessing.detrend': () => <g><line x1={2} x2={42} y1={20} y2={6} stroke={G} strokeDasharray="2 1.5" strokeWidth={1} />{wave(13, 4, G, 1.1)}<g transform="skewY(-18) translate(0 7)">{smooth(13, 3.5, B)}</g></g>,
  'preprocessing.bandpass': () => response('band'),
  'preprocessing.highpass': () => response('high'),
  'preprocessing.lowpass': () => response('low'),
  'preprocessing.surrogate': () => <g>{smooth(8, 3, G, 1.2)}{smooth(19, 3, B, 1.4, 2, 42, 1.9)}<path d="M20 12l3 2-3 2M24 16l-3-2 3-2" fill="none" stroke={PU} strokeWidth={1.1} /><circle cx={35} cy={13} r={1.2} fill={PU} /><circle cx={38.5} cy={13} r={1.2} fill={PU} /></g>,
  /* ---- Signal → Encoding · symbolic (three SAX variants) ---- */
  'detection.sax_csax': () => <g>{wave(9, 4, G, 1)}{[5, 9, 13].map(y => <line key={y} x1={2} x2={42} y1={y} y2={y} stroke={AM} strokeWidth={0.7} strokeDasharray="1.5 1.5" />)}{blocks(17, 7, [B, '#7fb8ff', BL, B, '#7fb8ff', BL, B, '#7fb8ff'])}</g>,
  'detection.sax_dsax': () => <g>{wave(8, 3, G, 1)}<polyline points="2,11 8,11 8,6 14,6 14,12 20,12 20,9 26,9 26,5 32,5 32,10 38,10 38,8 42,8" fill="none" stroke={B} strokeWidth={1.1} />{blocks(17, 7, [AM, '#c7cbd1', B, AM, B, '#c7cbd1', AM, B])}</g>,
  'detection.sax_psax': () => <g>{wave(8, 3.5, G, 1)}<g>{[3, 6, 9, 12].map((x, i) => <rect key={x} x={x + i * 2} y={14 - i * 2.5} width={2} height={i * 2.5 + 2} fill={G} />)}</g>{blocks(17, 7, [B, PU, GR, AM, B, PU, GR, B])}</g>,
  /* ---- Signal → Encoding · image (four gramian-family fields) ---- */
  'catalogue.gramian_gasf': () => <g>{matrix(3, 3, 5, 4, (r, c) => shade(0.5 + 0.5 * Math.cos((r + c) * 0.9)))}<text x={28} y={11} fill={G} style={{ fontSize: 7 }}>Σ</text><path d="M27 15h14M27 19h14M27 23h14" stroke={G} strokeWidth={0.8} /></g>,
  'catalogue.gramian_gadf': () => <g>{matrix(3, 3, 5, 4, (r, c) => shade(0.5 + 0.5 * Math.sin((c - r) * 0.9)))}<text x={28} y={11} fill={G} style={{ fontSize: 7 }}>Δ</text><path d="M27 15h14M27 19h14M27 23h14" stroke={G} strokeWidth={0.8} /></g>,
  'catalogue.gramian_fusion': () => <g>{matrix(3, 3, 5, 4, (r, c) => c < r ? shade(0.5 + 0.5 * Math.cos((r + c) * 0.9)) : (r + c) % 2 ? PU : '#ddd0ff')}<path d="M3 3l20 20" stroke="#fff" strokeWidth={0.8} /><rect x={27} y={4} width={5} height={5} fill={B} /><rect x={27} y={12} width={5} height={5} fill={PU} /><text x={34} y={9} fill={G} style={{ fontSize: 6 }}>gasf</text><text x={34} y={17} fill={G} style={{ fontSize: 6 }}>gadf</text></g>,
  'catalogue.gramian_recurrence': () => <g>{matrix(3, 3, 5, 4, (r, c) => (r === c || (r + c === 4) || (Math.abs(r - c) === 2 && r % 2 === 0)) ? B : '#eef0f3')}{wave(9, 3, G, 1, 27, 42)}<line x1={27} x2={42} y1={15} y2={15} stroke={G} strokeWidth={0.6} /></g>,
  /* ---- Signal → Encoding · spectral ---- */
  'detection.freq_stft': () => <g>{matrix(2, 3, 5, 4, (r, c) => shade(Math.max(0, Math.min(1, 0.9 - r * 0.2 + (c === 2 ? 0.45 : 0) * (r > 1 ? 1 : 0)))))}{wave(12, 5, G, 1, 25, 42)}<text x={26} y={22} fill={G} style={{ fontSize: 5.5 }}>t → f</text></g>,
  'detection.wavelet_scattering': () => <g><path d="M2 14 C6 14 7 4 10 4 S14 24 17 24 S21 4 24 4 S28 14 32 14" fill="none" stroke={G} strokeWidth={1.1} />{blocks(4, 18, ['#7fb8ff', B, '#0066d6', '#7fb8ff'], 33, 2, 0.4)}</g>,
  /* ---- Signal → Scores / Scores → SpanSet ---- */
  'detection.matrix_profile': () => <g>{wave(6, 2.5, G, 1)}<polyline points="2,19 6,18 10,19 13,12 16,19 20,18 24,19 27,12 30,19 33,17 36,9 39,18 42,19" fill="none" stroke={B} strokeWidth={1.3} /><circle cx={13} cy={12} r={1.6} fill={GR} /><circle cx={27} cy={12} r={1.6} fill={GR} /><circle cx={36} cy={9} r={1.6} fill={RD} /></g>,
  'detection.threshold': () => <g><polyline points="2,19 6,18 10,17 13,8 16,18 20,19 24,17 27,7 30,18 34,19 38,18 42,19" fill="none" stroke={G} strokeWidth={1.2} /><line x1={2} x2={42} y1={12} y2={12} stroke={AM} strokeWidth={1} strokeDasharray="2 1.5" /><rect x={11} y={3} width={5} height={6} fill={B} rx={0.6} /><rect x={25} y={3} width={5} height={6} fill={B} rx={0.6} /></g>,
  /* ---- Signal → SpanSet (three detectors) ---- */
  'detection.spike_v1': () => <g>{spikes(G)}<circle cx={15} cy={5} r={1.7} fill={GR} /><circle cx={28} cy={7} r={1.7} fill={GR} /><rect x={13} y={2} width={4} height={22} fill={B} opacity={0.25} /><rect x={26} y={2} width={4} height={22} fill={B} opacity={0.25} /></g>,
  'detection.dehshibi_spikes': () => <g>{spikes(G)}<line x1={2} x2={42} y1={11} y2={11} stroke={AM} strokeWidth={0.9} strokeDasharray="2 1.5" /><rect x={12} y={2} width={6} height={22} fill={B} opacity={0.3} /><rect x={25} y={2} width={6} height={22} fill={B} opacity={0.3} /><path d="M15 5l-1.5 3M15 5l1.5 3" stroke={GR} strokeWidth={1} /></g>,
  'detection.rupture': () => <g><polyline points="2,8 8,7 13,9 16,8 16,17 21,16 27,18 30,17 30,11 35,10 40,12 42,11" fill="none" stroke={G} strokeWidth={1.2} /><line x1={16} x2={16} y1={2} y2={24} stroke={B} strokeWidth={1.2} /><line x1={30} x2={30} y1={2} y2={24} stroke={B} strokeWidth={1.2} /><rect x={16} y={2} width={14} height={22} fill={B} opacity={0.12} /></g>,
  /* ---- WindowSet → Grouping → Model ---- */
  'preprocessing.window_matrix': () => <g>{wave(6, 3, G, 1)}{[2, 10, 18, 26, 34].map(x => <rect key={x} x={x} y={11} width={7} height={3} fill={BL} stroke={B} strokeWidth={0.7} />)}{[2, 10, 18, 26, 34].map((x, i) => <g key={x}>{[0, 1, 2].map(k => <rect key={k} x={x} y={16 + k * 2.6} width={7} height={2.1} fill={shade(((i * 7 + k * 3) % 5) / 4)} />)}</g>)}</g>,
  'catalogue.cluster': () => <g><path d="M6 24v-6M12 24v-6M9 18v-6M20 24v-6M26 24v-6M23 18v-6M16 12v-5M34 24v-4M38 24v-4M36 20v-13M26 7h10" fill="none" stroke={G} strokeWidth={1} /><path d="M9 12h14" stroke={G} strokeWidth={1} /><circle cx={6} cy={24} r={1.6} fill={B} /><circle cx={12} cy={24} r={1.6} fill={B} /><circle cx={20} cy={24} r={1.6} fill={GR} /><circle cx={26} cy={24} r={1.6} fill={GR} /><circle cx={34} cy={24} r={1.6} fill={AM} /><circle cx={38} cy={24} r={1.6} fill={AM} /><line x1={2} x2={42} y1={9.5} y2={9.5} stroke={AM} strokeWidth={0.8} strokeDasharray="2 1.5" /></g>,
  /* ---- stage-3 prompt 01: the eleven blocks added with the templates (docs/BLOCK_INTEGRATION.md checklist step 4) ---- */
  'preprocessing.wavelet_transform': () => <g>{wave(6, 2.5, G, 1)}{matrix(2, 11, 3, 4.2, (r, c) => shade(0.15 + 0.8 * Math.abs(Math.sin((c + 1) * (r + 1) * 0.9))))}{matrix(16, 11, 3, 4.2, (r, c) => shade(0.15 + 0.8 * Math.abs(Math.cos((c + 2) * (r + 1) * 0.7))))}{matrix(30, 11, 3, 4.2, (r, c) => shade(0.15 + 0.8 * Math.abs(Math.sin((c + 3) * (r + 2) * 0.5))))}<text x={26} y={9} fill={G} style={{ fontSize: 5.5 }}>τ × s</text></g>,
  'detection.wavelet_summation': () => <g>{matrix(2, 3, 3, 4, (r, c) => shade(0.2 + 0.7 * ((r + c) % 3) / 2))}<path d="M15 8h6M18 5l3 3-3 3" fill="none" stroke={G} strokeWidth={1} /><text x={24} y={10} fill={G} style={{ fontSize: 7 }}>Σ</text><polyline points="2,23 8,22 13,21 17,14 21,22 26,22 30,15 34,21 38,22 42,23" fill="none" stroke={B} strokeWidth={1.3} /></g>,
  'detection.summation_threshold': () => <g><polyline points="2,20 6,19 10,18 13,9 16,19 20,20 24,18 27,8 30,19 34,20 38,19 42,20" fill="none" stroke={G} strokeWidth={1.2} /><line x1={2} x2={42} y1={13} y2={13} stroke={AM} strokeWidth={1} strokeDasharray="2 1.5" /><rect x={11} y={3} width={5} height={7} fill={B} rx={0.6} /><rect x={25} y={3} width={5} height={7} fill={B} rx={0.6} /><path d="M11 24c2-3 3-3 5 0M25 24c2-3 3-3 5 0" fill="none" stroke={GR} strokeWidth={1} /></g>,
  'detection.stage_encoding': () => <g><polyline points="2,18 10,8 13,20 21,9 24,21 32,10 35,22 42,12" fill="none" stroke={G} strokeWidth={1} /><rect x={3} y={9} width={38} height={4} fill={GL} opacity={0.8} />{blocks(17, 7, [B, B, AM, B, B, AM, B, B], 2, 4.6, 0.6)}<text x={35} y={8} fill={AM} style={{ fontSize: 5.5 }}>±kσ</text></g>,
  'detection.drop_detection': () => <g><rect x={11} y={3} width={7} height={20} fill={BL} opacity={0.8} /><rect x={27} y={3} width={7} height={20} fill={BL} opacity={0.8} /><polyline points="2,8 10,8 14,21 18,8 26,8 30,20 34,8 42,8" fill="none" stroke={B} strokeWidth={1.3} strokeLinejoin="round" /><circle cx={10} cy={8} r={1.5} fill={AM} /><circle cx={14} cy={21} r={1.5} fill={AM} /></g>,
  'detection.mp_motifs': () => <g>{wave(6, 2.5, G, 1)}<polyline points="2,19 6,18 10,19 13,12 16,19 20,18 24,19 27,12 30,19 33,17 36,12 39,18 42,19" fill="none" stroke={B} strokeWidth={1.2} /><rect x={10} y={2} width={6} height={22} fill={GR} opacity={0.25} /><rect x={24} y={2} width={6} height={22} fill={GR} opacity={0.25} /><rect x={33} y={2} width={6} height={22} fill={GR} opacity={0.25} /><text x={11} y={24} fill={GR} style={{ fontSize: 5 }}>G0</text></g>,
  'detection.seed_matches': () => <g>{wave(13, 5, G, 1)}<rect x={4} y={5} width={8} height={16} fill="none" stroke={PU} strokeWidth={1.3} /><rect x={18} y={5} width={8} height={16} fill="none" stroke={GR} strokeWidth={1.2} /><rect x={31} y={5} width={8} height={16} fill="none" stroke={GR} strokeWidth={1.2} strokeDasharray="2 1" /></g>,
  'detection.symbol_search': () => <g>{blocks(5, 7, [GL, B, B, AM, GL, GL, B, AM], 2, 4.6, 0.6)}<rect x={6.5} y={4} width={15} height={9} fill="none" stroke={GR} strokeWidth={1.2} rx={1} /><text x={4} y={23} fill={G} style={{ fontSize: 6.5, fontFamily: 'monospace' }}>/c+a+/</text></g>,
  'catalogue.window_images': () => <g>{[2, 12, 22].map((x, i) => <g key={x}>{matrix(x, 3, 4, 2.4, (r, c) => shade(0.2 + 0.7 * Math.abs(Math.sin((r + c + i) * 0.8))))}</g>)}{smooth(19, 2, G, 1, 2, 42)}</g>,
  'catalogue.cnn_score': () => <g><rect x={2} y={4} width={9} height={9} rx={1.5} fill={PU} />{blocks(16, 6, [G, G, G, G], 2, 4, 1)}<polyline points="15,20 19,19 23,20 27,10 31,19 35,20 39,18 42,20" fill="none" stroke={B} strokeWidth={1.3} /><text x={13} y={11} fill={G} style={{ fontSize: 6 }}>p(int)</text></g>,
  /* ---- frame chain-6b glyphs the registry did not yet draw (the B24 chain and the encoding / interrogation blocks) ---- */
  'preprocessing.noise_floor': () => <g><rect x={3} y={9} width={38} height={8} fill={GL} />{wave(13, 2, B, 1.2)}<polyline points="18,13 21,4 24,13" fill="none" stroke={B} strokeWidth={1.2} /><circle cx={21} cy={4} r={2} fill={AM} /></g>,
  'encoding.smoothing': () => <g><polyline points="2,16 6,9 10,17 14,8 18,15 22,7 26,16 30,9 34,15 38,8 42,14" fill="none" stroke={G} strokeWidth={1} />{smooth(12, 2, B, 1.4)}</g>,
  'encoding.run_length': () => <g>{blocks(9, 8, [BL, BL, BL, BL], 2, 5, 1)}<path d="M26 13h8M31 10l3 3-3 3" fill="none" stroke={G} strokeWidth={1.1} /><rect x={36} y={8} width={7} height={10} fill={B} rx={0.6} /></g>,
  'encoding.alphabet_remap': () => <g>{blocks(3, 6, [BL, BL, BL, BL], 5, 6, 3.5)}<path d="M8 9l10 8M18 9l-10 8M27 9l10 8M37 9l-10 8" stroke={G} strokeWidth={0.8} />{blocks(17, 6, [B, B, B, B], 5, 6, 3.5)}</g>,
  'encoding.word_filter': () => <g>{blocks(7, 7, [GL, GL, B, B, GL, GL], 3, 5.5, 1.3)}<path d="M16 18v3h11v-3" fill="none" stroke={B} strokeWidth={1.1} /></g>,
  'detection.seeded_search': () => <g>{wave(13, 5, G, 1)}<rect x={6} y={5} width={9} height={16} fill="none" stroke={PU} strokeWidth={1.3} /><rect x={27} y={5} width={9} height={16} fill="none" stroke={GR} strokeWidth={1.3} /></g>,
  'detection.drop': () => <g><rect x={11} y={3} width={7} height={20} fill={BL} opacity={0.8} /><rect x={27} y={3} width={7} height={20} fill={BL} opacity={0.8} /><polyline points="2,8 10,8 14,21 18,8 26,8 30,20 34,8 42,8" fill="none" stroke={B} strokeWidth={1.3} strokeLinejoin="round" /></g>,
  'model.stage': () => <g><rect x={3} y={4} width={6} height={18} fill={BL} /><rect x={12} y={8} width={6} height={12} fill={BL} /><rect x={21} y={10} width={6} height={7} fill={B} /><path d="M27 13.5h6" stroke={G} strokeWidth={1} /><ellipse cx={37.5} cy={13.5} rx={4.5} ry={3} fill={GR} /></g>,
  'interrogation.slope': () => <g><path d="M2 7h10" stroke={G} strokeWidth={1.2} /><path d="M12 7L28 19h14" fill="none" stroke={G} strokeWidth={1.2} /><path d="M12 7L28 19" stroke={B} strokeWidth={1.6} /><circle cx={12} cy={7} r={2} fill={AM} /><circle cx={28} cy={19} r={2} fill={AM} /></g>,
  'interrogation.aggregate': () => <g>{[[6, 18], [11, 12], [16, 7], [21, 5], [26, 9], [31, 14], [36, 18]].map(([x, y]) => <rect key={x} x={x - 2} y={y} width={4.2} height={23 - y} fill={BL} />)}<path d="M2 22C10 21 13 4 21 4S32 21 42 22" fill="none" stroke={B} strokeWidth={1.3} /></g>,
  /* ---- fixup-d: the per-event feature blocks and the inversion ---- */
  'interrogation.event_shape': () => <g><rect x={5} y={3} width={30} height={20} fill={BL} opacity={0.45} /><polyline points="2,9 8,9 12,7 16,21 22,21 30,11 42,10" fill="none" stroke={G} strokeWidth={1.1} strokeLinejoin="round" /><path d="M12 7L16 21" stroke={B} strokeWidth={1.6} /><path d="M12 4v17" stroke={AM} strokeWidth={0.9} strokeDasharray="1.5 1" /><path d="M14 14h11" stroke={GR} strokeWidth={1.1} /><circle cx={12} cy={7} r={1.6} fill={AM} /><circle cx={16} cy={21} r={1.6} fill={AM} /></g>,
  'interrogation.intervals': () => <g><polyline points="2,8 6,8 8,19 10,8 18,8 20,19 22,8 34,8 36,19 38,8 42,8" fill="none" stroke={G} strokeWidth={1.1} strokeLinejoin="round" /><path d="M8 23h12M20 23h16" stroke={B} strokeWidth={1.3} /><path d="M8 21v4M20 21v4M36 21v4" stroke={B} strokeWidth={1} /></g>,
  'preprocessing.invert': () => <g><polyline points="2,13 8,13 11,4 14,13 42,13" fill="none" stroke={G} strokeWidth={1.1} strokeLinejoin="round" /><polyline points="2,13 22,13 25,22 28,13 42,13" fill="none" stroke={B} strokeWidth={1.4} strokeLinejoin="round" /><path d="M11 6C14 10 20 16 24 20" fill="none" stroke={AM} strokeWidth={0.9} strokeDasharray="1.5 1" /></g>,
  'preprocessing.sliding_windows': () => <g>{smooth(13, 3, G, 1)}{[3, 16, 29].map(x => <rect key={x} x={x} y={5} width={11} height={16} fill="none" stroke={B} strokeWidth={1.3} />)}</g>,
  'model.template': () => <g>{[6, 13, 20].map(y => <circle key={`a${y}`} cx={5} cy={y} r={2} fill={BL} />)}{[7, 13, 19].map(y => <circle key={`b${y}`} cx={21} cy={y} r={2.4} fill={B} />)}{[6, 13, 20].map(y1 => [7, 13, 19].map(y2 => <path key={`${y1}-${y2}`} d={`M7 ${y1}L19 ${y2}`} stroke={G} strokeWidth={0.5} />))}{[7, 13, 19].map(y => <path key={`c${y}`} d={`M23 ${y}L34 13`} stroke={G} strokeWidth={0.5} />)}<ellipse cx={38} cy={13} rx={4} ry={3} fill={GR} /></g>,
  'catalogue.classifier': () => <g><circle cx={6} cy={8} r={2} fill={B} /><circle cx={9} cy={16} r={2} fill={GR} /><circle cx={5} cy={21} r={2} fill={AM} /><path d="M15 13h5M20 13v-7h5M20 13v7h5M25 6v-3h4M25 6v3h4M25 20v-3h4M25 20v3h4" fill="none" stroke={G} strokeWidth={0.9} /><rect x={31} y={4} width={11} height={18} rx={2} fill={B} /><path d="M34 9h5M34 13h5M34 17h3" stroke="#fff" strokeWidth={1} /></g>,
}

const BY_SIG: Record<string, () => ReactElement> = {
  'signal→signal': () => <g>{wave(13, 6, G)}{smooth(13, 4, B)}</g>,
  'signal→scores': () => <g>{wave(7, 3, G, 1)}<polyline points="2,19 6,18 10,19 14,17 18,19 22,18 26,8 30,18 34,19 38,17 42,19" fill="none" stroke={B} strokeWidth={1.3} /><circle cx={26} cy={8} r={1.6} fill={RD} /></g>,
  'scores→spanset': () => <g><polyline points="2,19 6,18 10,17 13,8 16,18 20,19 24,17 27,7 30,18 34,19 38,18 42,19" fill="none" stroke={G} strokeWidth={1.2} /><line x1={2} x2={42} y1={12} y2={12} stroke={AM} strokeWidth={1} strokeDasharray="2 1.5" /><rect x={11} y={3} width={5} height={6} fill={B} rx={0.6} /><rect x={25} y={3} width={5} height={6} fill={B} rx={0.6} /></g>,
  'signal→spanset': () => <g>{wave(13, 6, G)}<rect x={9} y={2} width={7} height={22} fill={B} opacity={0.35} /><rect x={28} y={2} width={6} height={22} fill={B} opacity={0.35} /></g>,
  'signal→encoding': () => <g>{wave(8, 3.5, G, 1)}{blocks(15, 8, [B, AM, G, B, B, AM, G, B])}</g>,
  'signal→windowset': () => <g>{wave(11, 5, G)}{[2, 10, 18, 26, 34].map(x => <rect key={x} x={x} y={19} width={7} height={5} fill={BL} stroke={B} strokeWidth={0.8} />)}</g>,
  'windowset→grouping': () => <g>{blocks(4, 7, [G, G, G, G, G, G, G, G])}{blocks(15, 7, [B, GR, B, AM, GR, B, AM, B])}</g>,
  'windowset→windowset': () => <g>{blocks(4, 7, [G, G, G, G, G, G, G, G])}{blocks(15, 7, [B, BL, B, B, BL, B, BL, B])}</g>,
  'windowset→encoding': () => <g>{blocks(3, 5, [G, G, G, G], 2, 8, 1)}{Array.from({ length: 4 }, (_, r) => Array.from({ length: 4 }, (_, c) => <rect key={`${r}-${c}`} x={22 + c * 5} y={4 + r * 5} width={4.4} height={4.4} fill={(r + c) % 3 === 0 ? B : (r + c) % 3 === 1 ? BL : '#5aa9ff'} />))}</g>,
  'grouping→model': () => <g><circle cx={7} cy={8} r={2.5} fill={B} /><circle cx={7} cy={18} r={2.5} fill={GR} /><circle cx={13} cy={13} r={2.5} fill={AM} /><path d="M17 13h6M23 13v-6h6M23 13v6h6" fill="none" stroke={G} strokeWidth={1} /><rect x={31} y={4} width={11} height={18} rx={2} fill={B} /></g>,
  'model→scores': () => <g><rect x={2} y={4} width={9} height={9} rx={1.5} fill={PU} />{blocks(16, 6, [G, G, G, G], 2, 4, 1)}<polyline points="15,20 19,19 23,20 27,10 31,19 35,20 39,18 42,20" fill="none" stroke={B} strokeWidth={1.3} /></g>,
  'spanset→spanset': () => <g><rect x={2} y={4} width={40} height={7} fill={G} opacity={0.4} /><rect x={6} y={15} width={9} height={7} fill={B} /><rect x={20} y={15} width={6} height={7} fill={B} /><rect x={31} y={15} width={9} height={7} fill={B} /></g>,
  'encoding→spanset': () => <g>{blocks(3, 6, [G, AM, G, G, AM, G, G, G])}<rect x={7} y={14} width={6} height={9} fill={B} opacity={0.5} /><rect x={22} y={14} width={6} height={9} fill={B} opacity={0.5} /></g>,
  'encoding→encoding': () => <g>{blocks(4, 7, [BL, BL, BL, BL], 2, 7, 1)}<path d="M20 13h5" stroke={G} strokeWidth={1.2} /><rect x={28} y={3} width={14} height={10} fill={B} rx={1} /></g>,
}

export function glyphKey(input: TypeKind, output: TypeKind) { return `${input}→${output}` }
/** 'own' when the block has a registered glyph, 'signature' for the type-signature fallback. */
export function glyphSource(name: string): 'own' | 'signature' { return BY_NAME[name] ? 'own' : 'signature' }

export function Glyph({ adapter, width = 44, height = 26, className }: { adapter: Pick<AdapterCard, 'input_kind' | 'output_kind'> & { name?: string }; width?: number; height?: number; className?: string }) {
  const own = adapter.name ? BY_NAME[adapter.name] : undefined
  const draw = own ?? BY_SIG[glyphKey(adapter.input_kind, adapter.output_kind)]
  return (
    <svg width={width} height={height} viewBox="0 0 44 26" className={className} aria-hidden="true" style={{ flex: 'none' }} data-glyph={own ? adapter.name : `sig:${glyphKey(adapter.input_kind, adapter.output_kind)}`}>
      <rect x={0.5} y={0.5} width={43} height={25} rx={3} fill="#fff" stroke={GL} />
      {draw ? draw() : <g><rect x={3} y={8} width={12} height={10} rx={1.5} fill={G} /><path d="M18 13h7" stroke={G} strokeWidth={1.2} /><rect x={28} y={8} width={12} height={10} rx={1.5} fill={B} /></g>}
    </svg>
  )
}
