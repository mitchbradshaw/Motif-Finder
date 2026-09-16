/* Settings › Audit log (frame settings-13 · spec §9.13).
 * Append-only: every act that changes what a result means, in order. Entries cannot be edited or deleted. */
import { Badge, Button, EmptyState, SectionCard, Seg, Table, useDemoWrites, useNotWired, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getAuditLog, type AuditEntry } from '../api/settings'
import { LoadFailed, Loading, SettingsShell } from './chrome'
import { sessionAuditFromWrites } from './store'

const TONE: Record<string, 'blue' | 'green' | 'purple' | 'amber' | 'grey' | 'red'> = {
  settings: 'blue', 'sign-off': 'green', 'hand edit': 'purple', 'HPC status': 'grey',
  vocabulary: 'amber', events: 'grey', lock: 'grey', 'batch undo': 'red',
}

export function AuditLogPage() {
  const rd = useSourced(getAuditLog, [])
  const notWired = useNotWired()
  return (
    <SettingsShell slug="audit-log" demo={rd.source === 'demo'} noReset
      actions={<Button icon="upload" testid="export-csv" onClick={() => notWired('GET /api/audit.csv')}>Export CSV</Button>}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the audit log" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getAuditLog>>['data']

function Body({ data }: { data: Data }) {
  const [kind, setKind] = useQueryState('kind', 'all')
  const writes = useDemoWrites('settings')
  const session = sessionAuditFromWrites(writes) as AuditEntry[]
  const all = [...session, ...data.entries]
  const rows = kind === 'all' ? all : all.filter(e => e.kind === kind)

  return (
    <SectionCard title="Entries" testid="entries-card"
      actions={<Seg value={kind} onChange={setKind} options={data.kinds} testid="kind-filter" size="sm" />}
      footer={<span className="s-note">entries record “this installation” — user accounts are future scope · entries cannot be edited or deleted</span>}>
      {rows.length ? (
        <Table rows={rows} rowKey={e => `${e.when}-${e.what.slice(0, 24)}`} testid="audit-table" dense
          columns={[
            { key: 'when', header: 'when', width: '12%', render: e => <span className="mono small">{e.when}</span> },
            { key: 'kind', header: 'kind', width: '11%', render: e => <Badge tone={TONE[e.kind] ?? 'grey'} icon={e.kind === 'lock' ? 'lock' : undefined}>{e.kind}</Badge> },
            { key: 'what', header: 'what', width: '52%', render: e => <span className="small">{e.what}</span> },
            {
              key: 'where', header: 'where', width: '14%', render: e => e.route
                ? <Button variant="link" size="sm" testid={`goto-${e.route.replace(/\//g, '-')}`} onClick={() => navigate(e.route!)}>{e.where}</Button>
                : <span className="muted small">{e.where}</span>,
            },
            { key: 'by', header: 'by', width: '11%', render: e => <span className="muted small">{e.by}</span> },
          ]} />
      ) : (
        <EmptyState size="sm" testid="audit-empty" title={`No ${kind} entries`} caption={`${all.length} entries in the log`}
          action={<Button size="sm" onClick={() => setKind('all')}>Show all</Button>} />
      )}
    </SectionCard>
  )
}
