/* Jobs shared chrome: the loading and loud-failure cards every card on the board draws. */
import { Button } from '../kit'

export const Loading = ({ height = 320, testid = 'jobs-loading' }: { height?: number; testid?: string }) => (
  <div className="jb-loading" style={{ minHeight: height }} data-testid={testid} aria-label="loading">reading jobs…</div>
)

/** Loud failure (brief): a read that throws renders the error, never a blank. */
export function LoadFailed({ what, error, onRetry }: { what: string; error: Error; onRetry?: () => void }) {
  return (
    <div className="error-card" role="alert" data-testid="jobs-load-failed">
      <h3>Could not read {what}</h3>
      <div className="mono small" style={{ color: 'var(--red)' }}>{error.message}</div>
      {onRetry && <div style={{ marginTop: 8 }}><Button size="sm" icon="refresh" onClick={onRetry}>Retry</Button></div>}
    </div>
  )
}
