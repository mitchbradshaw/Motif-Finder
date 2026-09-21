/* Typed client for the FastAPI bridge (server/app.py). One function per route.
   Every non-2xx response throws ApiError carrying the server's message and, for
   500s, the traceback — so a backend failure is never silent in the page. */

export class ApiError extends Error {
  status: number
  detail: unknown
  traceback?: string
  constructor(status: number, message: string, detail?: unknown, traceback?: string) {
    super(message)
    this.status = status
    this.detail = detail
    this.traceback = traceback
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let body: any = null
    try { body = await r.json() } catch { /* not json */ }
    const msg = body?.error ?? (typeof body?.detail === 'string' ? body.detail : body?.detail?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, body?.detail ?? body, body?.traceback)
  }
  return r.json() as Promise<T>
}
const post = <T,>(path: string, body: unknown) => req<T>(path, { method: 'POST', body: JSON.stringify(body) })

/* ---------------- explore ---------------- */
export interface ChannelRef { id: number; channel: number; name: string; npy_exists: boolean }
export interface RecordingFile {
  source_file: string; fs: number; n_samples: number; duration_h: number; n_channels: number; held_out: boolean
  held_out_reason: string | null; channels: ChannelRef[]
}
export interface CoverageRow {
  id: number; channel: number; name: string
  annotations: number[]; detections: number[]; both: number[]; disagree: number[]
  counts: { annotations: number; detections: number; disagree: number; reviewed_pct: number | null }
}
export interface Coverage {
  source_file: string; fs: number; n_samples: number; duration_h: number; bins: number; bin_h: number; bin_edges_h: number[]
  rows: CoverageRow[]; verdict_counts: Record<string, number>; n_detection_runs: number; held_out: boolean; compute_ms: number
}
export interface Ribbons { buckets: number; bucket_s: number; coverage: (string | null)[]; detection_density: number[] }
export interface Channel {
  id: number; source_file: string; channel: number; fs: number; n_samples: number; duration_s: number; name: string; held_out: boolean; npy_path: string
  summary: { annotations: number; detections: number; detection_runs: number }; ribbons: Ribbons; y_range: [number, number]
}
export interface Envelope { t: number[]; v: (number | null)[]; n_source: number; n_points: number; decimated: boolean }
export interface WindowData { recording_id: number; fs: number; n_samples: number; t0_s: number; t1_s: number; envelope: Envelope; decimate_ms: number }
export interface Annotation { id: number; start_s: number; end_s: number; verdict: string; tag: string | null; note: string | null; source: string }
export interface Detection { id: number; start_s: number; end_s: number; score: number | null; run_id: number }
export interface Spans { recording_id: number; t0_s: number; t1_s: number; annotations: Annotation[]; detections: Detection[]; annotations_capped: boolean; detections_capped: boolean }

export const getRecordings = () => req<RecordingFile[]>('/api/recordings')
export const getCoverage = (file: string, bins = 57, verdicts?: string[]) =>
  req<Coverage>(`/api/corpus/${encodeURIComponent(file)}/coverage?bins=${bins}${verdicts?.length ? `&verdicts=${verdicts.join(',')}` : ''}`)
export const getChannel = (id: number) => req<Channel>(`/api/channels/${id}`)
export async function getWindow(id: number, t0: number, t1: number, px: number): Promise<WindowData & { round_trip_ms: number }> {
  const t = performance.now()
  const d = await req<WindowData>(`/api/channels/${id}/window?t0=${t0}&t1=${t1}&px=${Math.round(px)}`)
  return { ...d, round_trip_ms: performance.now() - t }
}
export const getSpans = (id: number, t0: number, t1: number) => req<Spans>(`/api/channels/${id}/spans?t0=${t0}&t1=${t1}`)

/* ---------------- analyse: chain ---------------- */
export interface ParamSpec { name: string; type: 'int' | 'float' | 'str' | 'bool'; default: unknown; description: string; choices: unknown[] | null; min: number | null; max: number | null }
export interface AdapterCard {
  name: string; stage: string; algorithm: string; display_name: string; page_name: string; description: string
  input_kind: TypeKind; output_kind: TypeKind; signature: string; category: 'preprocess' | 'encode' | 'detect' | 'cluster' | 'model' | 'control'
  has_estimate: boolean; max_span_samples: number | null; has_recommend: boolean
  side_inputs: { name: string; type_kind: TypeKind; sources: string[] }[]; known_broken: string | null; params: ParamSpec[]
}
export type TypeKind = 'signal' | 'spanset' | 'windowset' | 'encoding' | 'grouping' | 'model' | 'scores'
export const TYPE_LABEL: Record<TypeKind, string> = { signal: 'Signal', spanset: 'SpanSet', windowset: 'WindowSet', encoding: 'Encoding', grouping: 'Grouping', model: 'Model', scores: 'Scores' }

export interface Step { stage: string; algorithm: string; params: Record<string, unknown>; side_inputs?: Record<string, unknown> }
export interface Junction { index: number; ok: boolean; producing: TypeKind; expected: TypeKind | null; reason: string; core_reason?: string }
export interface Validation {
  ok: boolean; junctions: Junction[]; terminal_kind: TypeKind | null; terminal_label: string | null
  estimate?: { total_s: number; per_step_s: (number | null)[]; unknown?: number[]; route?: 'local' | 'unknown' }; hashes?: { config_hash: string; recipe_hash: string }
  cache?: { index: number; prefix_hash: string; cached: boolean; path: string | null }[]; over_ceiling?: number[]; recipe_error?: string
}
export interface Compatible {
  position: number; producing: TypeKind; producing_label: string; next_requires: TypeKind | null; next_requires_label: string | null; next_name: string | null
  n_fit: number; n_total: number; rows: { name: string; ok: boolean; reason: string }[]; stale_from: number | null
}
export interface Template { id: string | number; name: string; builtin: boolean; steps: Step[]; kind?: 'detection' | 'encoding' | 'training' | 'interrogation'; version?: number; description?: string; valid?: boolean; created_at?: string; updated_at?: string }

export const getAdapters = () => req<AdapterCard[]>('/api/adapters')
export const validateChain = (steps: Step[], recording_id?: number, span?: [number, number] | null) =>
  post<Validation>('/api/chain/validate', { steps, recording_id, span })
export const compatibleAt = (steps: Step[], position: number) => post<Compatible>('/api/chain/compatible', { steps, position })
export const validateParams = (step: Step) => post<{ params: Record<string, unknown> }>('/api/chain/params', step)
export const getTemplates = () => req<Template[]>('/api/templates')
export const saveTemplate = (name: string, steps: Step[]) => post<{ id: number; name: string; note: string }>('/api/templates', { name, steps })

