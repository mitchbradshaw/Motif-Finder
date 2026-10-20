/* site-runs (2026-10-20): a deep-linked Discovery scope, and the scope built from the bridge's session.
 * Pure (no runtime imports) so tests/test_site_runs_scope_link.py runs it under Node.
 *
 * Explore › Cross-channel › *Apply a template across these N channels* opened Discovery with channel IDS and no
 * recording; the session (on another recording) was then asked for channels named `667…`. A link is now resolved
 * here first: it names a recording key and channel NAMES, every name must be a channel of that recording, and only
 * then does session.ts write it to the session through `putScope` — the Scope card's own write. */

export interface LinkRecording { key: string; label?: string; channels: string[]; hours: number; heldOut?: boolean }
export interface LinkScope { recording: string; channels: string[]; section: [number, number] }
/** `section` is null for another recording: the bridge opens that recording's own session, which keeps its own
 *  section (clamped to the recording by the bridge); carrying the old recording's hours over would overwrite it. */
export interface LinkTarget { recording: string; channels: string[]; section: [number, number] | null }
export type LinkResolution = null | { refused: string } | { scope: LinkTarget; same: boolean }

/** The scope a Discovery link asks for, or why it is refused; null when there is nothing to write.
 *  A link that names no channels (`?recording=` alone) is a VIEW, as before: the held-out states open
 *  `?recording=M4…` to show the Scope card's refusal, and a write there would move the whole session. A held-out
 *  recording is never written either — the Scope card refuses it from the client's copy. */
export function resolveScopeLink(recordingQ: string, channelsQ: string, current: LinkScope, recordings: LinkRecording[]): LinkResolution {
  const names = (channelsQ || '').split(',').map(s => s.trim()).filter(Boolean)
  if (!names.length) return null
  const key = recordingQ || current.recording
  const rec = recordings.find(r => r.key === key)
  if (!rec) return { refused: `the link names a recording “${key}” this project does not have — nothing was changed` }
  if (rec.heldOut) return null
  const label = rec.label || rec.key
  const unknown = names.filter(n => !rec.channels.includes(n))
  if (unknown.length) {
    return { refused: `${unknown.join(', ')} ${unknown.length === 1 ? 'is not a channel' : 'are not channels'} of ${label} — the link was not applied; the session keeps its scope` }
  }
  const section = rec.key === current.recording ? current.section : null
  const same = rec.key === current.recording && names.join(',') === current.channels.join(',')
  return { scope: { recording: rec.key, channels: names, section }, same }
}

/** The bridge's session payload, as much of it as the scope reads. */
export interface SessionLike {
  name: string; recording: string; channels: string[]; section: [number, number]
  null: { method: string | null; n: number; requested?: string | null; reason?: string | null; explicit?: boolean }
  nulls?: { template: { method: string | null; n: number } }
}

/** The page's scope from the bridge's session — the first read's and every `putScope` answer's, so a change of
 *  recording shows the session the bridge OPENED (its name included), never the old one with a patch merged in. */
export function scopeFromSession(s: SessionLike) {
  return {
    name: s.name, saved: true, recording: s.recording, channels: s.channels, section: s.section,
    nullMethod: s.null.method, nullN: s.null.n, nullRequested: s.null.requested ?? null, nullReason: s.null.reason ?? null,
    nullTemplateN: s.nulls?.template.n ?? s.null.n, nullTemplateMethod: s.nulls?.template.method ?? s.null.method,
    nullExplicit: !!s.null.explicit,
  }
}
