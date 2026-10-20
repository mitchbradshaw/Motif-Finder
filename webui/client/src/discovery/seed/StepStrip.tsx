/* seed-search (2026-10-18): the Seed page as four steps walked in order — the researcher's own words: "select exemplar →
 * run preview → use preview detections as detections on their own, or run with surrogates and use detections". The
 * strip across the top says where the researcher is and lets them go back; only the open step's card is drawn. */
import type { ReactNode } from 'react'
import { InfoTip, Stepper, type StepState } from '../../kit'

export type SeedStep = 1 | 2 | 3 | 4

/** The four steps' names, in the researcher's words. */
export const SEED_STEPS: Record<SeedStep, string> = {
  1: 'Pick the exemplar',
  2: 'Run the preview',
  3: 'Choose the cut',
  4: 'Keep the matches',
}

export interface StepStatus {
  /** the line under the step's name: what it holds now (the seed, the preview, the cut, the kept run) */
  detail: ReactNode
  /** reached: everything it needs is in hand (a seed for 2, a preview for 3 and 4) */
  open: boolean
  /** finished: the step's own work is done */
  done: boolean
  /** why it cannot be opened yet, in words */
  blocked?: string
}

/** Which step a page opens on. The exemplar unless a preview of this query is in hand — while one is being chosen,
 *  when there is none, and when the remembered seed has no preview yet (the researcher, 2026-10-20: "don't jump to
 *  step 2 by default"; picking a seed still walks on to step 2, and `?step=` still opens any step that can open);
 *  with a preview in hand, the keep when this search is already kept, else the cut. */
export function openingStep(o: { kept: boolean; previewIn: boolean; hasSeed: boolean; choosing: boolean }): SeedStep {
  if (o.choosing || !o.hasSeed || !o.previewIn) return 1
  return o.kept ? 4 : 3
}

export function StepStrip({ current, status, onStep }: { current: SeedStep; status: Record<SeedStep, StepStatus>; onStep: (s: SeedStep) => void }) {
  const steps = ([1, 2, 3, 4] as SeedStep[]).map(n => {
    const st = status[n]
    const state: StepState = n === current ? 'current' : st.done ? 'done' : 'todo'
    return {
      id: `step-${n}`, state,
      label: <span data-testid={`seed-step-${n}`} data-open={st.open ? '1' : '0'} title={st.open ? undefined : st.blocked}>{SEED_STEPS[n]}</span>,
      // site-changes (2026-10-20): a step that cannot open yet says nothing under its name ("run the preview first" beside
      // steps 3 and 4 read as an instruction); why it is closed is on the name's hover
      detail: <span className="dsc-step-detail">{st.open ? st.detail : null}</span>,
    }
  })
  return (
    <div className="k-card dsc-seed-steps" data-testid="seed-steps" data-step={current}>
      <Stepper variant="numbered" orientation="horizontal" steps={steps} onSelect={i => { const n = (i + 1) as SeedStep; if (status[n].open) onStep(n) }} testid="seed-steps-strip" />
      <InfoTip title="Four steps">
        A seed search is four steps, one card at a time. 1: the shape to look for. 2: the preview — the whole search over every
        channel in scope, with a null drawn from noise copies of each channel, so you can see what chance alone finds. 3: where to
        cut — the matches closer than the cut are kept. 4: keep them: as they are (the preview's null stands behind them), or
        with the rigorous null (200 paired surrogate runs per channel). Click a step to go back to it.
      </InfoTip>
    </div>
  )
}