/* ---------------- analyse: runs ---------------- */
export type StepStatus = 'pending' | 'running' | 'done' | 'failed' | 'cancelled' | 'blocked'
export interface JobStep {
  index: number; stage: string; algorithm: string; status: StepStatus; started_at: number | null; elapsed_s: number | null
  cached_predicted: boolean; cached: boolean | null; core_elapsed_s?: number; kind: TypeKind | null; summary: string | null; has_payload: boolean
}
export interface JobError { step: number | null; message: string; type: string; traceback?: string; adapter?: string | null }
export interface JobSnapshot {
  job_id: number; status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'; n_steps: number; current_step: number | null
  steps: JobStep[]; error: JobError | null; step_timings: Record<string, number> | null; detections_written: number | null
  config_hash: string | null; db_run_id: number | null; started_at: number; finished_at: number | null; recipe: { recording_id: number; span: [number, number] | null; steps: Step[] }
  recording_id: number; elapsed_s: number
}
export interface RunEvent { event: 'hello' | 'step_start' | 'step_done' | 'run_end' | 'cancel_requested'; job_id: number; ts: number; [k: string]: unknown }
export interface DbRun {
  id: number; config_id: number; recording_id: number; span_start: number; span_end: number; started_at: string; status: string
  finished_at: string | null; duration_s: number | null; error_text: string | null; current_step: number | null; name: string | null
  steps: string[]; recipe: { recording_id: number; span: [number, number] | null; steps: Step[] } | null; step_timings: Record<string, number> | null; n_detections: number; cancelled?: boolean
}

export const startRun = (recording_id: number, span: [number, number] | null, steps: Step[], px = 1200) =>
  post<JobSnapshot>('/api/runs', { recording_id, span, steps, px })
export const getRun = (jobId: number) => req<JobSnapshot>(`/api/runs/${jobId}`)
export const cancelRun = (jobId: number) => post<{ accepted: boolean; status: string; note: string }>(`/api/runs/${jobId}/cancel`, {})
export const getStepPayload = (jobId: number, index: number) => req<Payload>(`/api/runs/${jobId}/steps/${index}`)
export const getRunLog = (jobId: number) => req<{ job_id: number; lines: string[]; error: JobError | null }>(`/api/runs/${jobId}/log`)
export const listRuns = (recording_id?: number, limit = 30) => req<{ db_runs: DbRun[]; jobs: JobSnapshot[] }>(`/api/runs?limit=${limit}${recording_id ? `&recording_id=${recording_id}` : ''}`)
export const exportRun = (jobId: number) => req<{ path: string; bytes: number }>(`/api/runs/${jobId}/export`)

/** Subscribe to a run's SSE stream. Late subscribers get the full replay. Returns an unsubscribe fn.
 *  `onError` fires with a typed reason for a transport error AND for an unparseable frame (critique r1:
 *  a corrupt frame must never leave the page "computing" forever); `isOpen()` lets a store poll as a
 *  liveness fallback while the socket is not OPEN. */
export interface SseHandle { close: () => void; isOpen: () => boolean }
export function subscribeRun(jobId: number, onEvent: (e: RunEvent) => void, onError?: (reason: string) => void): SseHandle {
  const es = new EventSource(`/api/runs/${jobId}/events`)
  const handler = (ev: MessageEvent) => {
    try {
      const data = JSON.parse(ev.data) as RunEvent
      onEvent({ ...data, event: (ev.type as RunEvent['event']) })
      if (ev.type === 'run_end') es.close()
    } catch (err) {
      console.error('bad SSE payload', err, ev.data)
      onError?.(`run stream unreadable (${err instanceof Error ? err.message : String(err)})`)
    }
  }
  for (const name of ['hello', 'step_start', 'step_done', 'run_end', 'cancel_requested']) es.addEventListener(name, handler as EventListener)
  es.onerror = () => { onError?.(es.readyState === EventSource.CLOSED ? 'run stream closed' : 'run stream interrupted') }
  return { close: () => es.close(), isOpen: () => es.readyState === EventSource.OPEN }
}

/* ---------------- the seven payload types (server/serialize.py) ---------------- */
export interface EnvelopeSeries { t: number[]; v: (number | null)[]; n_source: number; n_points: number; decimated: boolean }
export interface SignalPayload { type: 'signal'; fs: number; n: number; t0_s: number; t1_s: number; y_range: [number, number] | null; envelope: EnvelopeSeries; summary: string }
export interface ScoresPayload {
  type: 'scores'; fs: number; n: number; t0_s: number; t1_s: number; nan_tail: number; value_range: [number, number] | null; envelope: EnvelopeSeries
  top: { low: { t_s: number; v: number }[]; high: { t_s: number; v: number }[] }; histogram: { counts: number[]; edges: number[] } | null; m: number | null; summary: string
}
export interface SpansetPayload { type: 'spanset'; fs: number; n: number; capped: boolean; start_s: number[]; end_s: number[]; labels: (string | null)[] | null; scores: (number | null)[] | null; summary: string }
export interface WindowsetPayload {
  type: 'windowset'; fs: number; n_windows: number; length: number; length_s: number; starts_s: number[]; capped: boolean
  features: { n_columns: number; columns: string[]; matrix: (number | null)[][] | null; col_range?: [number | null, number | null][] } | null; summary: string
}
export interface EncodingSymbolicPayload {
  type: 'encoding'; kind: 'symbolic'; n_symbols: number; alphabet_size: number; symbols: number[]; letters: string; capped: boolean; alphabet?: string | null
  samples_per_symbol: number | null; seconds_per_symbol: number | null; t0_s: number; fs: number; cutlines: number[] | null; cutline_domain: string | null
  representatives: number[] | null; paa: number[] | null; n_trimmed: number | null; summary: string
}
export interface EncodingImagePayload {
  type: 'encoding'; kind: 'image'; ndim: number; shape: number[]; n_images?: number | null; display_shape?: [number, number]; channels?: number; value_range?: [number, number]
  pixels_b64?: string; series?: number[]; bin_freqs?: number[] | null; summary: string
}
export interface GroupingPayload {
  type: 'grouping'; n: number; k: number; label_base: number; linkage: string | null; clusters: { id: number; count: number }[]; labels: number[]; capped: boolean
  strip: { starts_s: number[]; length_s: number } | null; summary: string
}
export interface ModelPayload { type: 'model'; path: string; exists: boolean; size_bytes: number | null; card: Record<string, unknown>; summary: string }
export interface ErrorPayload { type: string; error: string; traceback?: string; summary: string }
export type Payload = SignalPayload | ScoresPayload | SpansetPayload | WindowsetPayload | EncodingSymbolicPayload | EncodingImagePayload | GroupingPayload | ModelPayload | ErrorPayload

/* ---------------- settings: registry, settings, audit, about, storage (server/registration.py, Prompt 02) ---------------- */
const put = <T,>(path: string, body: unknown) => req<T>(path, { method: 'PUT', body: JSON.stringify(body) })
const del = <T,>(path: string) => req<T>(path, { method: 'DELETE' })

