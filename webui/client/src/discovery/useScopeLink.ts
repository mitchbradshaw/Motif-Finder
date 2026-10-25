/* tq-scope (2026-10-25): a deep-linked Discovery scope (`?recording=<key>&channels=<names>`) and its one write, as one
 * hook. Its state was spread over useDiscovery: three link values, an error, a key and an effect, and a writing flag
 * that re-tested what the target already implied. The resolution is pure (./scopeLink.ts); this holds the query
 * keys, the write and the error it may come back with, and says where the link stands in one `phase`.
 *
 * site-runs item 5: a link that names channels (Cross-channel's *Apply a template across these N channels*) BECOMES
 * the session's scope, through the Scope card's own write, and its keys are cleared once it has landed, so a template
 * is applied where the page says. A name the recording does not have is refused in words and nothing is sent. A link
 * with no channels (`?recording=` alone, the held-out states) and a held-out recording stay a view. */
import { useEffect, useState } from 'react'
import { writeSession } from '../api/discovery'
import type { DiscSessionPayload } from '../api'
import { useQueryState } from '../kit'
import { resolveScopeLink, type LinkRecording, type LinkScope, type LinkTarget } from './scopeLink'

/** `refused` covers a link the page will not send and a write the bridge rejected (fix round F2: that is said
 *  through the same callout, and the page does not hang on its loading layout while it is held). */
export type LinkPhase = { kind: 'idle' } | { kind: 'writing'; target: LinkTarget } | { kind: 'refused'; why: string }

/** `recordings` is null until the session has been read: no link is resolved against an empty list.
 *  `took` is handed the bridge's answer to the link's write. */
export function useScopeLink<S extends LinkScope>(scope0: S | null, recordings: LinkRecording[] | null, took: (p: DiscSessionPayload) => void) {
  const [channelsQ, setChannelsQ] = useQueryState('channels', '')
  const [recordingQ, setRecordingQ] = useQueryState('recording', '')
  const [error, setError] = useState<string | null>(null)
  const link = scope0 && recordings ? resolveScopeLink(recordingQ, channelsQ, scope0, recordings) : null
  const asked = link && 'scope' in link ? link : null
  /* a key is set only when it is there: every set replaces the hash and fires 'hashchange', and the toast host drops
   * toasts older than 1 s on each one ("opened the X session as it was left" vanished after every scope edit) */
  const clear = () => { setError(null); if (channelsQ) setChannelsQ(null); if (recordingQ) setRecordingQ(null) }

  const askedKey = asked ? `${asked.scope.recording}|${asked.scope.channels.join(',')}|${asked.scope.section?.join(',') ?? 'own'}` : ''
  useEffect(() => {
    if (!asked) return
    if (asked.same) { clear(); return }
    setError(null)
    let alive = true
    const t = asked.scope
    // another recording's link carries no section: that recording's session keeps its own
    writeSession({ recording: t.recording, channels: t.channels, section: t.section ?? undefined })
      .then(p => { if (!alive) return; took(p); clear() })
      .catch(e => {
        console.error('the linked scope could not be written', e)
        if (alive) setError(`the bridge did not take the link's scope — ${(e instanceof Error ? e.message : String(e)).replace(/^\d{3} /, '')} — the session keeps its scope`)
      })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [askedKey])

  const phase: LinkPhase = link && 'refused' in link ? { kind: 'refused', why: link.refused }
    : error ? { kind: 'refused', why: error }
      : asked && !asked.same ? { kind: 'writing', target: asked.scope } : { kind: 'idle' }

  /* While a link is written or refused the page stays on the session the bridge HOLDS: drawing the target over it
   * sent the new names to the old recording ("no channel(s) ['CH1', 'CH2'] on M2_aug_concat_fs1"). A bare
   * `?recording=` is drawn over the session as a view. */
  const scope: S | null = !scope0 || link || error ? scope0
    : (channelsQ || recordingQ) ? {
      ...scope0,
      recording: recordingQ || scope0.recording,
      channels: channelsQ ? channelsQ.split(',').filter(Boolean) : scope0.channels,
    } : scope0

  /** After the Scope card's own write: a new recording or new channels end the link (critic, night-disc: a bare
   *  `?recording=` view must go once the researcher picks another recording, or the page keeps drawing it over the
   *  session the bridge just opened). A section alone leaves it. */
  const settle = (patch: { recording?: string; channels?: string[] }) => { if ((channelsQ || recordingQ || error) && (patch.recording !== undefined || patch.channels)) clear() }

  return { phase, scope, clear, settle }
}
