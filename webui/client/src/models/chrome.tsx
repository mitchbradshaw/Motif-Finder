/* Models shared chrome (inventory "Models — shared chrome"): the Launch · Results · Compare · Registry tab row with its
 * per-page Jobs link, the arm letter badges (A green · B purple · RF grey), the null chip, loading and loud-failure cards. */
import type { ReactNode } from 'react'
import { Button, Icon, InfoTip, Tabs, useDemoWrites, type IconName } from '../kit'
import { navigate } from '../state'

export type ModelsTab = 'launch' | 'results' | 'compare' | 'registry'
const TAB_ITEMS: { value: ModelsTab; label: string; icon: IconName }[] = [
  { value: 'launch', label: 'Launch', icon: 'rocket' },
  { value: 'results', label: 'Results', icon: 'bar-chart' },
  { value: 'compare', label: 'Compare', icon: 'compare' },
  { value: 'registry', label: 'Registry', icon: 'library' },
]

/** The in-page tab row. `middle` sits right-aligned before the Jobs link (Results puts its arm Seg there). */
export function ModelsTabs({ current, jobsLink, middle }: { current: ModelsTab; jobsLink: ReactNode; middle?: ReactNode }) {
  return (
    <div className="m-tabs-row" data-testid="models-tabs-row">
      <Tabs items={TAB_ITEMS} value={current} onChange={v => navigate(`models/${v}`)} testid="models-tabs" ariaLabel="Models pages" />
      <span className="k-spacer" />
      {middle}
      {jobsLink}
    </div>
  )
}

/** "2 training jobs · open in Jobs ↗" — counts the canon training jobs plus any launched from this tab. */
export function TrainingJobsLink({ base }: { base: number }) {
  const added = useDemoWrites('models').filter(w => w.kind === 'add-training-job').length
  return (
    <button type="button" className="m-jobs-link" onClick={() => navigate('jobs?kind=cluster')} data-testid="open-training-jobs"
      title="opens Jobs filtered to training (cluster) jobs">
      <Icon name="checklist" size={14} />{base + added} training jobs · open in Jobs<Icon name="external" size={13} />
    </button>
  )
}

export function JobLink({ id, status }: { id: string; status: string }) {
  return (
    <button type="button" className="m-jobs-link" onClick={() => navigate(`jobs/cluster/${id}`)} data-testid="open-job" title={`opens ${id} in Jobs`}>
      <Icon name="checklist" size={14} />{id} · {status} · open in Jobs<Icon name="external" size={13} />
    </button>
  )
}

export const ARM_COLOUR = { A: 'var(--green)', B: 'var(--purple)', RF: '#6b7280' } as const
export function ArmBadge({ letter, size = 18 }: { letter: 'A' | 'B' | 'RF'; size?: number }) {
  return <span className="m-arm" style={{ background: ARM_COLOUR[letter], height: size, minWidth: size, fontSize: letter === 'RF' ? 8.5 : 10 }} aria-label={`arm ${letter}`}>{letter}</span>
}

/** "● null label shuffle · RF 200× + model 5× ⓘ" */
export function NullChip() {
  return (
    <span className="m-tool-chip" data-testid="null-chip">
      <span className="m-dot" style={{ background: 'var(--green)' }} />
      <span className="muted">null</span> label shuffle · RF 200× + model 5×
      <InfoTip title="Null" testid="null-chip-info">
        Label shuffle: 200× on the RF baseline plus 5× on the full model — every full-model shuffle is a full retrain.
        <div style={{ marginTop: 6 }}><Button variant="link" size="sm" icon="external" onClick={() => navigate('settings/nulls')}>Settings › Nulls</Button></div>
      </InfoTip>
    </span>
  )
}

export const Loading = ({ height = 360, testid = 'models-loading' }: { height?: number; testid?: string }) => <div className="skeleton" style={{ height }} data-testid={testid} aria-label="loading" />

export function LoadFailed({ what, error, onRetry, action }: { what: string; error: Error; onRetry?: () => void; action?: ReactNode }) {
  return (
    <div className="error-card" data-testid="models-load-failed" role="alert">
      <h3>Could not read {what}</h3>
      <div className="mono small" style={{ color: 'var(--red)' }}>{error.message}</div>
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>{onRetry && <Button size="sm" icon="refresh" onClick={onRetry}>Retry</Button>}{action}</div>
    </div>
  )
}

export const f2 = (v: number) => v.toFixed(2)
export const signed = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)}`
