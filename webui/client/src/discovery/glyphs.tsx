/* Discovery-local algorithm thumbnails for the runs list and stage cards (frames discovery-1, -1b, -3, -3b).
 * The kit registry has no seeded-search, drop-detection, noise-floor or human-reference glyph yet (requested in
 * pages/requests/discovery.md); these draw what the frames draw, in the registry's 44 × 26 box. */
import type { GlyphKind } from '../api/discovery'
import { BlockGlyph, SourceGlyph } from '../kit'

const B = '#0a84ff', G = '#6b7280', GR = '#22a06b', PU = '#af52de', AM = '#e8900c', RD = '#e5484d'

export function RunGlyph({ kind, width = 44, height = 26 }: { kind: GlyphKind; width?: number; height?: number }) {
  switch (kind) {
    case 'source': return <SourceGlyph width={width} height={height} />
    case 'baseline': return <BlockGlyph name="baseline" width={width} height={height} />
    case 'mp': return <BlockGlyph name="matrix_profile" width={width} height={height} />
    case 'threshold': return <BlockGlyph name="threshold" width={width} height={height} />
    case 'spike': return <BlockGlyph name="spike" width={width} height={height} />
    case 'model': return <BlockGlyph name="model_stage" width={width} height={height} />
  }
  return (
    <svg width={width} height={height} viewBox="0 0 44 26" aria-hidden="true" style={{ flex: 'none' }} data-glyph={kind}>
      <rect x={0.5} y={0.5} width={43} height={25} rx={3} fill="#f7f8fa" stroke="#e5e7eb" />
      {kind === 'human' && <g><path d="M4 10c4-3 7 3 11 0s7-3 11 0 8 3 14 0" fill="none" stroke={G} strokeWidth={1.2} /><path d="M9 19h7M21 19h6M31 19h6" stroke={GR} strokeWidth={2.2} strokeLinecap="round" /></g>}
      {kind === 'drop' && <g><path d="M3 8h8c2 0 3 12 5 12s2-12 4-12h3c2 0 3 12 5 12s2-12 4-12h9" fill="none" stroke={B} strokeWidth={1.4} strokeLinejoin="round" /><rect x={13} y={4} width={6} height={18} fill={B} opacity={0.14} /><rect x={25} y={4} width={6} height={18} fill={B} opacity={0.14} /></g>}
      {kind === 'sax' && <g><polyline points="3,18 9,18 9,8 17,8 17,15 23,15 23,8 31,8 31,18 41,18" fill="none" stroke={B} strokeWidth={1.4} /></g>}
      {kind === 'seed' && <g><rect x={5} y={6} width={13} height={14} fill="none" stroke={PU} strokeWidth={1.2} /><path d="M6 17l5-9 6 9" fill="none" stroke={PU} strokeWidth={1.1} /><rect x={24} y={6} width={13} height={14} fill="none" stroke={GR} strokeWidth={1.2} /><path d="M25 16l5-8 6 10" fill="none" stroke={GR} strokeWidth={1.1} /><path d="M19.5 13h3" stroke={G} strokeWidth={1} /></g>}
      {kind === 'noise' && <g><polyline points="3,14 6,11 8,16 11,9 13,15 16,12 18,17 21,8 24,15 27,12 30,14 33,10 36,15 41,13" fill="none" stroke={B} strokeWidth={1.1} /><line x1={3} x2={41} y1={7} y2={7} stroke={AM} strokeWidth={0.9} strokeDasharray="2 1.5" /><line x1={3} x2={41} y1={19} y2={19} stroke={AM} strokeWidth={0.9} strokeDasharray="2 1.5" /><circle cx={21} cy={8} r={1.4} fill={RD} /></g>}
    </svg>
  )
}
