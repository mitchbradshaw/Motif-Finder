/* The encoded-image thumbnails (frames training-0, training-3). No kit component draws a raster, so the
 * pseudo-image from fixtures/training.ts is painted as one <rect> per cell. Not a plot of mV — an image. */
import { encodingImage, type EncodingKind } from '../fixtures/training'

/** Yellow → blue ramp (the frames' GASF/GADF palette); recurrence plots use the same ramp. */
function ramp(v: number): string {
  const t = Math.max(0, Math.min(1, (v + 1) / 2))
  const stops: [number, number, number][] = [[247, 234, 160], [163, 205, 220], [110, 155, 195], [74, 100, 140]]
  const i = Math.min(stops.length - 2, Math.floor(t * (stops.length - 1)))
  const f = t * (stops.length - 1) - i
  const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

export function EncodingImage({ kind, window, size = 66, n = 20, testid }: {
  kind: EncodingKind; window: number; size?: number; n?: number; testid?: string
}) {
  const grid = encodingImage(kind, window, n)
  const c = size / n
  return (
    <svg className="tr-img" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={`${kind.toUpperCase()} encoding of window ${window}`} data-testid={testid}>
      {grid.map((row, i) => row.map((v, j) => (
        <rect key={`${i}-${j}`} x={j * c} y={i * c} width={c + 0.4} height={c + 0.4} fill={ramp(v)} />
      )))}
    </svg>
  )
}
