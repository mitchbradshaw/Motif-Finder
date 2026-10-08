# Fixup 09 — Jobs: All jobs, Paused run, Upload and continue, Cluster job

**Status: overtaken (2026-10-09, `fixup-jobs`).** Jobs is one real board — *In progress here* (the bridge's job table), *Waiting on the cluster* (every script the site wrote, from the job folders, Discovery's seed run rows and the flat recipe scripts; `GET /api/hpc/cluster`), *Waiting in review* (the open queues) and the Manifest inbox — and the three fixture sub-pages (paused run, upload-and-continue, hand-marked cluster job) are gone with their store and fixtures. Of the symptoms below, J1, J2, J4 and J5's listing are closed; **J3 (a paused run continued from a placed stage result) and J6 (a between-target cancel) remain open** — the core has no paused run to continue, and a cluster job's status is read from its folder, its result file and the database, never marked by hand.

*Symptoms as written on 2026-10-05, kept for the record:*

## Symptoms

| # | Symptom | Evidence |
|---|---|---|
| J1 | **`api/jobs.ts` holds 6 fixture reads and every page wears the "demo data" chip.** | wiring `reports/05-review.md` §7 |
| J2 | **What exists to wire against**: the job model in `webui/server/jobs.py` with SSE, cancel and restart-safe snapshots; `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/jobs/{id}/events`; `subscribeJob`/`subscribeRun` in `api.ts`; the core's own SLURM array exporter, which Discovery drove for real. The shell already polls `listRuns` for the live-jobs and need-you badges, so the data is one page away. | wiring `reports/01-analyse-blocks.md` §"Job model"; `reports/04-discovery.md` |
| J3 | **Jobs › Upload and continue was specified by Prompt 02 and never built**: continue the paused run from `paused_run_id`, with the **paused status vocabulary still a guess** (`paused \| waiting \| pending \| queued \| hpc` — one tuple to edit). | wiring `reports/02-settings-import.md` §"Requests written", Q7 |
| J4 | **Not every job is a chain run, and the app has already been bitten by assuming so.** Discovery's `sweep` jobs carry no recipe; `HistoryPopover` read `j.recipe.steps` for every live job and blanked the Analyse pane as soon as a Discovery run existed. Patched in place by skipping recipe-less jobs; **the design question — a route-side filter or a non-chain row — was left open.** A Jobs page that lists every job across workspaces meets this head-on. | wiring `reports/04-discovery.md` out-of-scope table; `requests/04-to-01.md` §5 |
| J5 | **Cluster-job status is hand-marked**, with a reminder, a script and a manifest inbox — none of it wired. The HPC path in the core is real (`Working/` HPC, the SLURM exporter); the inbox is not. | `webui/client/src/shell/pages.ts` (`jobs.cluster`) |
| J6 | **No between-target cancel for `fan_out_recipe`**, filed by Discovery: a fan-out cannot be stopped between targets. | wiring `requests/04-to-01.md` |

## Goal · Work · Testing and critique · Report

*(written after the questions)*
