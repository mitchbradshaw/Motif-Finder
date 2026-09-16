/* Settings › About (frame settings-14 · spec §9.14).
 * What this installation is running, and the future-scope list kept so it is not designed out. */
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
  const [state] = useQueryState('state', '')
  const [modal, setModal] = useQueryState('modal', '')
  const matches = data.about.matches_export && state !== 'mismatch'
  return (
    <>
      <SectionCard title="Versions" testid="versions-card">
        <Row label="code" testid="code-row" wide>
          <b className="mono">{data.about.code}</b>
          {matches
            ? <Badge tone="green" testid="matches-export">matches last export</Badge>
            : <Badge tone="amber" testid="mismatch-export">the last export was made on 9f21b04 — re-export to match</Badge>}
        </Row>
        <Row label="database schema" testid="schema-row" wide><span className="mono">{data.about.schema}</span></Row>
        <Row label="analysis blocks" testid="blocks-row" wide>
          <span className="mono">{data.about.blocks}</span>
          <Button variant="link" size="sm" iconRight="arrow-right" onClick={() => navigate('settings/blocks')} testid="to-blocks">Blocks</Button>
        </Row>
        <Row label="environment" testid="env-row" wide>
          <span className="mono">{data.about.environment}</span>
          <Button variant="link" size="sm" onClick={() => setModal('lock')} testid="show-lock-file">Show lock file</Button>
        </Row>
      </SectionCard>

      <SectionCard title="This installation" testid="installation-card">
        <Row label="project" testid="project-row" wide><span className="mono">{data.about.project}</span></Row>
        <Row label="settings file" testid="settings-file-row" wide caption="project settings travel with the database backup">
          <span className="mono">{data.about.settings_file}</span>
        </Row>
      </SectionCard>

      <SectionCard title="Future scope" subtitle="not built, recorded so it is not designed out" testid="future-card">
        {data.about.future.map(f => (
          <div key={f.name} className="s-row wide" data-testid={`future-${f.name.replace(/\s/g, '-')}`}>
            <span><Chip tone="grey" size="sm">future</Chip> <b className="mono">{f.name}</b></span>
            <span className="s-note">{f.detail}</span>
            <span />
          </div>
        ))}
      </SectionCard>

      <Modal open={modal === 'lock'} onClose={() => setModal('')} title="environment.lock" size="md" testid="lock-file-modal"
        footerNote="the lock file travels in every reproducibility bundle">
        <CodeBlock code={data.about.lock_file} filename="environment.lock" lineNumbers testid="lock-file" save={false} />
      </Modal>
    </>
  )
}
