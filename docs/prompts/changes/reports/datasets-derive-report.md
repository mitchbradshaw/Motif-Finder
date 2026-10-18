WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\agent-a93877ac934d1979d
BRANCH: worktree-agent-a93877ac934d1979d

# datasets-derive: report

## In plain words

A recording is a long list of voltages taken at regular ticks. Before anyone can use one, two things must be known:
how often the ticks came (the sampling rate) and what the numbers are measured in (volts or millivolts). Two scripts
now settle both and refuse to write anything when they are unsure.

- `scripts/derive_mju26a_fs10.py` puts MJu26a's unevenly spaced samples onto an even 10-per-second clock as a new
  recording, `MJu26a_fs10`. Before it writes anything, it checks that each L_LM channel really is a ×1000 copy of
  one MJu26a channel. It does this by sliding the two against each other and asking whether they match almost
  perfectly. If they do, it records the link, so Review can draw L_LM's shapes from the parent. If they do not, it
  prints the scores and writes nothing.
- `scripts/derive_raw_mat.py` turns any raw MATLAB matrix (CO, LM, SH, SO, F2B, L_R_Aug_26_PD_raw) into channel
  files and registers them.

**Stop condition partly met.** The MATLAB time object cannot be read without a new dependency: the six files'
clocks are `MatlabOpaque` objects, which scipy reads but cannot decode. I wrote `scripts/export_mat_time.m` for the
local MATLAB to export them, as the prompt says. I also built the fallback that does not need it: the
whole-days-at-10 Hz count rule, labelled "inferred, not read". So the scripts are complete either way.

## Assumed

- **`MJu26a_fs10`'s `source_file` is `MJu26a_fs10.mat`.** `recordings` is `UNIQUE(source_file, channel)` and a
  recording's identity is its source file. Reusing `MJu26a.mat` would collide with the old rows. The manifest names
  the real raw file (`raw_file: DATA/raw/MJu26a.mat`, `derived_from`).
- **The old `MJu26a.mat` rows stay active.** I found no "mark inactive" on the Datasets page beyond unregister, and
  the prompt says to keep them. They are declared V too.
- **`t` is in seconds.** The script switches to days ×86400 only on a MATLAB datenum signature (first value
  7e5–8e5 and a step under 0.01 d). `--t-unit` overrides this. The dry run prints `t[0]`, the span in h and d, and
  the dt statistics, so the manager can see whether the span is the expected ≈ 636 h.
- **Alignment.** I correlate high-passed signals (each minus a 601-sample, 60 s moving mean) because the slow drift
  is shared across channels. The search covers 3 windows (25 / 50 / 75 % through the child), each `--window` 10,000
  samples. The offset range is ±(36,000 + |grid length − child length|). *(Superseded in the critic round, below:
  the three best parents are refined to a fractional offset; a link needs refined r ≥ 0.95, 0.1 above the next
  parent, and one offset within half a sample on all three windows.)* The five children must choose distinct
  parents. A negative offset (child starts before parent) is refused because `parent_offset` cannot represent it
  (except under one sample, which links at 0). Gain and intercept come from a raw-signal fit and are printed
  (expect ≈ 1000).
- **The registry's automatic excerpt rule must not re-point existing links.** Registering a new stem can link
  short registered rows (for example Mushroom_260720, whose parent is L_LM CH2) to it. Rows that already have a
  parent keep it, and the script prints each such case. The rows the script links itself are also excluded from
  that rule. Without this, registering `MJu26a_fs10` would silently move Mushroom's parent from L_LM to MJu26a.
- **Rate rule.**
  - 10 Hz is the only rate the count rule accepts ("the lab's logging rate"). CO's 17,280,001 is also whole days at
    1, 2, 5 and 20 Hz. The note lists those alternatives and says the lab rate was taken.
  - An uneven time axis without `--fs` refuses.
  - A `--fs` stated with no time axis is recorded as `fs_source = inferred`.
