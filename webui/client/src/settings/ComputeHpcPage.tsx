/* Settings › Compute & HPC (frame settings-06 · spec §9.6, B19, B26).
 * Where work runs: this machine, the per-workspace local limits, clusters, job profiles with a live
 * script preview, and the by-hand job status policy. Estimates include null draws. */
import { useState } from 'react'
import {
  Badge, Button, Callout, Chip, CodeBlock, EmptyState, InfoTip, Modal, NumberField, ProgressBar,
  SectionCard, Seg, SelectField, Table, TextField, Toggle, useDemoState, useNotWired, useQueryState, useSim,
} from '../kit'
import { useSourced } from '../api/seam'
import { navigate } from '../state'
import { getCompute, slurmScript, type JobProfile } from '../api/settings'
import { LoadFailed, Loading, LockedChip, Row, SettingsShell } from './chrome'
import { useSettingsPage } from './store'

export function ComputeHpcPage() {
  const rd = useSourced(getCompute, [])
  return (
    <SettingsShell slug="compute-hpc" demo={rd.source === 'demo'}>
      {rd.loading && <Loading />}
      {rd.error && <LoadFailed what="the compute settings" error={rd.error} onRetry={rd.reload} />}
      {rd.data && <Body data={rd.data} />}
    </SettingsShell>
  )
}

type Data = Awaited<ReturnType<typeof getCompute>>['data']

