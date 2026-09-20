/* Settings › Keyboard & behaviour — personal (frame settings-16 · spec §9.16).
 * The key map with a conflict check, and adjudication behaviour. Verdict and class keys are part of
 * the vocabulary and are set there. */
import { useState } from 'react'
import { Badge, Button, Kbd, SectionCard, Table, Toggle, useQueryState } from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getKeyboard, keyKey, type KeyBinding } from '../api/settings'
import { LoadFailed, Loading, LockedChip, LockedToggle, Row, SettingsShell } from './chrome'
import { PersonalFoot } from './DisplayPage'
import { useSettingsPage } from './store'

export function KeyboardPage() {
  const rd = useSourced(getKeyboard, [])
  return (
    <SettingsShell slug="keyboard" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the key map" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
      <PersonalFoot />
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getKeyboard>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('keyboard')
  const [state, setState] = useQueryState('state', '')
  const [capturing, setCapturing] = useState<string | null>(null)
  const [live, setLive] = useState<{ id: string; key: string; with: string } | null>(null)
  /* derived, not seeded once: ?state=conflict has to land even when only the query changed */
  const conflict = live ?? (state === 'conflict' ? { id: 'reviewed', key: 'E', with: 'open in Explore' } : null)
  const setConflict = (c: { id: string; key: string; with: string } | null) => { setLive(c); if (!c) setState('') }

  const keysOf = (k: KeyBinding): string[] => k.locked ? k.keys : String(s.value(keyKey(k.id)) ?? k.keys.join(' · ')).split(' · ')
  const owner = (key: string, exceptId: string) => data.keys.find(k => k.id !== exceptId && keysOf(k).some(x => x.toUpperCase() === key.toUpperCase()))

  const capture = (k: KeyBinding, e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setCapturing(null); return }
    if (e.key.length !== 1 && !['Enter', 'Backspace', 'Tab'].includes(e.key)) return
    e.preventDefault()
    const pressed = e.key === ' ' ? 'Space' : e.key.length === 1 ? e.key.toUpperCase() : e.key
    const clash = owner(pressed, k.id)
    if (clash) { setConflict({ id: k.id, key: pressed, with: clash.action }); setState('conflict'); setCapturing(null); return }
    s.set(keyKey(k.id), pressed)
    setConflict(null); setState(''); setCapturing(null)
  }

  return (
    <>
      <SectionCard title="Keys" testid="keys-card"
        actions={conflict
          ? <Badge tone="red" testid="conflict-badge">1 conflict</Badge>
          : <Badge tone="green" testid="no-conflicts">no conflicts</Badge>}>
        <Table rows={data.keys} rowKey={k => k.id} testid="keys-table" dense
          rowTone={k => (conflict?.id === k.id ? 'red' : k.locked ? 'dim' : undefined)}
          columns={[
            { key: 'action', header: 'action', width: '32%', render: k => <span className="mono">{k.action}</span> },
            {
              key: 'key', header: 'key', width: '30%', render: k => k.locked
                ? <span style={{ display: 'inline-flex', gap: 4 }}>{k.keys.map((x, i) => <Kbd key={i}>{x}</Kbd>)}</span>
                : capturing === k.id
                  ? <span className="s-keycap capture" tabIndex={0} autoFocus data-testid={`capture-${k.id}`}
                    onKeyDown={e => capture(k, e)} onBlur={() => setCapturing(null)}>press a key…</span>
                  : (
                    <button type="button" style={{ display: 'inline-flex', gap: 4, border: 'none', background: 'none', cursor: 'pointer', padding: 0 }}
                      onClick={() => setCapturing(k.id)} data-testid={`key-${k.id}`} title="click to rebind">
                      {keysOf(k).map((x, i) => <span key={i} className={`s-keycap${conflict?.id === k.id ? ' conflict' : ''}`}>{x}</span>)}
                    </button>
                  ),
            },
            { key: 'where', header: 'where', width: '22%', render: k => <span className="muted small">{k.where}</span> },
            {
              key: 'note', header: '', width: '16%', render: k => k.note
                ? <Button variant="link" size="sm" onClick={() => navigate('settings/vocabulary')} testid={`to-vocab-${k.id}`}>{k.note}</Button>
                : conflict?.id === k.id
                  ? <span className="small" style={{ color: 'var(--red)' }} data-testid="conflict-note">{conflict.key} is already “{conflict.with}”</span>
                  : null,
            },
          ]} />
        {conflict && (
          <div className="s-inline-edit" style={{ background: 'var(--red-100)', borderColor: 'var(--red)' }} data-testid="conflict-row">
            <span className="small"><b>{conflict.key}</b> is bound to “{conflict.with}”. A key does one thing.</span>
            <span className="k-spacer" />
            <Button size="sm" testid="conflict-cancel" onClick={() => { setConflict(null); setState('') }}>Keep the old binding</Button>
            <Button size="sm" variant="danger" testid="conflict-replace"
              onClick={() => {
                const loser = data.keys.find(k => k.action === conflict.with)
                if (loser && !loser.locked) s.set(keyKey(loser.id), '—')
                s.set(keyKey(conflict.id), conflict.key)
                setConflict(null); setState('')
              }}>Move {conflict.key} here</Button>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Adjudication behaviour" testid="behaviour-card">
        {data.behaviour.map(b => (
          <Row key={b.id} label={b.label} testid={`behaviour-${b.id}`} caption={b.caption} dot={s.differs(b.id)}>
            {b.chip
              ? <LockedChip reason={b.caption ?? 'enforced'} testid={`chip-${b.id}`}>{b.chip}</LockedChip>
              : b.locked
                ? <LockedToggle reason={b.caption ?? 'enforced by the tool'} testid={`locked-${b.id}`} />
                : <Toggle checked={s.bool(b.id)} onChange={v => s.set(b.id, v)} testid={`toggle-${b.id}`} />}
          </Row>
        ))}
      </SectionCard>
    </>
  )
}