- **Unit rule.** Let m be the 99th percentile of |samples|. m ≤ 2 gives V, 20 ≤ m ≤ 5000 gives mV, and anything
  else refuses without `--units`.
- **Display names.** The display name is the file stem without `_raw` (so `L_R_Aug_26_PD_raw` becomes
  `L_R_Aug_26_PD`). For MJu26a_fs10 it is `MJu26a (10 Hz)`.
- **Where the MATLAB export goes.** `export_mat_time.m` writes to `DATA/derived/time_axes/<stem>_time.mat`, not
  beside the raw file, because Settings › Datasets would list a file there as a raw recording. The Python reads
  that directory, a sibling file, or `--time-file`.
- **`units.py` is untouched.** Declaration goes through the existing `declare_units`, and the manifest's `units`
  text carries the reason into `units_note`.

## Files

- `scripts/derive_raw_mat.py` (new).
- `scripts/derive_mju26a_fs10.py` (new).
- `scripts/export_mat_time.m` (new). Untested: I did not run MATLAB on a shared machine with about 3 GB free.
- `Working/registration/kinds.py`: appended `link_parent(conn, child_id, parent_id, offset, decimation)`. It is the
  explicit link for a child too long for the excerpt rule (that rule caps at 200,000 samples, and L_LM has 22.9 M).
  It checks rate = decimation × child rate, 0 ≤ offset < parent length, and no self-link, and returns any
  overhang. It does not commit.
- `tests/test_derive_raw_mat.py`, `tests/test_derive_mju26a_fs10.py`, `tests/_derive_fixtures.py` (new). The
  fixtures include a v5 writer and a MATLAB-shaped v7.3 writer built with h5py.
- `docs/datasets/NEW_RAW_2026-10.md` (new): a table for the manager to fill in from the real runs.

## Tests (conda interpreter, `/c/ProgramData/anaconda3/python.exe`)

- **Red:** `1b8774b`, 2 collection errors because the scripts did not exist.
- **Green:** `7629cc2`. The new test files plus `test_import_boundaries`, `test_registration_recording`,
  `test_registration_artifacts`, `test_registration_settings` and `test_recording_units` give 84 passed.
- **What the tests pin:**
  - `N = d·864000 + 1` gives 10 Hz with the note "inferred from the sample count, not read".
  - 3,851,550 refuses and prints 4.46 d at 10 Hz and 44.6 d at 1 Hz.
  - Values in ±1 give V, values in the hundreds give mV, and values in between refuse.
  - A one-day 10 Hz v5 file is derived, registered (fs_source inferred, units V with its note) and given its
    display name.
  - A v7.3 file is oriented correctly and gives mV.
  - An uneven `t` with `--fs 10` is interpolated exactly; the manifest's `resampling` carries the method, the dt
    min/median/max and the extrema warning.
  - An uneven `t` without `--fs` refuses.
  - The exported `<stem>_time.mat` gives a read 1 Hz.
  - A `--fs` that contradicts a uniform axis refuses.
  - An ambiguous count refuses, then derives with `--fs`.
  - Two candidate matrices need `--variable`.
  - `--dry-run` leaves the file tree and the database bytes unchanged.
  - A second run refuses.
  - MJu: the uniform grid equals `np.interp`; datenum days convert to seconds; uneven `t` → 10 Hz stem; rows are V;
    the old rows are declared V; two children are linked to the right parents at offset 1,234 with decimation 1;
    a non-correlating child is refused with nothing written (tree, rows and links unchanged); the dry run writes
    nothing and prints the offset; an existing stem refuses; `link_parent` rejects a rate mismatch and a negative
    offset.

## What the manager runs, in order (main checkout, conda python)

