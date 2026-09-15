/* Upload computed artifact (P4, P24; frames chain-1g → 1i): a stage's cluster result is checked before it is placed —
 * recipe hash, length, finite values, made with this run's parameters. The file itself is not read (demo): the path is
 * validated, the checks run on a simulated timer, and a file whose name says other parameters is refused. */
import { useState } from 'react'
import { Button, Checklist, Field, Modal, ProgressBar, TextField, recordDemoWrite, useSim } from '../../kit'

const CHECKS = ['recipe hash a7f39c2e', 'length 2,595,481 samples', 'values finite', "made with this run's m = 600"]

export function UploadArtifactModal({ stage, onClose, onPlaced }: { stage: string; onClose: () => void; onPlaced: () => void }) {
  const [path, setPath] = useState('./PROFILES/mp_CH4_A2_m600.npy')
  const sim = useSim('analyse.demo.upload-check')
  const problem = !path.trim() ? 'a path to the computed profile' : !/\.npy$/.test(path.trim()) ? 'expects a .npy profile (one float per sample)' : null
  const wrongParams = /m(\d+)/.exec(path)?.[1]
  const refused = sim.status === 'done' && wrongParams && wrongParams !== '600'
  const passed = sim.status === 'done' && !refused
  const items = CHECKS.map((label, i) => ({ label: i === 3 && refused ? `made with m = ${wrongParams} · this run uses m = 600 · refused` : label, state: (sim.status === 'idle' ? 'pending' : sim.status === 'done' ? (i === 3 && refused ? 'fail' : 'pass') : i < Math.floor(sim.fraction * CHECKS.length) ? 'pass' : 'pending') as 'pass' | 'fail' | 'pending' }))
  return (
    <Modal open onClose={() => { sim.reset(); onClose() }} title={`Upload computed artifact · stage ${stage}`} subtitle="checked before it is placed" size="md" testid="upload-modal"
      footer={<>
        <Button onClick={() => { sim.reset(); onClose() }}>Cancel</Button>
        <Button onClick={() => sim.start({ steps: CHECKS, stepMs: 350, queuedMs: 150 })} disabled={!!problem || sim.busy} disabledReason={problem ?? 'checking…'} testid="upload-check">Check file</Button>
        <Button variant="primary" disabled={!passed} disabledReason={refused ? 'a file made with other parameters is refused' : 'run the checks first'} onClick={() => { recordDemoWrite('analyse', 'place-artifact', { stage, path }); sim.reset(); onPlaced() }} testid="upload-place">Place as stage {stage}'s artifact</Button>
      </>}>
      <Field label="computed profile" error={path ? problem ?? undefined : undefined} hint="a path on this machine or a copied cluster_out/ folder">
        <TextField value={path} onChange={v => { setPath(v); sim.reset() }} invalid={!!problem} block testid="upload-path" autoFocus />
      </Field>
      <div style={{ marginTop: 12 }}>
        {sim.busy && <ProgressBar value={sim.fraction} label="checking" />}
        <Checklist items={items} testid="upload-checks" />
      </div>
    </Modal>
  )
}