export interface RegistryKind { name: string; label: string; roots: string[]; table: string; ui: string; naming: string }
export interface Candidate { kind: string; path: string; name: string; facts: Record<string, any>; warnings: string[]; registered: boolean; registered_ids: number[] }
export interface CheckItem { name: string; ok: boolean; detail: string }
export interface ExcerptLink { recording_id: number; source_file: string; channel: number; candidate_channel: number; offset: number; decimation: number; r: number; name?: string }
export interface CheckReport { candidate: Candidate; ok: boolean; checks: CheckItem[]; facts: Record<string, any>; warnings: string[]; sha1: string | null; excerpts: ExcerptLink[]; excerpt_of: ExcerptLink | null }
export interface RegisteredChannel { id: number; channel: number; name: string; npy_path: string; exists: boolean; parent_recording_id: number | null }
export interface RegisteredRecording {
  kind: 'recording'; id: number; ids: number[]; name: string; source_file: string; dir: string; n_channels: number; fs: number; fs_source: 'read' | 'inferred' | 'unrecorded'
  n_samples: number; duration_h: number | null; held_out: boolean; warnings: string[]; registered_at: string | null; registered_by: string | null
  excerpt_of: { recording_id: number; source_file: string; channel: number; name: string; offset: number | null; decimation: number | null } | null
  channels: RegisteredChannel[]; npy_exists: boolean; manifest: Record<string, any> | null
}
export interface RegisteredArtifact {
  id: number; kind: string; path: string; name: string; manifest_path: string | null; recording_id: number | null; channel: number | null
  span_start: number | null; span_end: number | null; fs: number | null; params: Record<string, any>; producer: string | null; sha1: string | null
  warnings: string[]; checks: CheckItem[]; created_at: string; actor: string | null; exists: boolean; manifest: Record<string, any> | null; bytes: number | null
}
export interface RegistryPage<T = RegisteredRecording | RegisteredArtifact> { kind: string; spec: RegistryKind; roots: string[]; registered: T[]; candidates: Candidate[]; scan_ms: number }
export interface RegisterResult { id: number; kind: string; name: string; path: string; table: string; warnings: string[]; sha1: string | null; recording_id: number | null; ids: number[] | null; facts: Record<string, any>; excerpts: ExcerptLink[]; excerpt_of: ExcerptLink | null; note: string }

export const getRegistryKinds = () => req<{ kinds: RegistryKind[] }>('/api/registry')
export const getRegistry = <T = RegisteredRecording | RegisteredArtifact>(kind: string) => req<RegistryPage<T>>(`/api/registry/${encodeURIComponent(kind)}`)
export const checkCandidate = (kind: string, path: string, overrides: Record<string, unknown> = {}) =>
  post<CheckReport>(`/api/registry/${encodeURIComponent(kind)}/check`, { path, overrides })
export const registerCandidate = (kind: string, path: string, overrides: Record<string, unknown> = {}, provenance: Record<string, unknown> = {}) =>
  post<RegisterResult>(`/api/registry/${encodeURIComponent(kind)}/register`, { path, overrides, provenance })
export const unregisterRow = (kind: string, id: number) => del<{ table: string; id: number; active: number }>(`/api/registry/${encodeURIComponent(kind)}/${id}`)

export interface HeldOutState { on: boolean; recording: string; name: string; file: string }
export interface SettingsPageData {
  page: string; title: string; values: Record<string, unknown>; updated_at: string | null; n_keys: number; actor: string | null; mode: 'sandbox' | 'project'
  /* datasets */ recordings?: RegisteredRecording[]; candidates?: Candidate[]; raw_candidates?: Candidate[]; held_out?: HeldOutState; defaults?: Record<string, unknown>
  /* vocabulary */ verdicts?: { name: string; n_annotations: number; n_adjudications: number }[]; tags?: Record<string, any>[]
  /* compute */ machine?: { cores: number | null; ram_gb: number | null; gpu: string | null; platform: string; detected: string }
  /* analysis defaults */ cache_gb?: number; cache_root?: string | null
  /* blocks */ adapters?: AdapterCard[]; n_adapters?: number
}
export const getSettingsPage = (page: string) => req<SettingsPageData>(`/api/settings/${encodeURIComponent(page)}`)
export const putSettingsPage = (page: string, values: Record<string, unknown>, confirm_name?: string, previous: Record<string, unknown> = {}) =>
  put<{ page: string; changed: string[]; values: Record<string, unknown>; updated_at: string | null; held_out?: HeldOutState }>(`/api/settings/${encodeURIComponent(page)}`, { values, confirm_name, previous })
export const getAllSettings = () => req<{ pages: Record<string, Record<string, unknown>>; mode: string }>('/api/settings')

export interface AuditRow { id: number; when: string; kind: string; what: string; where: string; route: string | null; by: string; detail: Record<string, unknown> | null }
export const getAudit = (kind?: string, limit = 500) => req<{ entries: AuditRow[]; kinds: string[]; mode: string }>(`/api/audit?limit=${limit}${kind && kind !== 'all' ? `&kind=${encodeURIComponent(kind)}` : ''}`)
export const postAudit = (e: { kind: string; what: string; where: string; route?: string; detail?: Record<string, unknown> }) => post<{ id: number }>('/api/audit', e)
export const auditCsvUrl = (kind?: string) => `/api/audit.csv${kind && kind !== 'all' ? `?kind=${encodeURIComponent(kind)}` : ''}`

export interface About {
  project: string; code: { version: string; branch: string | null; dirty: boolean; summary: string }
  schema: { tables: number; settings_rows: number; audit_rows: number; recordings: number; recording_rows: number; registered_artifacts: number; path: string }
  blocks: { registered: number; broken: string[]; summary: string }; python: string; executable: string; packages: Record<string, string | null>
  mode: string; banner: string; db_path: string; db_backup: string | null; runtime_dir: string; repo_root: string; held_out_file: string
  settings_store: string; environment: string; future: { name: string; detail: string }[]; diagnostics: string
}
export const getAbout = () => req<About>('/api/about')

export interface StorageRootRow { id: string; root: string; path: string; exists: boolean; bytes: number; n_files: number; actions: string[]; note: string; locked: boolean }
export interface BackupRow { name: string; path: string; bytes: number; mtime: number; current: boolean }
export interface Storage { roots: StorageRootRow[]; backups: BackupRow[]; free_gb: number | null; total_gb: number | null; mode: string; backups_dir: string; db_backup: string | null }
export const getStorage = () => req<Storage>('/api/storage')
export const postBackup = () => post<{ path: string; bytes: number; mode: string }>('/api/backups', {})

/* ---------------- stage-3 prompt 01: templates as rows, jobs, explore live regions, interrogation, window sets ---------------- */
export const getTemplate = (id: number) => req<Template>(`/api/templates/${id}`)
export const createTemplate = (name: string, steps: Step[], description = '', kind?: Template['kind']) =>
  post<Template>('/api/templates', { name, steps, description, kind })
export const updateTemplate = (id: number, patch: { name?: string; steps?: Step[]; description?: string }) =>
  req<Template>(`/api/templates/${id}`, { method: 'PUT', body: JSON.stringify(patch) })
