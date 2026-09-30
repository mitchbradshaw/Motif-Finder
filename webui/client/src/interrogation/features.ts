/* What a feature key means on one member (fixup-e). Every value here is READ — from the store's slope
 * measures (01 Resolve spans) or from interrogation.event_shape (01 Event shape) — and `null` means the core
 * did not measure it for this event. Nothing is derived on the page: the three constants that used to live
 * here (`half_width_s = duration × 0.84`, `rise_s = × 0.31`, `isi_s = × 4.2`) were fabrications drawn as
 * measurements, and a browser-side recovery reported a never-recovered event as 0 s. */
import type { InterrogationMember, Upstream } from '../fixtures/interrogation'

/** The member's value for a feature key, or `null` when it is not measured. Two keys — `max_slope` and
 *  `peakedness` — exist on both upstreams and are measured by different code: the store's gradients for
 *  Resolve spans, the shape block's for Event shape (they agree on 408 of 410 seed events, but they are not
 *  the same number and the page does not mix them). */
export function featureOf(m: InterrogationMember, key: string, upstream: Upstream): number | null {
  const x = m.measures
  switch (key) {
    case 'depth_mV': return m.depth_mV
    case 'duration_s': return m.duration_s
    case 'onset_h': return m.onset_h
    case 'recovery_s': case 'decay_s': return m.recovery_s
    case 'max_slope': return upstream === 'event-shape' ? abs(x?.max_slope) : Math.abs(m.max_slope)
    case 'peakedness': return upstream === 'event-shape' ? (x?.peakedness ?? null) : m.peakedness
    case 'amplitude_mV': return x?.amplitude_mV ?? null
    case 'precursor_mV': return x?.precursor_mV ?? null
    case 'width_s': return x?.width_s ?? null
    case 'event_duration_s': return x?.event_duration_s ?? null
    case 'fwhm_s': case 'half_width_s': return x?.fwhm_s ?? null
    case 'rise_time_s': case 'rise_s': return x?.rise_time_s ?? null
    default: return null
  }
}

const abs = (v: number | null | undefined) => (v === null || v === undefined ? null : Math.abs(v))

/** Why a value can be missing, per feature — printed beside every `n` that is smaller than the family. */
export function whyMissing(key: string, recovery: { frac: number; max_mult: number }): string {
  const pct = `${Math.round(recovery.frac * 100)} %`
  switch (key) {
    case 'recovery_s': case 'decay_s':
      return `did not return to ${pct} of the amplitude within ${recovery.max_mult} event widths of the extremum, or before the next event — not recovered, which is not 0 s`
    case 'event_duration_s':
      return `duration runs onset → recovery, so an event that did not recover (${pct} of the amplitude, ${recovery.max_mult} widths) has none`
    case 'fwhm_s': case 'half_width_s':
      return 'never re-crossed the half level (onset level − amplitude / 2) inside the same bound as recovery — no full width at half maximum'
    case 'rise_time_s': case 'rise_s':
      return 'a drop has no rise: null, not 0 (Q19) — only a spike, or a drop the chain inverted, has a rise time'
    case 'interval_h':
      return 'the first event on each recording × channel has no interval before it'
    default:
      return 'not measured for this event'
  }
}

/** A measure for a table cell: the number, or an explicit "—" (never 0, never blank) when it is not measured. */
export function fmtMeasure(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined || !Number.isFinite(v) ? '—' : v.toFixed(digits)
}
