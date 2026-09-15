# Shared-code requests — Analyse › Chain builder

- **Jobs: read HPC jobs created in Analyse** · where: `src/jobs/` (Jobs builder) · what: list jobs written by
  `recordDemoWrite('jobs', 'add-job', { id, kind: 'cluster', title, status: 'queue', detail, for })` (read with
  `useDemoWrites('jobs')`), or agree a shared demo key (Analyse also writes `setDemo('analyse.hpcJobs', [{ id, title }])`)
  · why: frame chain-1g "Create SLURM script" / P24 — the HPC job must appear in Jobs. Worked around: the write is made
  and a toast links to Jobs.
- **kit Popover max-width** · where: `kit/kit.css` `.k-popover { max-width: min(560px, …) }` · what: let `width` win over
  the 560 px cap (or add a `wide` flag) · why: the run-history pop-up (frame chain-1b) is ~940 px. Worked around with an
  inline `style.maxWidth`.
- **kit Modal footer spacer** · where: `kit/surfaces.tsx` Modal footer · what: a `footerStart` slot for a left-aligned
  button (frame chain-1c "Import .json file", chain-2 registry count) · why: `footerNote` is styled as muted text.
  Worked around by passing a Button as `footerNote`.