export const deleteTemplate = (id: number) => req<{ deleted: number }>(`/api/templates/${id}`, { method: 'DELETE' })
export const applyTemplate = (id: number, recording_id: number, span?: [number, number] | null) =>
  post<{ template: { id: number; name: string; kind: string; version: number }; recipe: { recording_id: number; span: [number, number] | null; steps: Step[] } }>(`/api/templates/${id}/apply`, { recording_id, span })

export type JobKind = 'chain_run' | 'sweep' | 'import' | 'regroup' | 'training'
export interface JobRow {
  job_id: number; kind?: JobKind; status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'; error: JobError | null
  started_at: number | string; finished_at: number | string | null; db_run_id: number | null; restored?: boolean
  progress?: { done: number; total: number | null; message: string } | Record<string, unknown>; meta?: Record<string, unknown>; result?: unknown
  steps?: JobStep[]; recipe?: JobSnapshot['recipe']; n_steps?: number; current_step?: number | null
}
export const listJobs = (limit = 50) => req<JobRow[]>(`/api/jobs?limit=${limit}`)
export const getJob = (id: number) => req<JobRow>(`/api/jobs/${id}`)
export const cancelJob = (id: number) => post<{ accepted: boolean; status: string; note: string }>(`/api/jobs/${id}/cancel`, {})
export function subscribeJob(jobId: number, onEvent: (e: RunEvent & { event: string }) => void, onError?: (reason: string) => void): SseHandle {
  const es = new EventSource(`/api/jobs/${jobId}/events`)
  const handler = (ev: MessageEvent) => {
    try { onEvent({ ...(JSON.parse(ev.data) as RunEvent), event: ev.type as RunEvent['event'] }); if (ev.type === 'run_end' || ev.type === 'job_end') es.close() }
    catch (err) { onError?.(`job stream unreadable (${err instanceof Error ? err.message : String(err)})`) }
  }
  for (const name of ['hello', 'step_start', 'step_done', 'run_end', 'cancel_requested', 'job_start', 'progress', 'job_end']) es.addEventListener(name, handler as EventListener)
  es.onerror = () => { onError?.(es.readyState === EventSource.CLOSED ? 'job stream closed' : 'job stream interrupted') }
  return { close: () => es.close(), isOpen: () => es.readyState === EventSource.OPEN }
}

export interface FileRun { id: number; recording_id: number; channel: number; status: string; started_at: string; name: string | null; algorithms: string[]; method: string; n_detections: number }
export const getRunsForFile = (file: string) => req<{ source_file: string; runs: FileRun[]; methods: string[] }>(`/api/corpus/${encodeURIComponent(file)}/runs`)
export const getCoverageFiltered = (file: string, bins: number, opts: { verdicts?: string[]; run?: number[]; method?: string }) =>
  req<Coverage & { run_filter: number[] | null; method_filter: string | null }>(
    `/api/corpus/${encodeURIComponent(file)}/coverage?bins=${bins}${opts.verdicts?.length ? `&verdicts=${opts.verdicts.join(',')}` : ''}${opts.run?.length ? `&run=${opts.run.join(',')}` : ''}${opts.method ? `&method=${encodeURIComponent(opts.method)}` : ''}`)
export interface TagRow { category: string; value: string }
export interface Tags {
  recording_id: number; t0_s: number; t1_s: number
  annotations: (Annotation & { tags: TagRow[] })[]
  reviewed: { id: number; start_s: number; end_s: number; scale: string | null; source: string; at: string }[]
  reviewed_pct: number; tag_counts: Record<string, number>; vocabulary: { id: number; category: string; value: string; description: string | null; active: number }[]
  annotations_capped?: boolean; reviewed_capped?: boolean
}
export const getTags = (id: number, t0?: number, t1?: number) => req<Tags>(`/api/channels/${id}/tags?t0=${t0 ?? 0}${t1 != null ? `&t1=${t1}` : ''}`)
export const getSiblings = (id: number) => req<{ recording_id: number; source_file: string; channels: { id: number; channel: number; name: string; npy_exists: boolean }[] }>(`/api/channels/${id}/siblings`)
export interface CrossRow { id: number; channel: number; name: string; is_reference: boolean; lag_s: number | null; r: number | null; classification: string; envelope?: EnvelopeSeries; y_range?: [number, number]; error?: string }
export const getCross = (id: number, t0: number, t1: number, px = 900) => req<{ reference_id: number; source_file: string; t0_s: number; t1_s: number; fs: number; stride: number; channels: CrossRow[] }>(`/api/cross/${id}?t0=${t0}&t1=${t1}&px=${Math.round(px)}`)
export const takeSpanForReview = (recording_id: number, start_idx: number, end_idx: number, note?: string, scale_viewed?: string) =>
  post<{ id: number; recording_id: number; start_s: number; end_s: number; verdict: 'seed'; source: string; note: string | null; banner: string }>('/api/annotations/seed', { recording_id, start_idx, end_idx, note, scale_viewed })

export interface SeedFamily { id: string; label: string; source: 'seed'; recording_id: number; source_file: string; channel: number; fs: number; morphology: string | null; n_members: number; span_h: [number, number]; median_depth_mv: number }
export interface SeedMember {
  event_id: string; recording_id: number; source_file: string; channel: number; fs: number; morphology: string; trigger: string
  onset_idx: number; onset_h: number; trough_idx: number; trough_h: number; snippet_start_idx: number; snippet_end_idx: number
  drop_depth_mv: number; rise_height_mv: number; fall_duration_s: number; peak_to_peak_mv: number; fall_dominance: number; purity: number; is_pure: number; cluster_id: number
  source: 'seed'; snippet?: { t_s: number[]; detrended_mv: number[]; n: number }
}
export interface SlopeMember { event_id: string; onset_slope_mv_s: number; max_slope_mv_s: number; mean_slope_mv_s: number; peakedness: number; drop_depth_mv: number; fall_duration_s: number; onset_h: number; onset_offset: number; trough_offset: number; angle_deg: number | null; recording_id: number; source_file: string; span_key: string }
export const getFamilies = () => req<{ source: 'seed'; store: string; manifest: Record<string, unknown>; families: SeedFamily[] }>('/api/interrogation/families')
export const getFamilyMembers = (key: string, snippets = true) => req<{ family: string; source: 'seed'; members: SeedMember[] }>(`/api/interrogation/families/${encodeURIComponent(key)}/members?snippets=${snippets}`)
export const getFamilySlope = (key: string, scale = 'raw') => req<{ family: string; source: 'seed'; features: { name: string; unit: string; kind: string; label: string }[]; rules: { name: string; rule: string }[]; members: SlopeMember[]; rose: { bin_centres_deg: number[]; counts: number[]; scale: string; caption: string; groups: Record<string, Record<string, unknown>> } }>(`/api/interrogation/families/${encodeURIComponent(key)}/slope?scale=${scale}`)
export interface Dist { n: number; counts: number[]; edges: number[]; median: number | null; iqr: [number, number] | null; min?: number; max?: number }
export const getFamilyAggregate = (key: string) => req<{ family: string; source: 'seed'; n: number; distributions: Record<string, Dist>; timeline: { event_id: string; onset_h: number; depth_mv: number; max_slope_mv_s: number; position: number }[]; scaling: { x: string; y: string; beta: number; ci95: [number, number]; n: number } | null }>(`/api/interrogation/families/${encodeURIComponent(key)}/aggregate`)

