/* Stops 2 and 3 · Analyse and Build: the chain on the marked stretch, one row per step, each step's output beside
   it. Stop 2 shows the thesis drop detector at its own settings; stop 3 opens the menu (Q6 = A): three slots,
   notched knobs, and every combination answers at once because every one was computed in advance. */
import { useEffect, useMemo, type ReactNode } from 'react'
import { Icicles, Trace, type Box } from '../charts'
import { api, comboLabel, fmtDur, fmtH, fmtKnob, fmtNum, go, useAsync, useDemo } from '../store'
import type { Combo, Manifest } from '../api'
import { tourSignal } from '../tour'

const LETTER: Record<string, [string, string]> = {
  '0': ['#e5484d', 'fast down'], '1': ['#f5a35c', 'down'], '2': ['#e5e7eb', 'flat'], '3': ['#9cc7ff', 'up'], '4': ['#0a84ff', 'fast up'],
  '-1': ['#ffffff', 'gap'],
}

export function findCombo(m: Manifest, p: Partial<Combo> & { knobs?: Record<string, number> }, from: Combo): Combo {
  const want = { ...from, ...p, knobs: { ...(p.detector && p.detector !== from.detector ? {} : from.knobs), ...(p.knobs || {}) } }
  const det = m.menu.detectors.find(d => d.key === want.detector)!
  const knobs: Record<string, number> = {}
  for (const [k, kn] of Object.entries(det.knobs)) knobs[k] = want.knobs[k] ?? kn.default
  const hit = m.combos.find(c => c.detector === want.detector && c.look_for === want.look_for &&
    Math.abs(c.window_s - want.window_s) < 1e-6 && Object.entries(knobs).every(([k, v]) => Math.abs((c.knobs[k] ?? NaN) - v) < 1e-6))
  return hit ?? from
}

export function AnalysePage({ build }: { build: boolean }) {
  const { m, thread, set, slice } = useDemo()
  const s = slice(thread.slice)
  const combo = m.combos.find(c => c.id === thread.combo) ?? m.combos[0]
  const det = m.menu.detectors.find(d => d.key === combo.detector)!
  // the stretch: the marked one, else the Explore window
  const [a, b] = thread.span ?? thread.view
  const chain = useAsync(() => api.chain(combo.id, s.id), [combo.id, s.id])
  const evs = useMemo(() => (chain.data?.events ?? []).filter(e => e.e > a && e.s < b), [chain.data, a, b])
  const boxes: Box[] = evs.map(e => ({ s: e.s, e: e.e, tone: 'mine', alpha: 0.9, mark: e.extremum_idx ?? null }))
  const change = (p: Partial<Combo> & { knobs?: Record<string, number> }) => {
    const c = findCombo(m, p, combo)
    if (c.id !== combo.id) { set({ combo: c.id }); tourSignal('knob') }
  }
  useEffect(() => { if (!build) return; tourSignal('build') }, [build])
  const ds = m.datasets.find(d => d.key === s.dataset)!
  const icicles = useMemo(() => evs.slice(0, 40).map(e => ({ s: e.onset_idx ?? e.s, e: e.recovery_idx ?? e.e, depth: Math.abs(e.event_amplitude_mv ?? 0) })), [evs])

  return (
    <div className="page-body analyse">
      <div className="toolbar">
        <span className="src-chip" data-testid="analyse-source"><b>{ds.name}</b> · {s.label} · {fmtH(a, s.fs)}–{fmtH(b, s.fs)} ({fmtDur((b - a) / s.fs)})</span>
        <button className="link" onClick={() => go('explore')}>change</button>
        <span className="grow" />
        {!build && <button className="btn" data-testid="to-build" onClick={() => go('build')}>Change the settings</button>}
      </div>

      <div className="chain">
        <Step n="01" title="The recording" sub="as it was measured">
          <Trace sid={s.id} fs={s.fs} a={a} b={b} height={130} />
        </Step>

        <Step n="02" title="Clean" sub={`remove the slow drift · look for ${combo.look_for}`} tour="step-clean"
          controls={build && <>
            <Notches label="Drift window" unit="min" values={m.menu.clean_windows_s.map(v => v / 60)} value={combo.window_s / 60}
              onChange={v => change({ window_s: m.menu.clean_windows_s.find(w => Math.abs(w / 60 - v) < 1e-6)! })} />
            <div className="seg small">{m.menu.look_for.map(l => <button key={l.key} className={combo.look_for === l.key ? 'on' : ''}
              onClick={() => change({ look_for: l.key as Combo['look_for'] })}>{l.label}</button>)}</div>
          </>}>
          <Trace sid={s.id} fs={s.fs} a={a} b={b} height={130} combo={combo.id} color="#1d6fd9" />
        </Step>

        <Step n="03" title="Find events" sub={det.label} tour="step-find"
          controls={build && <>
            <div className="seg small" data-tour="detectors">{m.menu.detectors.map(d => <button key={d.key} className={combo.detector === d.key ? 'on' : ''}
              onClick={() => change({ detector: d.key })} data-testid={`det-${d.key}`}>{d.label}</button>)}</div>
            <p className="hint">{det.blurb}</p>
            {Object.entries(det.knobs).map(([k, kn]) => <Notches key={k} label={kn.label} unit={kn.unit} values={kn.values} value={combo.knobs[k]}
              onChange={v => change({ knobs: { [k]: v } })} testid={`knob-${k}`} />)}
          </>}>
          {chain.data?.letters && <Letters letters={chain.data.letters} a={a} b={b} />}
          <Trace sid={s.id} fs={s.fs} a={a} b={b} height={150} combo={combo.id} boxes={boxes} color="#1d6fd9" testid="find-trace" />
          <div className="stat-line" data-testid="events-in-span">
            {chain.loading ? 'finding…' : <><b>{evs.length}</b> events in this stretch · <b>{chain.data?.n ?? 0}</b> in 24 h on {s.label}</>}
          </div>
        </Step>

        <Step n="04" title="Describe" sub="each event's shape, and the gaps between them">
          <MiniIcicles sid={s.id} fs={s.fs} rows={icicles} />
          <div className="kv">
            <span>median depth <b>{fmtNum(median(evs.map(e => Math.abs(e.event_amplitude_mv ?? NaN))))} mV</b></span>
            <span>median width <b>{fmtNum(median(evs.map(e => e.event_width_s ?? NaN)))} s</b></span>
            <span>median gap <b>{fmtNum(median(evs.map(e => e.interval_after_s ?? NaN)) / 60)} min</b></span>
          </div>
        </Step>
      </div>

      <div className="cta-bar">
        <span className="muted">Your detector: <b className="text">{comboLabel(m, combo.id)}</b></span>
        <span className="grow" />
        <button className="btn primary big" data-tour="run-btn" data-testid="run-btn"
          onClick={() => { set({ ran: combo.id }); tourSignal('run'); go('discovery') }}>Run it on all 12 channels</button>
      </div>
    </div>
  )
}