function Body({ data }: { data: Data }) {
  const s = useSettingsPage('compute-hpc')
  const notWired = useNotWired()
  const [state, setState] = useQueryState('state', '')
  const [modal, setModal] = useQueryState('modal', '')
  const [cluster, setCluster] = useQueryState('cluster', data.clusters[0].name)
  const [profileName, setProfile] = useQueryState('profile', data.profiles[0].name)
  const [editor, setEditor] = useQueryState('editor', 'guided')
  const [extraClusters, setExtraClusters] = useDemoState<typeof data.clusters>('settings.clusters.extra', () => [])
  const [raw, setRaw] = useState<string | null>(null)
  const bench = useSim('settings.benchmark')

  const clusters = [...data.clusters, ...extraClusters]
  const current = clusters.find(c => c.name === cluster) ?? clusters[0]
  const profiles = current.name === data.clusters[0].name ? data.profiles : []
  const profile = profiles.find(p => p.name === profileName) ?? profiles[0]
  const benchRunning = bench.status === 'queued' || bench.status === 'running' || state === 'benchmark'
  const calibrated = bench.status === 'done' ? '16 Sep 2026' : data.machine.calibrated

  const script = profile ? slurmScript(profile, {
    account: current.account, env: s.str('env_setup'), workdir: s.str('workdir'),
    remote: s.str('return_remote'), email: s.bool('email_on_finish'),
  }) : ''

  return (
    <>
      <SectionCard title="This machine" testid="machine-card"
        actions={<Button icon="refresh" testid="run-benchmark" loading={benchRunning} disabled={benchRunning}
          disabledReason={benchRunning ? 'benchmark running…' : undefined}
          onClick={() => { setState('benchmark'); bench.start({ steps: ['fft', 'matrix profile', 'window matrix', 'image encode', 'cnn forward'], stepMs: 600 }) }}>Run benchmark</Button>}>
        <Row label="detected" caption={`estimates calibrated ${calibrated}`} testid="detected-row">
          <b className="mono">{data.machine.detected}</b>
        </Row>
        {(benchRunning || bench.status === 'running') && bench.status !== 'idle' && (
          <ProgressBar value={bench.fraction} testid="benchmark-progress"
            label={`benchmarking · ${Math.max(1, bench.step + 1)} of ${bench.steps.length || 5} kernels`} />
        )}
        {bench.status === 'done' && <Callout tone="green" icon="check" testid="benchmark-done">Benchmark done (demo) · not wired yet: POST /api/compute/benchmark</Callout>}
        <Row label="local jobs at once" dot={s.differs('local_jobs')} unsaved={s.dirty('local_jobs')} testid="local-jobs-row"
          caption={`local runs share ${data.machine.cores} cores`}>
          <NumberField value={s.num('local_jobs')} min={1} max={data.machine.cores} integer width={100} testid="local-jobs"
            onValid={v => { s.set('local_jobs', v); s.markInvalid('local_jobs', null) }}
            onChange={(_r, reason) => s.markInvalid('local_jobs', reason ? `At most ${data.machine.cores} (detected cores)` : null)} />
        </Row>
      </SectionCard>

      <SectionCard title="Local limits per workspace" subtitle="above a limit the work goes to the cluster" testid="limits-card">
        <Table rows={data.limits} rowKey={l => l.workspace} testid="limits-table" dense
          columns={[
            { key: 'ws', header: 'workspace', width: '14%', render: l => <b>{l.workspace}</b> },
            { key: 'what', header: 'what is estimated', width: '28%', render: l => <span className="small">{l.estimated}</span> },
            {
              key: 'limit', header: 'run locally up to', width: '18%', render: l => {
                const id = `limit.${l.workspace}`
                const max = l.unit === 'h' ? 48 : l.workspace === 'Review' ? 60 : l.workspace === 'Library' ? 120 : 240
                const min = l.unit === 'h' ? 0.5 : 1
                return (
                  <span className={s.dirty(id) ? 'unsaved' : undefined} style={{ display: 'inline-flex' }} id={l.workspace === 'Analyse' ? 'f-run-locally-up-to' : undefined}>
                    <NumberField value={s.num(id)} min={min} max={max} step={l.unit === 'h' ? 0.5 : 1} integer={l.unit === 'min'} unit={l.unit} width={120} testid={`limit-${l.workspace}`}
                      onValid={v => { s.set(id, v); s.markInvalid(id, null) }}
                      onChange={(_r, reason) => s.markInvalid(id, reason ? `Enter ${min}–${max} ${l.unit}` : null)} />
                  </span>
                )
              },
            },
            { key: 'above', header: 'above the limit', width: '40%', render: l => <span className="muted small">{l.above}</span> },
          ]} />
      </SectionCard>

      <SectionCard title="Clusters" testid="clusters-card"
        actions={<Button icon="plus" testid="add-cluster" onClick={() => setModal('add-cluster')}>Add cluster</Button>}>
        <Table rows={clusters} rowKey={c => c.name} testid="clusters-table" dense highlighted={current.name} onRowClick={c => setCluster(c.name)}
          columns={[
            { key: 'name', header: 'name', width: '18%', render: c => <span className="mono" style={{ fontWeight: 600 }}>● {c.name}</span> },
            { key: 'host', header: 'login host', width: '28%', render: c => <span className="mono small">{c.login_host}</span> },
            { key: 'scheduler', header: 'scheduler', width: '14%' },
            { key: 'account', header: 'account', width: '16%', render: c => <span className="mono small">{c.account}</span> },
            { key: 'status', header: '', width: '24%', render: c => <Badge tone={c.status.startsWith('in use') ? 'green' : 'grey'}>{c.status}</Badge> },
          ]} />
        <Callout tone="amber" outlined icon={null} testid="second-cluster-note">
          A second cluster? Add it here if you submit to more than one — each cluster keeps its own profiles and return path.
          <InfoTip title="B19">Confirm which clusters you actually submit to.</InfoTip>
        </Callout>
      </SectionCard>

      <SectionCard title={`Job profiles · ${current.name}`} subtitle="which profile each kind of job uses" testid="profiles-card">
        {profiles.length ? (
          <>
            <Table rows={profiles} rowKey={p => p.name} testid="profiles-table" dense highlighted={profile?.name} onRowClick={p => setProfile(p.name)}
              columns={[
                { key: 'profile', header: 'profile', width: '15%', render: p => <span className="mono" style={{ fontWeight: 600 }}>{p.name}</span> },
                { key: 'partition', header: 'partition', width: '11%', render: p => <span className="mono small">{p.partition}</span> },
                { key: 'nodes', header: 'nodes', width: '7%', render: p => p.nodes },
                { key: 'gres', header: 'gres', width: '13%', render: p => <span className="mono small">{p.gres}</span> },
                { key: 'cpus', header: 'cpus', width: '7%', render: p => p.cpus },
                { key: 'memory', header: 'memory', width: '9%', render: p => p.memory },
                { key: 'time', header: 'time', width: '11%', render: p => <span className="mono small">{p.time}</span> },
                { key: 'array', header: 'array', width: '7%', render: p => p.array },
                {
                  key: 'used', header: 'used for', width: '20%', render: p => p.flag
                    ? <Chip tone="amber" testid={`flag-${p.name}`}>{p.flag}<InfoTip title="B19">Two nodes only help if the job is written for it — check before using.</InfoTip></Chip>
                    : <span className="muted small">{p.used_for}</span>,
                },
              ]} />
            {profile && <ProfileEditor profile={profile} store={s} editor={editor} setEditor={setEditor} raw={raw} setRaw={setRaw} script={script} />}
          </>
        ) : <EmptyState size="sm" title={`No profiles on ${current.name}`} caption="add one before submitting"
          action={<Button size="sm" onClick={() => notWired(`POST /api/clusters/${current.name}/profiles`)}>Add profile</Button>} testid="profiles-empty" />}
      </SectionCard>

      <SectionCard title="Job status" testid="job-status-card">
        <Row label="cluster job status" caption="the site cannot see the queue · the researcher marks submitted, running, finished" testid="marked-by-hand-row">
          <LockedChip reason="the site cannot see the cluster queue; job status is marked by hand in Jobs" testid="marked-by-hand">marked by hand</LockedChip>
          <Button variant="link" size="sm" icon="external" onClick={() => navigate('jobs')}>Jobs</Button>
        </Row>
        <Row label="remind to check a running job after" dot={s.differs('remind_x')} unsaved={s.dirty('remind_x')} testid="remind-row"
          caption="j-0214 is 3.3× its estimate">
          <NumberField value={s.num('remind_x')} min={1} max={20} width={90} onValid={v => s.set('remind_x', v)} testid="remind-x" />
          <span className="mono small">× estimate</span>
        </Row>
        <Row label="watch the manifest inbox every" dot={s.differs('watch_min')} unsaved={s.dirty('watch_min')} testid="watch-row"
          caption={<>results land in <button type="button" className="k-link" onClick={() => navigate('jobs')}>Jobs › Manifest inbox</button></>}>
          <NumberField value={s.num('watch_min')} min={1} max={60} integer unit="min" width={110} onValid={v => s.set('watch_min', v)} testid="watch-min" />
        </Row>
      </SectionCard>

      <AddCluster open={modal === 'add-cluster'} onClose={() => setModal('')} taken={clusters.map(c => c.name)}
        onAdd={c => { setExtraClusters(x => [...x, c]); setCluster(c.name); setModal('') }} />
    </>
  )
}

