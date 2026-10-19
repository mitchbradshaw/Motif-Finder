/* Reports reads and writes (webui/server/reports.py, docs/prompts/changes/reports.md) — all live.
 *
 *  · a detection run's report, rendered by the server with matplotlib from the live database
 *    (`GET /api/reports/detection-run/<key>`): the HTML the page shows, the Markdown, the twelve examples;
 *  · Save snapshot (`POST …/snapshot`): report.html, report.md and the PNGs under the results folder;
 *  · the saved snapshots (`GET /api/reports`), one file of one (`…/files/<name>`), open its folder. */
import { ApiError, fetchBridge, READ_TIMEOUT_MS } from '../api'

export interface ReportExample { detectionId: number; channel: string; pick: 'top' | 'random'; atH: number; score: number | null; verdict: string | null }
export interface DetectionRunReport {
  kind: 'detection-run'; runKey: string; title: string; subtitle: string
  /** the report body as one `<div class="ub-report">` with its own style, figures inline, no script */
  fragment: string
  /** the same as a whole page (what Print and "open in a tab" show) */
  html: string
  markdown: string; figures: string[]; examples: ReportExample[]
}
export interface SavedSnapshot { id: number; path: string; files: string[]; markdown: string; html: string }
export interface ReportRow {
  id: number; kind: 'detection-run' | 'chain-run' | string; runKey: string | null; runId: number | null; sessionId: number | null
  title: string | null; createdAt: string; path: string; note: string | null
  /** false when the folder (or its report.html) is no longer on disk */
  exists: boolean
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const write = !!init?.method && init.method !== 'GET'
  const r = await fetchBridge(path, { headers: { 'content-type': 'application/json' }, ...init }, write ? null : READ_TIMEOUT_MS)
  if (!r.ok) {
    let body: any = null
    try { body = await r.json() } catch { /* not json */ }
    const msg = body?.error ?? (typeof body?.detail === 'string' ? body.detail : body?.detail?.message) ?? `${r.status} ${r.statusText}`
    throw new ApiError(r.status, msg, body?.detail ?? body, body?.traceback)
  }
  return r.json() as Promise<T>
}

const enc = encodeURIComponent

export const getDetectionRunReport = (runKey: string) => call<DetectionRunReport>(`/api/reports/detection-run/${enc(runKey)}`)
export const detectionRunReportPageUrl = (runKey: string) => `/api/reports/detection-run/${enc(runKey)}/html`
export const saveDetectionRunSnapshot = (runKey: string, note?: string) =>
  call<SavedSnapshot>(`/api/reports/detection-run/${enc(runKey)}/snapshot`, { method: 'POST', body: JSON.stringify(note ? { note } : {}) })
export const listReports = () => call<ReportRow[]>('/api/reports')
export const reportFileUrl = (id: number, name: string) => `/api/reports/${id}/files/${enc(name)}`
export const openReportFolder = (id: number) => call<{ opened: string }>(`/api/reports/${id}/open-folder`, { method: 'POST', body: '{}' })