function median(v: number[]): number {
  const w = v.filter(Number.isFinite).sort((x, y) => x - y)
  return w.length ? w[Math.floor(w.length / 2)] : NaN
}

function Step({ n, title, sub, controls, children, tour }: { n: string; title: string; sub: string; controls?: ReactNode; children: ReactNode; tour?: string }) {
  return (
    <div className="step card" data-tour={tour}>
      <div className="step-head">
        <span className="step-n">{n}</span>
        <div><div className="step-title">{title}</div><div className="step-sub">{sub}</div></div>
      </div>
      {controls && <div className="step-controls">{controls}</div>}
      <div className="step-out">{children}</div>
    </div>
  )
}

export function Notches({ label, unit, values, value, onChange, testid }: { label: string; unit: string; values: number[]; value: number; onChange: (v: number) => void; testid?: string }) {
  const i = Math.max(0, values.findIndex(v => Math.abs(v - value) < 1e-6))
  return (
    <div className="notches" data-testid={testid} data-tour={testid}>
      <div className="notch-label">{label}</div>
      <div className="notch-row">
        {values.map((v, k) => <button key={k} className={k === i ? 'on' : ''} onClick={() => onChange(v)}>{fmtKnob(v)}{unit === 'σ' ? 'σ' : ` ${unit}`}</button>)}
      </div>
    </div>
  )
}

function Letters({ letters, a, b }: { letters: { seg: number; letters: string[] }; a: number; b: number }) {
  const i0 = Math.max(0, Math.floor(a / letters.seg)), i1 = Math.min(letters.letters.length, Math.ceil(b / letters.seg))
  const raw = letters.letters.slice(i0, i1)
  // a 24 h view of 5 s letters is 17,000 cells: draw at most ~600, each group showing its most telling letter
  // (a fast fall first, then a fall, a fast rise, a rise, flat), so no drop disappears from the strip
  const per = Math.max(1, Math.ceil(raw.length / 600))
  const rank: Record<string, number> = { '0': 0, '1': 1, '4': 2, '3': 3, '2': 4, '-1': 5 }
  const cells: { l: string; n: number }[] = []
  for (let k = 0; k < raw.length; k += per) {
    const grp = raw.slice(k, k + per)
    cells.push({ l: grp.reduce((m, x) => (rank[x] ?? 9) < (rank[m] ?? 9) ? x : m, grp[0]), n: grp.length })
  }
  const many = cells.length > 400
  return (
    <div className="letters" title="each segment of the cleaned trace as a letter: red = falling fast, orange = falling, grey = flat, blue = rising">
      {cells.map((c, k) => {
        const [col, name] = LETTER[c.l] ?? ['#fff', c.l]
        return <i key={k} style={{ flexGrow: c.n, background: col, borderRight: many ? 'none' : undefined }} title={name} />
      })}
    </div>
  )
}

function MiniIcicles({ sid, fs, rows }: { sid: number; fs: number; rows: { s: number; e: number; depth: number }[] }) {
  const ok = rows.filter(r => r.e > r.s)
  const env = useAsync(async () => {
    const pres = ok.map(r => Math.max(1, Math.round((r.e - r.s) / 6)))
    const envs = ok.length ? await api.snippets(sid, ok.map((r, k) => [Math.max(0, r.s - pres[k]), r.e] as [number, number])) : []
    return envs.map((e, k) => ({ e, pre: pres[k], depth: ok[k].depth }))
  }, [sid, ok.map(r => `${r.s}-${r.e}`).join(',')])
  // each result carries its own depth: while a new detector's events load, the previous list is still shown
  const data = (env.data ?? []).map(({ e, pre, depth }) => {
    const mid = e.lo.map((lo, i) => (lo + e.hi[i]) / 2)
    const base = mid[Math.min(mid.length - 1, Math.round(pre / e.step))] ?? 0
    return { dt: e.step / fs, t0: -pre / fs, v: mid.map(z => z - base), depth }
  })
  if (!ok.length) return <div className="empty-chart" style={{ height: 150 }}>no events in this stretch</div>
  return <Icicles rows={data} height={150} />
}