*(Rewritten in the critic round.)* Run from `C:\Users\mmebr\Documents\CNN` with
`PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/...`. The researcher's bridge may keep the
database open: every real run is one SQLite transaction per derived stem (30 s busy timeout), so a lock or any
other failure after the files are written prints `ROLLED BACK every database write ... and removed <stem dir>`,
exits 3, and a rerun starts clean. Nothing to clean by hand except a `.staging_<stem>_<pid>` directory if a run
is killed (Ctrl-C, out of memory) mid-write; the next run refuses and names it.

1. `python scripts/derive_mju26a_fs10.py --dry-run` (read-only DB; ~0.5 GB; about a minute)
   - **Prints:** M 16 channels × 14,722,842; `t` as seconds with t[0], a span of about 636 h / 26.5 d, dt min
     0.124 / median 0.138 / max 2.83; a grid of about 22.9 M samples; the child as 5 channels × 22,892,769; a 5 × 16
     table of whole-sample r; one `link` line per L_LM channel with offset, phase, refined r (≈ 1.0 if L_LM is a
     linear interpolation of the same `t`), the next parent's r and a gain of about 1000; `dry run: nothing
     written`; exit 0.
   - **`note ... is not a linear interpolation of the same t`:** L_LM was made another way (e.g. sample-and-hold);
     the link still stands on separation and a constant offset, to the nearest sample. Record it in the note.
   - **`REFUSED`** (exit 2): paste the table and the `problem` lines into the report and stop the MJu part; the
     researcher decides (`--skip-link` derives MJu26a_fs10 without the link).
   - **Span not ≈ 636 h:** `t` is in another unit; rerun with `--t-unit days` (or `s`).
2. `python scripts/derive_mju26a_fs10.py` (writes 16 × ~183 MB = 2.9 GB; peak ~1 GB; a few minutes, longer if
   the registry's excerpt check meets many short rows)
   - **Prints:** the same as step 1, then `registered 16 rows`, `declared V on the old MJu26a.mat rows`, display
     name 'MJu26a (10 Hz)', 5 `linked` lines, any `kept` lines (Mushroom_260720 keeps its L_LM parent), `wrote`.
3. **If MATLAB is available (recommended: the researcher asked for the rate to be READ where possible):**
   `matlab -batch "addpath scripts; export_mat_time()"` writes `DATA/derived/time_axes/<stem>_time.mat`, read-only
   on the raw files, and prints one line per file (variables; `t0`, `dur_s` or `t_s` with dt stats).
4. `python scripts/derive_raw_mat.py CO LM SH SO F2B L_R_Aug_26_PD_raw --dry-run` (read-only DB; one matrix in
   memory at a time, CO ~0.6 GB, ~1 GB with a read time axis)
   - **Without step 3:** CO/LM/SH/SO 10 Hz inferred (20 d), V, stems `*_fs10`; F2B 10 Hz inferred (6 d), mV;
     L_R `REFUSED` with the 10 Hz and 1 Hz durations; exit 2.
   - **With step 3:** each file says `read from <stem>_time.mat` and `uniform`, or `UNEVEN` → refused until
     `--fs 10` is passed for that file (then it is interpolated, as MJu26a). A file whose export holds only a
     start time falls back to the count rule and prints the start time.
   - **Any variable line or unit that looks wrong:** stop.
5. `python scripts/derive_raw_mat.py CO LM SH SO F2B` (add `--fs 10` per file only where step 4 said UNEVEN):
   `registered 4/4/4/4/5 rows`, display names, exit 0. Writes 4 × 138 MB per 20-day file, 5 × 41 MB for F2B.
6. `L_R_Aug_26_PD_raw` only once its rate is read (step 3) or stated by the researcher (`--fs <Hz>`).
7. Restart the project bridge (it caches recordings), then fill in `docs/datasets/NEW_RAW_2026-10.md`.

## Open questions and risks

- L_LM's grid phase or method: handled by the fractional-offset refinement (critic round); a non-linear copy links
  with a printed note.
- Memory (critic measurement: traced, extrapolated from 1–3 M-sample synthetic runs): MJu dry run ~0.5 GB; MJu
  real run ~1 GB peak (one channel, its grid and the time vector); `derive_raw_mat` ~1.1 × the matrix (CO ~0.6 GB),
  one file at a time.
- `export_mat_time.m` has not been executed (no MATLAB run here).
- Old analysis results on `MJu26a.mat` stay on the old, unevenly sampled rows; nothing migrates them.

## Critic round (2026-10-18)

Reviewed the branch at `b391648` against the prompt, with the real run on the researcher's live database in mind.

1. **Blocker: the L_LM link would have refused on the real data.** A simulation of the real situation (uneven
   `t`, dt 0.124–2.83 s, median 0.138 s; child = ×1000 linear interpolation on a 10 Hz grid whose origin is 0.3 /
   0.5 sample from ours, as MATLAB's `retime` gives) found whole-sample r of 0.971 / 0.916 / 0.950 for the RIGHT
   pair (wrong pairs 0.22–0.37) and window offsets 120/120/121, so the 0.999 rule refused. Fixed: the three best
   parents are refined to a fractional offset. Refined r is 1.0000 for every linear copy, 0.997 for a pchip copy
   and 0.966 for sample-and-hold, all linked; wrong pairs are unchanged. The rule is refined r ≥ 0.95, ≥ 0.1 above
   the next parent, and one offset (± 0.5 sample) on all three windows. Tests cover a shifted child (0.3, 0.5) and
   a child that starts 0.7 sample before ours. Timing: 7 children × 16 parents in 21 s on a 400 k-sample synthetic.
   The search reads only about 80 k samples per parent per window, so the real run costs about the same.
2. **Blocker: not atomic.** `register()`, `append_audit()` and `put_dataset()` commit on their own. A failure
   after registration (a locked database at link time, a display-name write) left 16 registered rows, no links,
   and a stem that the next run refused on, so the only way forward was hand-deleting rows. Fixed with a `Deferred`
   connection: one transaction per stem, with rollback and stem removal on any failure. The tests inject a lock at
   `link_parent` and at `put_dataset`, then rerun cleanly.
3. **Should-fix: absolute `npy_path`.** Rows registered from an absolute root carry `C:/Users/.../DATA/...`. The
   convention is repo-relative (`runtime.py` chdirs for it), and absolute paths break every copy of the database
   (cluster, sandbox). Fixed: a root inside the repo is registered repo-relative. Tested on the helper.
4. **Should-fix: memory.** `derive_raw_mat` kept the previous file's matrix while loading the next (2 × 553 MB on
   the six-file run). MJu kept both `t` and `t − t0`, and built the grid once per channel. Fixed; the measured
   peaks are above.
5. **Should-fix: a killed run left `.staging_*` (up to 2.9 GB) silently.** It is now refused, with the path to
   delete.
6. **Should-fix: the MATLAB export.** It exported only the first time object. A scalar `datetime` (a start time)
   became a one-element `t_s` that the deriver refused on, blocking even the count rule. Every time object is now
   exported (`t0`, `t_s`, `dur_s`) via `save -struct ... -v7.3`, and a file with only a start time falls back to
   the count rule. Test added.
7. **Coverage: the kept parent link.** The test registers a 1 Hz excerpt of L_LM (as Mushroom_260720 is). It
   proves the excerpt rule would re-point that row to MJu26a_fs10, and that the run keeps the existing parent. It
   fails with the protection removed.

Not changed: `fs_token` and `resample_uniform` restate `derive_dwij_mfs2`'s rules, because that module chdirs on
import. `link_parent` is minimal and tested, `init_db` is untouched, and there is no schema change.

**Commits:** `34e4e92` (failing tests), `24f1628` (fixes), and this report.

**Gate** (conda, one file at a time): `test_derive_mju26a_fs10` 11, `test_derive_raw_mat` 19,
`test_import_boundaries` 4, `test_registration_recording` 19, `test_registration_artifacts` 14,
`test_registration_settings` 10, `test_recording_units` 15. Total 92 passed, 0 failed.
