/* Settings › Audit log (frame settings-13 · spec §9.13) — LIVE (Prompt 02).
 * Append-only, read from the audit_log table (GET /api/audit): every act that changes what a result means,
 * in order. Entries cannot be edited or deleted — the table has no update or delete anywhere in the code. */
import { Badge, Button, EmptyState, SectionCard, Seg, Table, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { auditCsvUrl } from '../api'
import { getAuditLog } from '../api/settings'
import { LoadFailed, Loading, SettingsShell } from './chrome'

const TONE: Record<string, 'blue' | 'green' | 'purple' | 'amber' | 'grey' | 'red'> = {
  settings: 'blue', 'sign-off': 'green', 'hand edit': 'purple', 'HPC status': 'grey', registration: 'green',
  vocabulary: 'amber', events: 'grey', lock: 'grey', 'batch undo': 'red',
}

export function AuditLogPage() {
  const [kind, setKind] = useQueryState('kind', 'all')
  const rd = useSourced(() => getAuditLog(kind), [kind])
  return (
    <SettingsShell slug="audit-log" demo={rd.source === 'demo'} noReset
      actions={<Button icon="upload" testid="export-csv" onClick={() => { window.location.href = auditCsvUrl(kind) }}>Export CSV</Button>}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the audit log" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} kind={kind} setKind={setKind} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getAuditLog>>['data']

function Body({ data, kind, setKind }: { data: Data; kind: string; setKind: (k: string) => void }) {
  const rows = data.entries
  return (
    <SectionCard title="Entries" subtitle={`${rows.length} shown · ${data.mode === 'sandbox' ? 'the sandbox copy of the log' : 'the project log'}`} testid="entries-card"
      actions={<Seg value={kind} onChange={setKind} options={data.kinds} testid="kind-filter" size="sm" />}
      footer={<span className="s-note">entries record “this installation” — user accounts are future scope · entries cannot be edited or deleted</span>}>
      {rows.length ? (
        <Table rows={rows} rowKey={e => String(e.id)} testid="audit-table" dense
          columns={[
            { key: 'when', header: 'when', width: '12%', render: e => <span className="mono small" title={e.iso}>{e.when}</span> },
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
        <EmptyState size="sm" testid="audit-empty" title={kind === 'all' ? 'The log is empty' : `No ${kind} entries`}
          caption={kind === 'all' ? 'a save on any project page, a registration or the held-out lock writes the first entry' : 'other kinds have entries'}
          action={kind !== 'all' ? <Button size="sm" onClick={() => setKind('all')}>Show all</Button> : undefined} />
      )}
    </SectionCard>
  )
}
