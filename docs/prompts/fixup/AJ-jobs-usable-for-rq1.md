# Fixup AJ — the Jobs page, to the point where RQ1's cluster jobs can be run from it

**Fifth of five for RQ1 version 2. Runs after `AI`.** Written 2026-10-05; nothing here is run yet. Scope is set by one
question, not by the page's full specification: *can the researcher send RQ1's two cluster jobs out and get them back
without a command line?*

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` ("New scope, version 2"),
`reports/AI-cnn-arm-slurm.md`, `docs/prompts/fixup/09-jobs.md`, `Working/manifest.py` and `Working/hpc/job_export.py`.

Commit prefix `fixup-aj:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only. The
site does not log in to the cluster or submit anything; the researcher copies and runs.**

## In plain words

Jobs is still a demo page. `AI` leaves two scripts the site can write — a CNN training job and a Ward clustering over
every window — and a command that brings their results back. This prompt puts that on the Jobs page: what is running
here, which scripts were written and what to copy with them, and a place to hand back what the cluster returned.

## Decided (the researcher, 2026-10-05)

- **Finish Jobs only as far as it is needed to run this research question.** Anything the page's specification asks
  for beyond that stays for its own prompt and stays marked as demo.

## What to build

1. **Real rows in place of the fixture list:** local jobs from the bridge's own job table (training, clustering,
   window-set builds — state, stage, progress, started, duration, error with its traceback), and **exported jobs**:
   every SLURM script the site wrote for RQ1 (`AI`'s two kinds), with its recipe hash, when it was written, the list
   and size of what must be copied to the cluster, and its state: *written · results imported · import refused (why)*.
2. **Manifest inbox, minimally:** point it at a returned results directory → validated against the recipe hash through
   the same function as `AI`'s `import-results` (one implementation, two callers) → the run, artifacts and model are
   recorded and the exported job's row links to Models › Results (CNN) or to the Analyse chain whose tree it replaces
   (full-pool Ward). A mismatch is refused with the reason; nothing is half-imported.
3. **Honest edges:** the parts of Jobs still on fixture data keep their `demo data` chip; Models' link stops saying
   "Jobs (demo page)" only for what is now real.

## Leave alone

| Leave alone | Why |
|---|---|
| Submitting to, polling or reading from the cluster | out of scope; no credentials in the site |
| Discovery's sweeps and their SLURM scripts on this page, unless they come for free from the same table | not needed for RQ1 — say what came for free |
| The CNN arm, the scripts themselves | `AI` |

## Acceptance — the researcher's walk

1. Train a forest locally from Models › Launch → Jobs shows it running, then finished.
2. *Create SLURM script* for the CNN arm → Jobs lists it as *written*, with what to copy.
3. Hand Jobs the directory `AI`'s local smoke produced, as if returned from the cluster → *results imported* → the row
   opens the run in Models › Results. A directory from a different recipe is refused with the reason.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge; `pytest` against the README baseline;
`tests/test_import_boundaries.py`. Evidence into `webui/screenshots/fixup/AJ/`.

## Report

`docs/prompts/fixup/reports/AJ-jobs-usable-for-rq1.md`, opening in plain words: the walk, what on Jobs is now real and
what still wears `demo data`, items left for the page's own prompt, the gate. **Before you report, update**
`docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` per that folder's README. Any question to the researcher: plain
language first, then options, then a recommendation.