export const saveWindowSet = (job_id: number, step: number, name: string, notes?: string) =>
  post<{ id: number; name: string; path: string; n_windows: number; length: number; run_id: number; note: string }>('/api/windowsets', { job_id, step, name, notes })
export const listWindowSets = () => req<{ window_sets: { id: number; name: string; path: string; recording_id: number | null; channel: number | null; fs: number | null; created_at: string; active: number; manifest?: Record<string, unknown> }[]; root: string }>('/api/windowsets')

/* ---------------- stage-3 prompt 04: Discovery (server/discovery.py) ----------------
   One function per route, returning the server's own shape untranslated. The
   fixture-shaped adapter the pages read lives in api/discovery.ts; nothing here
   renames a field or fills in a number the server declined to give. */

const dq = (params: Record<string, string | number | boolean | undefined | null>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

export interface DiscMatchingRule { criterion: string; iou: number; onset: number }
export interface DiscNull { method: string | null; n: number; requested?: string | null; supported?: boolean; reason?: string | null }
export interface DiscSession {
  id: number; name: string; recording: string; channels: string[]
  section: [number, number]; sectionSamples: [number, number]
  null: DiscNull; localLimitMin: number; savedAt: string; matchingRule: DiscMatchingRule
}
export interface DiscRecordingOption {
  key: string; label: string; file: string; stem: string; hours: number; channels: string[]
  heldOut: boolean; fs: number; heldOutReason: string | null
}
export interface DiscSessionPayload { session: DiscSession; recordings: DiscRecordingOption[] }
export const getDiscoverySession = () => req<DiscSessionPayload>('/api/discovery/session')
export const putDiscoverySession = (body: { name?: string; recording?: string; channels?: string[]; section?: [number, number]; null?: { method?: string; n?: number } }) =>
  put<DiscSessionPayload>('/api/discovery/session', body)

export interface DiscRun {
  key: string; id: string | null; label: string; kind: string; colour: string; glyph: string; detail: string
  status: string; template: string | null; stageCount: number | null; version: number | null
  perChannelMin: number | null; job: string | null; runGroupId: number | null
  channelsDone: string | null; found: number | null
  progress?: number; doneAt?: string; error?: string; reviewedH?: number
}
export const getDiscoveryRuns = () => req<DiscRun[]>('/api/discovery/runs')

export interface DiscTemplateStage { index: string; name: string; signature: string; locked?: string; glyph: string }
export interface DiscTemplate {
  name: string; kind: string; signature: string; fits: boolean; fitsReason: string | null
  lastScore: string; savedAt: string; lastUsed: number; stages: DiscTemplateStage[]
  /* null until a real Preview has been run — `previewNote` says so */
  perChannelMin: number | null; diskGB: number | null
  preview: { spans: number; hours: number; channel: string; nullGives: number } | null
  previewNote: string | null; complexity: string
  bind: string | null; inSession: string | null; hasModel: boolean
  version: number | null; builtin: boolean; description: string | null
}
export const getDiscoveryTemplates = () => req<DiscTemplate[]>('/api/discovery/templates')

export interface DiscHistoryEntry { id: string; label: string; when: string; status: string; runKey: string; inSession: boolean; detail: string }
export const getDiscoveryHistory = () => req<DiscHistoryEntry[]>('/api/discovery/history')

export type DiscOverview = { refused: string; data?: undefined } | { refused?: undefined; data: Record<string, (number | null)[]> }
export const getDiscoveryOverview = (recording: string, channels: string[]) =>
  req<DiscOverview>(`/api/discovery/overview${dq({ recording, channels: channels.join(',') })}`)

export interface DiscFiresRow { run: string; counts: number[]; unfinishedFrom?: number }
export interface DiscFiresChannel { channel: string; reviewedH: number; reviewed: number[]; rows: DiscFiresRow[] }
export interface DiscFires { binH: number; firstBin: number; nBins: number; channels: DiscFiresChannel[] }
export const getDiscoveryFires = (channels: string[], t0: number, t1: number, runs: string[]) =>
  req<DiscFires>(`/api/discovery/fires${dq({ channels: channels.join(','), t0, t1, runs: runs.join(',') })}`)

/** §7.3's three branches. Exactly one variant's keys are present; the client branches on key presence. */
export type DiscRecall = { value: number; overH: number; none?: undefined } | { none: true; note: string | null }
export interface DiscScoreRow {
  found: number; judged: number; reviewed: number; interesting: number; nullExpects: number
  /** `nullExpects` of 0 with `nullRun: false` means no null was run; with true it means the null
   *  found nothing. `nullDraws` is how many surrogate draws that count is over — the number is not
   *  readable without it. `xNullNote` carries the server's words when there is no ratio to take. */
  nullRun: boolean; nullDraws: number | null; xNullNote: string | null
  recall: DiscRecall; precision: number | null; xNull: number | null
  note: string | null; precisionNote: string | null; reviewedH: number; status: string | null
}
export interface DiscScoreRun {
  run: string; total: DiscScoreRow; channels: (DiscScoreRow & { channel: string })[]
  pooledH: number; rule: DiscMatchingRule; reviewedCriterion: string
}
export const getDiscoveryScoreboard = (runs: string[], channels: string[], t0: number, t1: number) =>
  req<DiscScoreRun[]>(`/api/discovery/scoreboard${dq({ runs: runs.join(','), channels: channels.join(','), t0, t1 })}`)

export interface DiscDetection {
  id: string; detectionId: number; index: number; of: number; run: string; channel: string
  atH: number; durationS: number; depthMv: number | null; score: number | null
  priorVerdict: string | null; alsoFoundBy: string[]
}
export const getDiscoveryDetections = (run: string, channel: string, t0: number, t1: number) =>
  req<DiscDetection[]>(`/api/discovery/detections${dq({ run, channel, t0, t1 })}`)

export interface DiscDetectionWindow { t0H: number; stepS: number; values: (number | null)[]; spanS: [number, number] }
export const getDiscoveryDetectionWindow = (detectionId: number, padS = 120, px = 900) =>
  req<DiscDetectionWindow>(`/api/discovery/detections/${detectionId}/window${dq({ pad_s: padS, px })}`)

export interface DiscSignal { t0H: number; stepS: number; values: (number | null)[] }
export const getDiscoverySignal = (channel: string, t0: number, t1: number, px = 1200) =>
  req<DiscSignal>(`/api/discovery/signal${dq({ channel, t0, t1, px })}`)

export interface DiscSeedInfo {
  id: string; role: string; source: string; title: string; family: string | null; familyLine: string | null
  recording: string; channel: string; startH: number; samples: number; lengthS: number
  hash: string; trace: (number | null)[]
}
export const getDiscoverySeeds = () => req<{ seeds: DiscSeedInfo[]; counts: Record<string, number>; note: string | null }>('/api/discovery/seeds')

/** The window is locked to the exemplar's native length; there is no recommended
 *  cut here — it is computed from the distance distribution (`recommendedCut`). */
export interface DiscSeedParams {
  algorithm: string; windowSamples: number; windowS: number; windowLocked: boolean
  scaleBank: string; exclusionSamples: number; exclusionS: number; overlap: string
  /** The guard that RAN is `exclusionS` (stumpy.match's m/4); §7.6's m/2 is
   *  `specExclusionS`. `exclusionSettable` is false: the block takes no
   *  exclusion parameter, so a control that moved it would move only the card. */
  specExclusionS?: number; exclusionSettable?: boolean
  exclusion_note: string; threshold?: number | null
}
export interface DiscSeedDraft {
  key: string; label: string; seedId: string; source: string; bind: string
  params: DiscSeedParams; applied: DiscSeedParams | null; estimateS: number | null
  recommended: DiscSeedParams; seed: DiscSeedInfo
}
export interface DiscSeedSetup { draft: DiscSeedDraft; recommended: DiscSeedParams; seeds: DiscSeedInfo[] }
export const getDiscoverySeedSetup = (seed?: string) => req<DiscSeedSetup>(`/api/discovery/seed/setup${dq({ seed })}`)
export const putDiscoverySeedDraft = (body: { seedId?: string; label?: string; bind?: string; params?: Record<string, unknown> }) =>
  put<{ draft: DiscSeedDraft }>('/api/discovery/seed/draft', body)

export interface DiscSeedQuery { seedId: string; channels: string[]; t0: number; t1: number; k?: number; maxDistance?: number }
export interface DiscSeedMatch {
  id: string; d: number; channel: string; atH: number; index: number
  judged: boolean; verdict: string | null; trace: (number | null)[]
}
export interface DiscSeedNull { distances: number[]; draws: number; method: string | null; supported: boolean; reason: string | null; requested: string | null }
export interface DiscSeedResults {
  ready: true; key: string; candidates: DiscSeedMatch[]; nullDistances: number[]; null: DiscSeedNull
  recommendedCut: number | null; perChannel: { channel: string; n: number; nullDraws: number }[]
  m: number; seedId: string; span: [number, number]
  counts?: Record<string, number> | null; exclusionNote: string; computedAt?: string; restored?: boolean
}
export interface DiscSeedPending { ready: false; job_id: number | null; key: string; progress?: unknown; note?: string }
export const startDiscoverySeedResults = (q: DiscSeedQuery) =>
  post<DiscSeedResults | DiscSeedPending>('/api/discovery/seed/results', q)
export const pollDiscoverySeedResults = (q: DiscSeedQuery) =>
  req<DiscSeedResults | DiscSeedPending>(`/api/discovery/seed/results${dq({ seedId: q.seedId, channels: q.channels.join(','), t0: q.t0, t1: q.t1, k: q.k, maxDistance: q.maxDistance })}`)

export interface DiscSeedProfile {
  t0H: number; stepS: number; signal: (number | null)[]; distance: (number | null)[]
  m: number; seedId: string; channel: string; nSignal: number; nDistance: number
}
export const getDiscoverySeedProfile = (seedId: string, channel: string, t0: number, t1: number, px = 1200) =>
  req<DiscSeedProfile>(`/api/discovery/seed/profile${dq({ seedId, channel, t0, t1, px })}`)

export interface DiscPlanBody {
  template?: string; seedId?: string; channels?: string[]; t0?: number; t1?: number
  k?: number; maxDistance?: number; measuredPerChannelS?: number; sampleHours?: number; label?: string
}
export interface DiscPlan {
  runnable: boolean; reason: string | null; refused: unknown[]; route: 'local' | 'cluster'
  estimate_s: number | null; ceiling_s: number; uncosted: unknown[]; n_channels: number
  channels: string[]; sectionH: [number, number]; span: [number, number]
  template: string | null; seedId: string | null; m: number | null
  usesMatrixProfile: boolean; reuseNote: string | null
}
export const postDiscoveryPlan = (body: DiscPlanBody) => post<DiscPlan>('/api/discovery/plan', body)
/** The only measured cost: the chain run on a sample of one channel and extrapolated. */
export interface DiscPreview { estimate_s: number; route: 'local' | 'cluster'; ceiling_s: number; template: string | null; note: string | null }
export const postDiscoveryPreview = (body: DiscPlanBody) => post<DiscPreview>('/api/discovery/preview', body)

export interface DiscApplyResult { run_key: string; job_id: number | null; route: string; ceiling_s: number; estimate_s: number | null; started: boolean; note: string | null }
export const applyDiscoveryTemplates = (templates: string[], channels: string[], t0: number, t1: number, run = true) =>
  post<DiscApplyResult[]>('/api/discovery/templates/apply', { templates, channels, t0, t1, run })
export const runDiscoverySeedSearch = (body: DiscSeedQuery & { label?: string; cut?: number }) =>
  post<{ run_key: string; job_id: number | null; route: string; started: boolean }>('/api/discovery/seed/run', body)
export const postDiscoverySlurm = (body: DiscPlanBody) =>
  post<{ script_path: string; script: string; route: string; estimate_s: number | null; ceiling_s: number; channels: string[]; note: string | null }>('/api/discovery/slurm', body)

/** Adopt a past Discovery run into this session: a row pointing at the same run
 *  group, never a re-execution. `adopted: false` means it was already here. */
export const openDiscoveryHistoryRun = (historyId: string) =>
  post<{ run_key: string; adopted: boolean; note: string }>(`/api/discovery/history/${encodeURIComponent(historyId)}/open`, {})

export const discardDiscoveryRun = (runKey: string) =>
  post<{ run_key: string; status: string; superseded: number; adjudications_written: number; annotations_written: number; note: string }>(`/api/discovery/runs/${encodeURIComponent(runKey)}/discard`, {})
export const restoreDiscoveryRun = (runKey: string) =>
  post<{ run_key: string; status: string; restored: number }>(`/api/discovery/runs/${encodeURIComponent(runKey)}/restore`, {})
export const sendDiscoveryRunToReview = (runKey: string, limit = 500, name?: string) =>
  post<{ run_key: string; queued: number; unjudged: number; queue: string; run_group_id: number; writes: string; note: string }>(`/api/discovery/runs/${encodeURIComponent(runKey)}/review`, { limit, name })
export interface DiscQueue { name: string; run_key: string; run_group_id: number; n: number; created_at: string; source: string; blind: boolean; writes: string }
export const getDiscoveryQueues = () => req<DiscQueue[]>('/api/discovery/queues')

export interface DiscRoleCell { index?: string; name: string; param: string; signature: string; glyph: string; algorithm?: string | null }
export interface DiscSide {
  run: string; label: string; subtitle: string; isSeed: boolean
  cells: Record<string, DiscRoleCell | null>
  precision: number | null; reviewed: number; xNull: number | null; threshold: number | null; found: number
}
export interface DiscOverlapRow { channel: string; onlyA: number; both: number; onlyB: number }
/** `otherNearest` is null in the list: the other side's score at a place is a
 *  per-window computation, returned as `bScore` by /compare/window. */
export interface DiscDisagreement {
  kind: 'only A' | 'only B'; channel: string; atH: number; index: number; end: number
  detection: string; score: number | null; otherNearest: number | null
  otherThreshold: number | null; otherIsSeed: boolean
}
export interface DiscCompare {
  a: DiscSide; b: DiscSide; differing: string[]
  overlap: DiscOverlapRow[]; total: DiscOverlapRow
  disagreements: DiscDisagreement[]; disagreementsTotal: number; disagreementsCapped: boolean
  sortedBy: string; both: { channel: string; atH: number; iou: number }[]
  attributable: boolean; attributionNote: string | null
  stageDiff: unknown[]; rule: DiscMatchingRule; channels: string[]
}
export const getDiscoveryCompare = (a: string, b: string, channels: string[], t0: number, t1: number, limit = 400) =>
  req<DiscCompare>(`/api/discovery/compare${dq({ a, b, channels: channels.join(','), t0, t1, limit })}`)

export interface DiscCompareWindow {
  t0H: number; windowS: number; stepS: number; values: (number | null)[]
  aSpan: [number, number] | null; bSpan: [number, number] | null
  aScore: (number | null)[]; bScore: (number | null)[]; scoreNote: string | null
  minAt: number | null; otherThreshold: number | null; channel: string; detection: string | null
}
export const getDiscoveryCompareWindow = (a: string, b: string, channel: string, atH: number, kind: string, windowS = 240, detection?: string) =>
  req<DiscCompareWindow>(`/api/discovery/compare/window${dq({ a, b, channel, atH, kind, windowS, detection })}`)

export type DiscThumb =
  | { kind: 'trace'; values: (number | null)[]; ghost?: (number | null)[]; stroke?: string; span?: [number, number] | null; emptyTrack?: boolean }
  | { kind: 'distance'; values: (number | null)[]; threshold: number | null; minIndex: number; minValue: number | null; isSeed: boolean }
  | { kind: 'symbols'; values: number[]; lowRun: [number, number] | null }
  | { kind: 'absent' }
export interface DiscStageCell {
  role: string; cell: DiscRoleCell | null; badge: string; thumb: DiscThumb
  caption: string; decided: string; absentNote?: string | null; error?: string
}
export interface DiscStages {
  d: { kind: 'only A' | 'only B'; channel: string; atH: number; detection: string | null }
  index: number; of: number; firstDiffering: string | null
  a: DiscStageCell[]; b: DiscStageCell[]; aSubtitle: string; bSubtitle: string; windowS: number; note: string
}
export const getDiscoveryCompareStages = (a: string, b: string, channel: string, atH: number, kind: string, index: number, of: number, windowS = 240, detection?: string) =>
  req<DiscStages>(`/api/discovery/compare/stages${dq({ a, b, channel, atH, kind, index, of, windowS, detection })}`)

/* ---------------- library (server/library.py, 20 routes under /api/library) ----------------
   Route-shaped types only. The Library pages read the fixture-shaped module
   api/library.ts, which maps these onto the shapes the cards render; nothing
   here renames a field or invents one the server declined to give.
   Named `…Library…` on purpose: `getTemplates` above is a DIFFERENT, id-keyed
   template shape, and these are mapped onto the Library's name-keyed one. */

export interface LibCounts { motifs: number; windowSets: number; templates: number; spikeTrains: number; sequences: number }
export const getLibraryCounts = () => req<LibCounts>('/api/library/counts')

export interface LibGrouping {
  id: string; unit: 'motifs' | 'sequences' | 'spike-trains'; basis: string; basisLabel: string; params: string
  chip: [string, string]; computed: string
  motifs: number; families: number; omitted: number; handEditsKept: number
  name?: string | null; method?: string | null; cut?: number | null; recipeHash?: string | null; actor?: string | null; note?: string
}
export const getLibraryGroupings = () => req<LibGrouping[]>('/api/library/groupings')

export interface LibCell { perHour: number | null; count: number; artifact?: boolean; noCoverage?: boolean }
export interface LibFamily {
  id: string; name: string; colour: string; shape: string
  members: number; inScope: number; recordings: number; hand: number; artifact: number
  durationS: number; durationSd: number; depthMv: number; depthLabel: string
  judgedPct: number; judged: number
  exemplar: string; medoid: string; exemplarMedoidD: number; meanMemberD: number; snrDb: number
  artifactChannels: number; propChannels: number; indChannels: number; edges: string
  cells: Record<string, LibCell>; exemplarTrace: number[]; medoidTrace: number[]
  ampBins: number[]; ampDomain?: [number, number]; grouping?: string
}
export interface LibRecGroup {
  key: string; label: string; hours: number; reviewedPct: number; channels: string[]
  hiddenChannels: number; fsNote?: string; heldOut?: boolean; resampleOf?: string
}
export interface LibRecurrence {
  recordings: LibRecGroup[]; families: LibFamily[]; coverage: Record<string, number>
  sharedGround: { pair: [string, string]; family: string }[]; grouping: string | null
}
export const getLibraryRecurrence = (grouping?: string) => req<LibRecurrence>(`/api/library/recurrence${dq({ grouping })}`)
export const getLibraryFamilies = (grouping?: string) => req<LibFamily[]>(`/api/library/families${dq({ grouping })}`)

export interface LibSequenceFamily {
  id: string; name: string; colour: string; sequences: number
  composition: string[]; compositionLabel: string; recordings: number; hand: number
  durationLabel: string; gapLabel: string; judgedPct: number
  exemplar: string; motifs: number; exemplarMedoidD: number; orderKept: number
  meanMemberD: number; judgedMotifs: number; gapS: string
  exemplarTrace: number[]; medoidTrace: number[]
}
export const getLibrarySequenceFamilies = (grouping?: string) =>
  req<LibSequenceFamily[]>(`/api/library/sequence-families${dq({ grouping })}`)

export interface LibRevision { rev: number; spanId: string; origin: 'machine' | 'human edit'; run: string; role: string }
export interface LibMember {
  id: string; role?: 'exemplar' | 'medoid'; addedByHand?: boolean; d: number
  recording: string; recordingKey?: string | null; channel: string
  onsetH: number; durationS: number; amplitudeMv: number
  verdict: string; verdictAt?: string; foundBy: string
  revisions: LibRevision[]; tags: string[]; cls?: string; note?: string; seed: number
  handRecord?: string; contentHash?: string | null
}
export interface LibRemovedMember {
  id: string; d: number; channel: string; recording: string; recordingKey?: string | null
  removedAt: string; note: string; seed: number; onsetH?: number | null; contentHash?: string | null
}
export interface LibFamilyDetail {
  family: LibFamily; cut: number; members: LibMember[]; removed: LibRemovedMember[]
  channels: number; depthLabel: string; handAdded: number
}
export type LibFamilyRead =
  | { kind: 'motif'; detail: LibFamilyDetail }
  | { kind: 'sequence'; family: LibSequenceFamily }
  | { kind: 'missing'; id: string }
export const getLibraryFamily = (familyId: string, grouping?: string) =>
  req<LibFamilyRead>(`/api/library/family/${encodeURIComponent(familyId)}${dq({ grouping })}`)

export interface LibOmittedEntry {
  id: string; kind: 'motif' | 'sequence'; nearest: string; d: number
  recording: string; recordingKey?: string | null; channel: string; onsetH: number
  shape: string; amp: number; seed: number; omitReason?: string | null
}
export interface LibOmitted { groupingId: string | null; singles: LibOmittedEntry[]; sequences: LibOmittedEntry[] }
export const getLibraryOmitted = (grouping?: string) => req<LibOmitted>(`/api/library/omitted${dq({ grouping })}`)

export interface LibFeatureBin { lo: number; hi: number; n: number }
export interface LibUnitOption { unit: 'motifs' | 'sequences' | 'spike-trains'; caption: string; count: number }
export interface LibBasisOption {
  kind: string; group: 'distance' | 'feature bins · no distance' | 'labels'
  title: string; caption: string; units: ('motifs' | 'sequences' | 'spike-trains')[]; reason?: string
}
export interface LibGroupingEditor {
  units: LibUnitOption[]; bases: LibBasisOption[]
  distributions: Record<string, LibFeatureBin[]>
  clusterings: { value: string; label: string; scope: string }[]
  distributionsSampledFrom: number; elapsedMs: number
}
export const getLibraryGroupingEditor = (unit = 'motifs') =>
  req<LibGroupingEditor>(`/api/library/grouping-editor${dq({ unit })}`)

export interface LibWindowSet {
  id: string; version: number; saved: string; savedBy: string; source: string
  recording: string; recordingKeys: string[]; channels: string[]
  spacing: string; windowS: number | null; gapS: number | null; windows: number
  split: { train: number; validation: number; test: number } | null
  splitLabel: 'blocked' | 'test only' | 'no split'
  labelledPct: number; labelledWindows: number
  usedBy: { label: string; to: string; kind: string }[]; usedLabel: string | null
  check: string; checkReason: string; madeBy: string; recipeHash: string; lastUsed: string
  splitPlan: Record<string, unknown>
  planHours: number; dropped: number
  spacingChecks: { label: string; ok: boolean }[]
  classCounts: { now: Record<string, number>; atSave: Record<string, number>; atSaveLabelled: number }
  path?: string | null
}
export const getLibraryWindowSets = () => req<LibWindowSet[]>('/api/library/windowsets')

export interface LibTemplateStage { glyph: string; name: string; params: string }
export interface LibTemplate {
  name: string; version: number; kind: string; signature: string
  badges: { label: string; tone: 'purple' | 'blue' | 'grey' }[]
  stages: LibTemplateStage[]; recipe: string; nullModel: string; containsModel: boolean
  latest: { text: string; scope: string } | null; latestMuted?: string
  runs: string; runCount: number; lastRun: string
  versions: { v: number; change: string; date: string; diff?: { param: string; from: string; to: string }[] }[]
  scores: { run: string; scope: string; scopeFull: string; prec: number | null; recall: number | null; xNull: number | null }[]
  scoreHeader?: [string, string, string]
  id?: number
}
export const getLibraryTemplates = () => req<LibTemplate[]>('/api/library/templates')

export interface LibSequence {
  id: string; sequenceKey: string; origin: string; recording: string; recordingKey: string | null
  channel: string; onsetH: number; nEvents: number; needsExtraction: boolean
  sourceKind: string | null; sourceStore: string | null; createdAt: string | null
}
export const getLibrarySequences = (needsExtraction = false) =>
  req<LibSequence[]>(`/api/library/sequences${dq({ needs_extraction: needsExtraction ? 1 : 0 })}`)

export interface LibGroupingRunBody { unit?: string; basis?: string; method?: string; params?: Record<string, unknown>; name?: string; limit?: number }
export const runLibraryGrouping = (body: LibGroupingRunBody) =>
  post<{ job_id: number; kind: string; status: string }>('/api/library/groupings/run', body)

export interface LibGroupingAssignment {
  ref: number; contentHash?: string | null; familyId?: number | null; familyLabel?: string | null
  distance?: number | null; isMedoid?: boolean; omitReason?: string | null
}
export interface LibGroupingSaveBody {
  unit?: string; basis?: string; method?: string; params?: Record<string, unknown>
  cut?: number | null; name?: string; actor?: string; assignments: LibGroupingAssignment[]
}
export const saveLibraryGrouping = (body: LibGroupingSaveBody) => post<LibGrouping>('/api/library/groupings', body)

export interface LibImportCheck { status: 'ok' | 'warn' | 'fail'; title: string; detail: string; items?: string[]; link?: { label: string; to: string } }
export interface LibImportSample {
  id: number; recording: string; channel: string; onsetH: number; durationS: number
  shape: string; amp: number; seed: number; provisional: boolean
}
export interface LibImportBundle {
  path: string; provenanceFound: boolean
  counts: { motifs: number; spikeTrains: number; recordings: number; channels: number }
  checks: LibImportCheck[]; creates: string[]; sample: LibImportSample[]
  blockedReason?: string; heldOut?: boolean; kind?: string
}
export const dryRunLibraryImport = (path: string, kind?: string, exclude_corpora?: string[]) =>
  post<LibImportBundle>('/api/library/import/dry-run', { path, kind, exclude_corpora })
export const startLibraryImport = (path: string, kind?: string, exclude_corpora?: string[]) =>
  post<{ job_id: number; kind: string; status: string }>('/api/library/import', { path, kind, exclude_corpora })

export interface LibBundleRef { path: string; name: string; kind: string; registeredAt: string | null; heldOut: boolean }
export const getLibraryImportBundles = () => req<LibBundleRef[]>('/api/library/import/bundles')

export interface LibHandEditBody { contentHash: string; kind: string; familyLabel?: string | null; value?: string | null; grouping?: string | null; actor?: string }
export const postLibraryHandEdit = (body: LibHandEditBody) =>
  post<{ id: number } & Record<string, unknown>>('/api/library/hand-edits', body)
export const deleteLibraryHandEdit = (editId: number) =>
  del<{ id: number; active: number; undone: boolean }>(`/api/library/hand-edits/${encodeURIComponent(String(editId))}`)

/** Download URLs — these are attachments (Content-Disposition), so they are
 *  handed to the browser, not fetched and parsed. */
export const libraryFamilyExportUrl = (familyId: string, grouping?: string, format: 'json' | 'csv' = 'json') =>
  `/api/library/export/family/${encodeURIComponent(familyId)}${dq({ grouping, format })}`
export const libraryAtlasExportUrl = (grouping?: string, format: 'json' | 'csv' = 'json') =>
  `/api/library/export/atlas${dq({ grouping, format })}`