function ProfileEditor({ profile, store: s, editor, setEditor, raw, setRaw, script }: {
  profile: JobProfile; store: ReturnType<typeof useSettingsPage>; editor: string; setEditor: (v: string) => void
  raw: string | null; setRaw: (v: string | null) => void; script: string
}) {
  const notWired = useNotWired()
  const workdirError = /^(\/|\$)/.test(s.str('workdir')) ? null : 'Use an absolute path on the cluster'
  return (
    <div style={{ borderTop: '1px solid var(--border)', marginTop: 12, paddingTop: 12 }} data-testid="profile-editor">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <b className="mono">{profile.name}</b>
        <Seg value={editor} onChange={v => { if (v === 'guided' && raw !== null) setRaw(null); setEditor(v) }} testid="editor-seg"
          options={[{ value: 'guided', label: 'guided' }, { value: 'raw', label: 'raw template' }]} />
        <span className="s-note">guided keeps the script valid</span>
      </div>
      {editor === 'guided' ? (
        <>
          <Row label="environment setup" dot={s.differs('env_setup')} unsaved={s.dirty('env_setup')} testid="env-row" caption="runs before the job">
            <TextField value={s.str('env_setup')} onChange={v => s.set('env_setup', v)} width={340} testid="env-setup" />
          </Row>
          <Row label="working directory" dot={s.differs('workdir')} unsaved={s.dirty('workdir')} testid="workdir-row" caption={workdirError ?? 'cd here before running'}>
            <TextField value={s.str('workdir')} onChange={v => { s.set('workdir', v); s.markInvalid('workdir', /^(\/|\$)/.test(v) ? null : 'Use an absolute path on the cluster') }}
              width={260} invalid={!!workdirError} testid="workdir" />
          </Row>
          <Row label="results come back from" dot={s.differs('return_remote')} unsaved={s.dirty('return_remote') || s.dirty('return_local')} testid="return-row"
            caption="copied into Jobs › Manifest inbox · path in Storage">
            <TextField value={s.str('return_remote')} onChange={v => s.set('return_remote', v)} width={220} testid="return-remote" />
            <span className="mono small">→</span>
            <TextField value={s.str('return_local')} onChange={v => s.set('return_local', v)} width={150} testid="return-local" />
          </Row>
          <Row label="email on finish" dot={s.differs('email_on_finish')} unsaved={s.dirty('email_on_finish')} testid="email-row"
            caption="adds #SBATCH --mail-type=END">
            <Toggle checked={s.bool('email_on_finish')} onChange={v => s.set('email_on_finish', v)} testid="email-on-finish" />
          </Row>
        </>
      ) : (
        <>
          <Callout tone="amber" testid="raw-warning">raw templates are not validated · {'{{recipe}}'} and {'{{job}}'} are filled in when a script is created</Callout>
          <TextField value={raw ?? script} onChange={setRaw} multiline rows={8} block testid="raw-template" />
        </>
      )}
      <div style={{ marginTop: 10 }}>
        <CodeBlock code={raw ?? script} title="script preview" filename={`slurm_${profile.name}.sh`} testid="script-preview"
          onSave={() => notWired(`download slurm_${profile.name}.sh`)} />
      </div>
    </div>
  )
}

