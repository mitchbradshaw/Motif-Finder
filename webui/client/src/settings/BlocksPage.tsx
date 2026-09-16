/* Settings › Blocks (frame settings-07 · spec §9.7, B13, B24).
 * The registry read from Adapters/ at start. A disabled block leaves the insert modal; runs and
 * templates that used it stay readable. */
import { useRef } from 'react'
import { Badge, Button, InfoTip, Popover, SectionCard, Table, Toggle, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { blockKey, getBlocks, type BlockRow } from '../api/settings'
import { LoadFailed, Loading, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function BlocksPage() {
  const rd = useSourced(getBlocks, [])
  return (
    <SettingsShell slug="blocks" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the block registry" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getBlocks>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('blocks')
  const built = data.blocks.filter(b => b.built).length
  return (
    <SectionCard title="Registered blocks" subtitle={`${built} registered · ${data.blocks.length - built} not built`} testid="blocks-card"
      footer={<span className="s-note">a disabled block is hidden from the insert modal; runs and templates that used it stay readable</span>}>
      <Table rows={data.blocks} rowKey={b => b.id} testid="blocks-table" dense
        rowTone={b => (!b.built ? 'dim' : s.dirty(blockKey(b.id)) ? 'amber' : undefined)}
        columns={[
          { key: 'block', header: 'block', width: '15%', render: b => <b style={{ color: b.built ? undefined : 'var(--muted)' }}>{b.name}</b> },
          {
            key: 'signature', header: 'signature', width: '18%', render: b => (
              <span className="mono small">{b.signature}<InfoTip title="§6.8 contract types">{data.signatureTypes}</InfoTip></span>
            ),
          },
          { key: 'version', header: 'version', width: '8%', render: b => b.version ?? <span className="muted">—</span> },
          {
            key: 'adapter', header: 'adapter', width: '17%', render: b => b.adapter
              ? <span className="mono small muted" title="webui cannot open files">{b.adapter}</span>
              : <Badge tone="amber" testid="not-built">not built · B13</Badge>,
          },
          { key: 'null', header: 'null', width: '13%', render: b => <span className="small muted">{b.null_kind}</span> },
          { key: 'usedby', header: 'used by', width: '14%', render: b => <UsedBy block={b} /> },
          {
            key: 'on', header: 'on', width: '9%', render: b => (
              <span className={s.dirty(blockKey(b.id)) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }}>
                <Toggle checked={s.bool(blockKey(b.id))} onChange={v => s.set(blockKey(b.id), v)} testid={`block-${b.id}`}
                  disabled={!b.built} disabledReason={!b.built ? 'not built · B13 — the block has no adapter yet' : undefined}
                  ariaLabel={`${b.name} enabled`} />
              </span>
            ),
          },
        ]} />
    </SectionCard>
  )
}

function UsedBy({ block }: { block: BlockRow }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [usedby, setUsedby] = useQueryState('usedby', '')
  const open = usedby === block.id
  if (!block.templates.length) return <span className="muted small">0 templates</span>
  return (
    <>
      <Button ref={ref} variant="link" size="sm" testid={`usedby-${block.id}`} onClick={() => setUsedby(usedby === block.id ? '' : block.id)}>
        {block.templates.length} template{block.templates.length === 1 ? '' : 's'}
      </Button>
      <Popover open={open} onClose={() => setUsedby('')} anchorRef={ref} title={`${block.name} · used by`} width={300} testid="usedby-popover">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {block.templates.map(t => (
            <button key={t} type="button" className="s-hit mono" onClick={() => navigate(`library/templates?template=${t}`)}>{t}</button>
          ))}
        </div>
        <Button variant="link" size="sm" icon="external" style={{ marginTop: 6 }} onClick={() => navigate('library/templates')}>Open in Library ›</Button>
      </Popover>
    </>
  )
}
