/* fixup-ah — the blind check of a B.2 run (routes in `webui/server/blind_routes.py`; the core is
 * `Working/training/blind.py`). The labelling card reads only `getBlindQueue` and `getBlindShowing`, whose
 * payloads carry nothing that could tip the answer; Results reads `getBlindScores`. */
import { ApiError } from '../api'

async function rq<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let body: any = null
    try { body = await r.json() } catch { /* not json */ }
    const msg = body?.error ?? (typeof body?.detail === 'string' ? body.detail : body?.detail?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, body?.detail ?? body, body?.traceback)
  }
  return r.json() as Promise<T>
}

export type BlindVerdict = 'interesting' | 'not_interesting' | 'unsure' | 'artifact'
export type ExamKey = 'i_later_block' | 'ii_unseen_channels'
export const BLIND_EXAMS: ExamKey[] = ['i_later_block', 'ii_unseen_channels']

/* ---------------- the labelling card ---------------- */
export interface BlindQueuePage {
  queue: { id: number; name: string; total: number; judged: number; remaining: number; pace_s: number | null; verdict_options: BlindVerdict[]; run_id: number; closed: boolean }
  showings: { showing: number; judged: boolean; verdict: BlindVerdict | null }[]
  next_unjudged: number | null
  hidden: string
}
export interface BlindTrace { t: number[]; v: (number | null)[]; t0_s: number; t1_s: number; unit: string | null; reason: string | null; n_source: number; n_points: number; decimated: boolean }
export interface BlindShowing {
  showing: number; n_showings: number; judged: boolean; verdict: BlindVerdict | null
  window: { t0_s: number; t1_s: number }; duration_s: number; length: number; fs: number; scale_text: string
  pad_windows: number; unit: string | null; trace: BlindTrace
}
export const getBlindQueue = (qid: number | string) => rq<BlindQueuePage>(`/api/models/b2/blind/${qid}`)
export const getBlindShowing = (qid: number | string, i: number, px: number, pad = 1) =>
  rq<BlindShowing>(`/api/models/b2/blind/${qid}/showings/${i}?px=${Math.max(200, Math.round(px))}&pad=${pad}`)

/* ---------------- Models › Results — against a blind human ---------------- */
export interface Small { n: number; human_interesting: number; model_interesting: number; agreement: number | null; one_class: boolean; macro_f1: number | null; kappa: number | null; precision: number | null; recall: number | null }
export interface SelfAgreement { n_pairs: number; n_answered_pairs: number; n_scored_pairs: number; agree: number; share: number | null; any_word_share: number | null; kappa: number | null; note: string }
export interface ClusterRow { cluster: number; name: string; class: string | null; n_sample: number; n: number; human_interesting: number; share_interesting: number | null; agrees_with_mapping: number | null; population: number }
export interface BlindExam {
  title: string; status: string; n_sample: number; n_labelled: number; n_scored: number
  excluded: { unsure: number; artifact: number; not_yet_labelled: number }
  self_agreement: SelfAgreement; unit: string; n_units: number
  confusion: number[][]; confusion_labels: string[]; confusion_note: string
  macro_f1: number | null; macro_f1_ci: [number | null, number | null]; accuracy: number | null
  kappa: number | null; kappa_ci: [number | null, number | null]
  interesting: { precision: number | null; recall: number | null; f1: number | null; f1_ci: [number | null, number | null]; n_human?: number; n_model?: number }
  null: { n: number; mean: number | null; q95: number | null; p: number | null; draws: number[]; rule: string }
  reweighted: { precision?: number | null; recall?: number | null; f1?: number | null; accuracy?: number | null; note: string }
  per_cluster: ClusterRow[]
  per_scale: (Small & { scale_min: number; outside_training_scale: boolean })[]
  per_recording: (Small & { recording: string; name?: string })[]
}
export interface RefStats { all: Small; no_earlier_label: Small; n_overlapping_earlier_label: number }
export interface RefRow {
  model: string; file: string | null; image: string | null; kind: string; scale_min: number; outside_training_scale: boolean
  how_fed: string; embedding: string; contamination: string; status: string; reason: string | null; exams: Partial<Record<ExamKey, RefStats>>
}
export interface Stratum { exam: ExamKey; cluster: number; class: string; name: string; population: number; drawn: number; weight: number }
export interface BlindScores {
  run_id: number; k: number; queue_id: number | null; status: string
  mapping: { k: number | null; clusters: Record<string, { name: string; class: string | null }> } | null
  pool: { id: number; name: string; version: number; key: string } | null
  template: { id: number | null; name: string | null } | null
  arm: { name: string; label: string; k: number; linkage?: string } | null
  exam_titles: Record<ExamKey, string>
  predicted: Record<ExamKey, { n: number; by_class: Record<string, number>; by_cluster: Record<string, number>; status: string }>
  progress?: { total: number; judged: number; remaining: number; pace_s: number | null }
  verdicts?: Record<BlindVerdict, number>
  sample: { params: { n: number; repeat_frac: number; seed: number }; drawn_at: string
    summary: { n: number; n_showings: number; n_repeats: number; min_gap: number | null; strata: Stratum[]; by_scale: { exam: ExamKey; scale_min: number; drawn: number }[]; by_exam: Record<ExamKey, number>; rule: string } } | null
  exams: Partial<Record<ExamKey, BlindExam>>
  self_agreement?: SelfAgreement
  /** fixup-smoke2: one blind sample per pool — set when the sample and its labels are an earlier run's on this pool */
  shared?: { owner_run_id: number; not_predicted: number; note: string } | null
  reference: { status: 'not computed' | 'computed'; rows: RefRow[]; computed_at?: string; n_labelled?: number; n_overlapping_earlier_label?: number; contamination?: string; note?: string
    models?: { model: string; file: string; image: string | null; how_fed: string }[] }
}
export const getBlindScores = (runId: number) => rq<BlindScores>(`/api/models/b2/runs/${runId}/blind`)
export const makeBlindQueue = (runId: number, body: { n: number; repeat_frac: number; seed: number }) =>
  rq<{ queue_id: number; created: boolean; sample_path: string; summary: unknown }>(`/api/models/b2/runs/${runId}/blind`, { method: 'POST', body: JSON.stringify(body) })
export const scoreReference = (runId: number) => rq<{ job_id: number; status: string }>(`/api/models/b2/runs/${runId}/blind/reference`, { method: 'POST', body: '{}' })

export interface Disagreement {
  showing: number; window: number; recording_id: number; source_file: string; recording: string; channel: number; channel_name: string
  start: number; length: number; fs: number; scale_min: number; cluster: number; model_class: string; p_interesting: number; human: string
}
export type DisagreementKind = 'model_yes_human_no' | 'model_no_human_yes'
export const getDisagreements = (runId: number, exam: ExamKey, kind: DisagreementKind) =>
  rq<{ queue_id: number | null; windows: Disagreement[] }>(`/api/models/b2/runs/${runId}/blind/disagreements?exam=${exam}&kind=${kind}`)
