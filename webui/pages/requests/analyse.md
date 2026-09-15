# Shared-code requests — Analyse › Chain builder

- **Jobs: read HPC jobs created in Analyse** · where: `src/jobs/` (Jobs builder) · what: list jobs written by
  `recordDemoWrite('jobs', 'add-job', { id, kind: 'cluster', title, status: 'queue', detail, for })` (read with
  `useDemoWrites('jobs')`), or agree a shared demo key (Analyse also writes `setDemo('analyse.hpcJobs', [{ id, title }])`)
  · why: frame chain-1g "Create SLURM script" / P24 — the HPC job must appear in Jobs. Worked around: the write is made
  and a toast links to Jobs.
- **kit Popover max-width** · where: `kit/kit.css` `.k-popover { max-width: min(560px, …) }` · what: let `width` win over
  the 560 px cap (or add a `wide` flag) · why: the run-history pop-up (frame chain-1b) is ~940 px. Worked around with an
  inline `style.maxWidth`.
- **charts/useSize re-observes when its element changes** · where: `src/charts/useSize.ts` · what: the effect runs once
  (`[]` deps), so a component whose measured element is unmounted and re-mounted (a chain row switching from an
  error/HPC card back to a plot) keeps width 0 and paints nothing · why: silent blank pane (loud-failure rule). Worked
  around in `analyse/ChainRow.tsx` by moving the plot surface into its own component; other users of `useSize` that
  conditionally render the measured element have the same trap. **Resolved upstream 2026-09-16** (useSize now re-binds
  on element swap); the ChainRow split is kept, harmless.
- **kit Modal footer spacer** · where: `kit/surfaces.tsx` Modal footer · what: a `footerStart` slot for a left-aligned
  button (frame chain-1c "Import .json file", chain-2 registry count) · why: `footerNote` is styled as muted text.
  Worked around by passing a Button as `footerNote`.