function AddCluster({ open, onClose, taken, onAdd }: {
  open: boolean; onClose: () => void; taken: string[]
  onAdd: (c: { name: string; login_host: string; scheduler: string; account: string; status: string }) => void
}) {
  const [name, setName] = useState('')
  const [host, setHost] = useState('')
  const [account, setAccount] = useState('')
  const err = !/^[a-z0-9-]{2,20}$/.test(name) ? 'lowercase letters, digits and dashes, 2–20'
    : taken.includes(name) ? `${name} already exists`
      : !/^[a-z0-9.-]+\.[a-z]{2,}$/.test(host) ? 'Enter a host name like login.cluster.example'
        : !account ? 'an account is required' : null
  return (
    <Modal open={open} onClose={onClose} title="Add cluster" size="md" testid="add-cluster-modal"
      footerNote="each cluster keeps its own profiles and return path"
      footer={<>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" disabled={!!err} disabledReason={err ?? undefined} testid="add-cluster-confirm"
          onClick={() => onAdd({ name, login_host: host, scheduler: 'SLURM', account, status: '0 profiles' })}>Add</Button>
      </>}>
      <div className="s-grid c2">
        <div className="s-gf"><span className="s-label mono">name</span><TextField value={name} onChange={v => setName(v.toLowerCase())} block testid="cluster-name" placeholder="hpc-2" /></div>
        <div className="s-gf"><span className="s-label mono">login host</span><TextField value={host} onChange={setHost} block testid="cluster-host" placeholder="login.cluster.example" /></div>
        <div className="s-gf"><span className="s-label mono">scheduler</span>
          <SelectField value="SLURM" onChange={() => undefined} width="100%" testid="cluster-scheduler"
            options={[{ value: 'SLURM', label: 'SLURM' }, { value: 'PBS', label: 'PBS', disabled: true, reason: 'not supported yet' }, { value: 'LSF', label: 'LSF', disabled: true, reason: 'not supported yet' }]} />
        </div>
        <div className="s-gf"><span className="s-label mono">account</span><TextField value={account} onChange={setAccount} block testid="cluster-account" placeholder="a_myco" /></div>
      </div>
      {err && <div className="small" style={{ color: 'var(--red)', marginTop: 8 }} data-testid="add-cluster-error">{err}</div>}
    </Modal>
  )
}
