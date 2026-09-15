/* Algorithm glyphs (frame chain-6b). The registry lives in analyse/glyphs.tsx (unchanged, so every existing import
 * keeps working); the kit re-exports it and adds BlockGlyph, which takes a registry name or friendly alias. */
import type { TypeKind } from '../api'
import { Glyph } from '../analyse/glyphs'

export { Glyph, glyphKey, glyphSource } from '../analyse/glyphs'

/** Friendly aliases → [registry name, input kind, output kind]. Unknown names fall back to the signature glyph. */
export const GLYPH_ALIASES: Record<string, [string, TypeKind, TypeKind]> = {
  baseline: ['preprocessing.detrend', 'signal', 'signal'],
  bandpass: ['preprocessing.bandpass', 'signal', 'signal'],
  highpass: ['preprocessing.highpass', 'signal', 'signal'],
  lowpass: ['preprocessing.lowpass', 'signal', 'signal'],
  noise_floor: ['preprocessing.noise_floor', 'signal', 'signal'],
  surrogate: ['preprocessing.surrogate', 'signal', 'signal'],
  sax: ['detection.sax_csax', 'signal', 'encoding'],
  symbol_smoothing: ['encoding.smoothing', 'encoding', 'encoding'],
  gramian: ['catalogue.gramian_fusion', 'windowset', 'encoding'],
  image_encode: ['catalogue.gramian_fusion', 'windowset', 'encoding'],
  stft: ['detection.freq_stft', 'signal', 'encoding'],
  matrix_profile: ['detection.matrix_profile', 'signal', 'scores'],
  seeded_search: ['detection.seeded_search', 'signal', 'scores'],
  threshold: ['detection.threshold', 'scores', 'spanset'],
  drop_detection: ['detection.drop', 'encoding', 'spanset'],
  spike: ['detection.spike_v1', 'signal', 'spanset'],
  rupture: ['detection.rupture', 'signal', 'spanset'],
  model_stage: ['model.stage', 'model', 'scores'],
  sliding_windows: ['preprocessing.sliding_windows', 'signal', 'windowset'],
  window_matrix: ['preprocessing.window_matrix', 'windowset', 'windowset'],
  cluster: ['catalogue.cluster', 'windowset', 'grouping'],
  classifier: ['catalogue.classifier', 'grouping', 'model'],
  model: ['catalogue.classifier', 'grouping', 'model'],
}

export interface BlockGlyphProps { name: string; input?: TypeKind; output?: TypeKind; width?: number; height?: number; className?: string }
/** `<BlockGlyph name="matrix_profile" />` or a registry name with its kinds: `<BlockGlyph name="detection.threshold" input="scores" output="spanset" />`. */
export function BlockGlyph({ name, input, output, width = 44, height = 26, className }: BlockGlyphProps) {
  const alias = GLYPH_ALIASES[name]
  const reg = alias?.[0] ?? name
  return <Glyph adapter={{ name: reg, input_kind: input ?? alias?.[1] ?? 'signal', output_kind: output ?? alias?.[2] ?? 'signal' }} width={width} height={height} className={className} />
}

/** Source tile glyph (a plain waveform), used as the first block of a chain. */
export function SourceGlyph({ width = 44, height = 26 }: { width?: number; height?: number }) {
  return (
    <svg width={width} height={height} viewBox="0 0 44 26" aria-hidden="true" style={{ flex: 'none' }} data-glyph="source">
      <rect x={0.5} y={0.5} width={43} height={25} rx={3} fill="#fff" stroke="#e5e7eb" />
      <path d="M8 13h5l2-5 3 10 3-8 2 5 2-2h11" fill="none" stroke="#6b7280" strokeWidth={1.3} strokeLinejoin="round" />
    </svg>
  )
}
