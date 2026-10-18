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
  samples. The offset range is ±(36,000 + |grid length − child length|). A link needs r ≥ 0.999 on all three
  windows at the same offset, and the five children must choose distinct parents. A negative offset (child starts
  before parent) is refused because `parent_offset` cannot represent it. Gain and intercept come from a raw-signal
  fit and are printed (expect ≈ 1000).
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

1. `python scripts/derive_mju26a_fs10.py --dry-run`
   - **Prints:** the M shape (16 × 14,722,842); `t` read as seconds with t[0], a span of about 636 h / 26.5 d, and
     dt min 0.124 / median 0.138 / max 2.83; a grid of about 22.9 M samples; the child as 5 channels × 22,892,769;
     a 5 × 16 table of r; then one `link` line per L_LM channel with its offset and a gain of about 1000; then
     `dry run: nothing written` and exit 0.
   - **If it prints `REFUSED`:** paste me the table.
   - **If the span is not about 636 h:** `t` is in another unit; rerun with `--t-unit days`.
   - **If the best r is about 0.99 but below 0.999 at a consistent offset:** the grids differ by a fraction of a
     sample. Report it; do not lower `--min-r` without saying so.
2. `python scripts/derive_mju26a_fs10.py` writes 16 × about 183 MB.
   - **Prints:** `registered 16 rows`, `declared V on the old MJu26a.mat rows`, 5 `linked` lines, and any `kept`
     lines (Mushroom keeps its L_LM parent).
3. `python scripts/derive_raw_mat.py CO LM SH SO F2B L_R_Aug_26_PD_raw --dry-run`
   - **Prints:** CO/LM/SH/SO as 10 Hz inferred (20 days), V, stems `*_fs10`; F2B as 10 Hz inferred (6 days), mV;
     L_R as `REFUSED` with the 10 Hz and 1 Hz durations. Every file shows a `time` line naming the MatlabOpaque
     class, and the run exits 2 because of L_R.
   - **If any variable line or unit looks wrong:** stop.
4. **Optional, to read the rates instead of inferring them:**
   `matlab -batch "addpath scripts; export_mat_time()"`, then repeat step 3. The rates should then say "read
   from …_time.mat".
5. `python scripts/derive_raw_mat.py CO LM SH SO F2B`
   - **Prints:** `registered 4/4/4/4/5 rows` and the display names, and exits 0.
6. `L_R_Aug_26_PD_raw` only after its rate is read (step 4) or stated by the researcher: add `--fs <Hz>`.
7. Restart the project bridge, then fill in `docs/datasets/NEW_RAW_2026-10.md` from the output.

## Open questions and risks

- If L_LM was produced on a grid whose phase or interpolation differs from mine, r may stop short of 0.999 even
  for the right channel. The refusal table will show it.
- Memory for the real run:
  - The MJu dry run reads only `t` (about 118 MB) plus small slices.
  - The real MJu run holds one channel at a time (about 300 MB at peak).
  - `derive_raw_mat` loads the whole matrix (CO: about 553 MB).
- `export_mat_time.m` has not been executed.
- Old analysis results on `MJu26a.mat` stay on the old, unevenly sampled rows; nothing migrates them.
