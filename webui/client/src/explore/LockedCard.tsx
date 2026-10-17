/* Locked state for the held-out recording (spec §0 D6). Rendered from the API's 423 so the
   message on screen is the server's refusal, never a client-side guess. Nothing from the
   recording is drawn. */
import type { ApiError } from '../api'
import { InfoTip } from '../kit'

export function LockedCard({ error, file }: { error: ApiError | null; file?: string }) {
  const name = file ?? 'This recording'
  return (
    <div className="card card-pad ex-locked" data-testid="locked-card" role="status">
      <div className="row" style={{ gap: 10 }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>
        <span className="b" style={{ fontSize: 14 }}>{name} is held out</span>
        <span className="chip grey">locked</span>
        <InfoTip title="Held out">While the held-out lock is on, the API refuses every request for this recording and nothing from it is shown here, in Analyse or anywhere else (spec §0 D6). To use it, turn the lock off in Settings › Datasets (type the recording's name); it opens everywhere at once.</InfoTip>
      </div>
      <div className="mono" style={{ fontSize: 12, marginTop: 8 }} data-testid="locked-message">
        {error ? <>{error.status ? `${error.status} · ` : ''}{error.message}</> : 'checking with the server…'}
      </div>
    </div>
  )
}
