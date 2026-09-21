/* Settings › About (frame settings-14 · spec §9.14) — LIVE (Prompt 02): GET /api/about.
 * What this installation is running (code version and whether the tree is clean, schema, blocks, python and
 * packages, the mode and the database it is open on), and the future-scope list kept so it is not designed out. */
import { Badge, Button, Chip, CodeBlock, Modal, SectionCard, copyToClipboard, useQueryState } from '../kit'
import { useToast } from '../shell/Toast'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getAbout } from '../api/settings'
import { LoadFailed, Loading, Row, SettingsShell } from './chrome'

export function AboutPage() {
  const rd = useSourced(getAbout, [])
  const { push } = useToast()
  return (
    <SettingsShell slug="about" demo={rd.source === 'demo'} noReset
      actions={<Button icon="copy" testid="copy-diagnostics"
        onClick={() => copyToClipboard(rd.data?.diagnostics ?? '').then(ok => push({ text: ok ? 'Diagnostics copied' : 'Could not reach the clipboard', kind: ok ? 'info' : 'error' }))}>Copy diagnostics</Button>}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the installation details" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getAbout>>['data']

function Body({ data }: { data: Data }) {
  const [modal, setModal] = useQueryState('modal', '')
  const a = data.about
  return (
    <>
      <SectionCard title="Versions" testid="versions-card">
        <Row label="code" testid="code-row" wide>
          <b className="mono">{a.code}</b>
          {a.matches_export
            ? <Badge tone="green" testid="matches-export">clean working tree</Badge>
            : <Badge tone="amber" testid="mismatch-export">uncommitted changes — an export made now cannot be traced to a commit</Badge>}
        </Row>
        <Row label="database schema" testid="schema-row" wide><span className="mono small">{a.schema}</span></Row>
        <Row label="analysis blocks" testid="blocks-row" wide>
          <span className="mono">{a.blocks}</span>
          {a.broken.length > 0 && <span className="small muted">broken: {a.broken.join(', ')}</span>}
          <Button variant="link" size="sm" iconRight="arrow-right" onClick={() => navigate('settings/blocks')} testid="to-blocks">Blocks</Button>
        </Row>
        <Row label="environment" testid="env-row" wide>
          <span className="mono small">{a.environment}</span>
          <Button variant="link" size="sm" onClick={() => setModal('lock')} testid="show-lock-file">Show packages</Button>
        </Row>
      </SectionCard>

      <SectionCard title="This installation" testid="installation-card">
        <Row label="project" testid="project-row" wide><span className="mono">{a.project}</span></Row>
        <Row label="mode" testid="mode-row" wide>
          <Badge tone={a.mode === 'project' ? 'green' : 'amber'} testid="mode-badge">{a.mode}</Badge>
          <span className="small muted">{a.mode === 'project' ? `the real database, backed up first to ${a.db_backup ?? '?'}` : 'a throwaway copy of the database; nothing here reaches the project'}</span>
        </Row>
        <Row label="database" testid="db-row" wide><span className="mono small">{a.db_path}</span></Row>
        <Row label="settings" testid="settings-file-row" wide caption="project settings travel with the database backup">
          <span className="mono small">{a.settings_file}</span>
        </Row>
      </SectionCard>

      <SectionCard title="Future scope" subtitle="not built, recorded so it is not designed out" testid="future-card">
        {a.future.map(f => (
          <div key={f.name} className="s-row wide" data-testid={`future-${f.name.replace(/\s/g, '-')}`}>
            <span><Chip tone="grey" size="sm">future</Chip> <b className="mono">{f.name}</b></span>
            <span className="s-note">{f.detail}</span>
            <span />
          </div>
        ))}
      </SectionCard>

      <Modal open={modal === 'lock'} onClose={() => setModal('')} title="packages" size="md" testid="lock-file-modal"
        footerNote="what the bridge imported at start · a reproducibility bundle carries the conda environment lock">
        <CodeBlock code={a.lock_file} filename="environment" lineNumbers testid="lock-file" save={false} />
      </Modal>
    </>
  )
}
