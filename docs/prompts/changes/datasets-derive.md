# datasets-derive — MJu26a at a uniform 10 Hz as the parent of L_LM, and six new raw recordings into derived

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix `datasets:`; every
commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first on synthetic files.

**This prompt is special about data.** You work in a worktree with NO `DATA/`, and you must never create a junction,
symlink or copy pointing at `C:\Users\mmebr\Documents\CNN\DATA`. You write the scripts and their tests on small
synthetic `.mat` files you generate yourself (`scipy.io.savemat`, v7, and an HDF5 v7.3 variant); **the manager runs
the scripts on the real files in the main checkout at the gate** and feeds back what they print. Make every script
print what it inferred and refuse to write when an inference is uncertain, so that run is safe.

## Why (the researcher, 2026-10-18)

> Make the MJu26 dataset evenly sampled to 10 Hz (can replace derived channels in backend), then store as parent of
> L_LM. … I have just added 5 new datasets to RAW: LM, CO, SH, L_R_Aug_26_PD_raw and SO. Interpret sample rate,
> make sure even sampling or interpolate like with MJu, infer mV or V and save channels to appropriate directories
> in derived.

## Facts (manager, read-only inspection 2026-10-18)

| file | variable | shape | values (min / median / max) | note |
|---|---|---|---|---|
| `DATA/raw/MJu26a.mat` (v7.3) | `M` (16 × 14,722,842), `t` (1 × N) | — | volts, undeclared | `t` is NOT uniform: `scripts/rederive_channels.py:204 do_mju26a` wrote the rows as-is with `fs = 1/median(dt)` and saved `t.npy`, which nothing reads. L_LM_Jul_26_J_raw_fs10 is a 10 Hz ×1000 (mV) copy of five of its channels (`:241`) |
| `CO.mat` | `CO` | 17,280,001 × 4 | −0.664 / −0.360 / 0.086 | exactly 20.000 days at 10 Hz; looks like volts |
| `LM.mat` | `LM` | 17,280,001 × 4 | −0.682 / −0.301 / 0.088 | same |
| `SH.mat` | `SH` | 17,280,001 × 4 | −0.325 / −0.224 / 0.020 | same |
| `SO.mat` | `SO` | 17,280,001 × 4 | −0.653 / −0.548 / −0.378 | same |
| `F2B.mat` | `F2B` | 5,184,001 × 5 | −290 / −184 / 47 | exactly 6.000 days at 10 Hz; looks like millivolts |
| `L_R_Aug_26_PD_raw.mat` | `M1` | 3,851,550 × 13 | −0.128 / −0.097 / −0.003 | 4.46 days at 10 Hz or 44.6 at 1 Hz — neither round; volts |

Every one of the six also carries a **`MatlabOpaque`** object (fields `s0, s1, s2, arr`) that scipy cannot decode
— almost certainly the MATLAB `datetime`/`timetable` time axis. The sample count being `N·86400·10 + 1` for five of
the six is the "inclusive end" of a uniform 10 Hz grid.

Lineage in the schema: `recordings.parent_recording_id / parent_offset / decimation` (`schema.py:490`), set today
only by the excerpt rule (`Working/registration/kinds.py:456`, child ≤ 200 000 samples, one channel); shown on
`settings/DatasetsPage.tsx:166`; Review's shape code maps through it (`review.py:214-254`, requires
`fs_parent == decimation × fs_child`). Units: `Working/units.py:137` says MJu26a is undeclared; L_LM is mV. Caches:
the step cache key has no content hash (`execution.py:122`), HPC import checks npy sha1 (`chain_job.py:12-37`),
detections/annotations/runs are in sample indices. Resampler to reuse: `scripts/derive_dwij_mfs2.py:152 resample`
(linear `np.interp` onto a `0, dt, 2dt…` grid; its manifest at `:198` is the template: `fs_note`, `time_base`,
`resampling`, a warning about extrema lost). Registration: `Working/registration/kinds.py:503 _register_recording`
writes one row per `CH*.npy` from the manifest; `:774 derive_channels` is the generic raw→npy step.

## Decided with the researcher (grilling, 2026-10-18)

- **MJu26a:** register the 10 Hz copy as a **new recording file `MJu26a_fs10`** (never overwrite `MJu26a`'s
  channels: the step cache would silently serve stale results and this week's cluster imports check the file
  hashes). Linear interpolation onto a uniform 10 Hz grid from `t.npy`. The old rows stay (nothing in the Library
  references them any more); mark them inactive only if the Datasets page offers it already. **Declare both as
  volts** (`units = 'V'`, a `units_note` saying why).
- **Parent of L_LM:** each of L_LM_Jul_26_J_raw_fs10's five channels gets `parent_recording_id` = the matching
  `MJu26a_fs10` channel, `decimation = 1`, `parent_offset` = the sample offset found by aligning the two (they
  should be identical up to ×1000 and a constant offset — assert the correlation is ~1 over a 10 000-sample window
  and refuse if not). Review can then draw L_LM shapes from the parent.
- **The six new files** (`CO, LM, SH, SO, F2B, L_R_Aug_26_PD_raw`): derive to `DATA/derived/channels/<stem>/CH{i}.npy`
  + `manifest.json` the way the existing stems are laid out, and register. Sample rate: **read the MATLAB time
  object if you can** (try `scipy.io.matlab` with `struct_as_record`, `mat73`-free h5py for any v7.3, and as a last
  resort a tiny MATLAB script the manager can run in the local R2025b that writes `t` to a `.mat` v7.3 — write
  that script and say so); if the time axis cannot be read, the round-number rule (`N = days·86400·fs + 1`) gives
  **10 Hz** for CO/LM/SH/SO/F2B and the script must say so in `fs_note` as "inferred from the sample count, not
  read"; for `L_R_Aug_26_PD_raw` no round number exists — **refuse to write it until the time axis is read or the
  researcher states the rate** (print the two candidates). Units: V for values in the ±1 range, mV for values in
  the hundreds, written as `units` with a `units_note` "inferred from the value range"; F2B is mV. Even sampling:
  if a time axis is read and is not uniform, interpolate as for MJu26a; if uniform, copy.
- Stems: `CO_fs10`, `LM_fs10`, `SH_fs10`, `SO_fs10`, `F2B_fs10`, `L_R_Aug_26_PD_raw_fs10` (or `_fs1` if that is
  what the axis says), channels `CH0..`; the `datasets` display name is the researcher's short name (CO, LM, …).

## The work

1. `scripts/derive_mju26a_fs10.py`: reads `MJu26a.mat` (h5py) and `t`, resamples each of the 16 rows to 10 Hz
   (linear; `float64`; a `resampling` manifest field naming the method and the min/median/max of the original
   `dt`), writes the stem, registers it through the registry (never by inserting rows by hand), declares V, then
   links L_LM's channels to it as above and prints the alignment numbers. `--dry-run` prints everything and writes
   nothing. Refuses if the stem exists.
2. `scripts/derive_raw_mat.py <file> [--fs <Hz>] [--units V|mV] [--dry-run]`: the generic deriver for the six
   (and any future) `.mat` matrices: finds the one numeric matrix, orients it (samples × channels), reads the time
   object if possible, infers fs and units as decided, interpolates if the axis is uneven, writes the stem and
   manifest, registers, declares units. Prints a one-screen summary first and stops at anything uncertain unless
   the flag states it.
3. A `docs/datasets/NEW_RAW_2026-10.md` note the manager fills with the real-run output: per file, the rate, how
   it was known, the units, the stem, the channel count, the duration.

## Files

Yours: the two scripts (new), `Working/registration/kinds.py` only if a registration helper must accept an explicit
parent link (say so), `Working/units.py` if a declaration helper is missing, `tests/test_derive_raw_mat.py` and
`tests/test_derive_mju26a_fs10.py` (new), the docs note. Nothing under `DATA/`.

## Method and gate

- Tests (conda): on synthetic `.mat` files: a uniform 10 Hz matrix with `N·86400·10+1` rows infers 10 Hz; an uneven
  time axis is interpolated and the manifest says so; values in the hundreds infer mV, in the ±1 range V; an
  ambiguous count refuses without `--fs`; `--dry-run` writes nothing; registering twice is refused; the MJu26a
  script on a synthetic uneven `t` produces a uniform grid and links a synthetic child with the right offset and
  refuses a child that does not correlate.
- `tests/test_import_boundaries.py` green. No client work.
- The manager runs both scripts with `--dry-run` on the real files, pastes the output to you if anything is
  uncertain, then runs them for real and restarts the project bridge.

## Stop and report if

the MATLAB time object needs a dependency to read (say which, and write the MATLAB export script instead); or
L_LM does not correlate with any MJu26a channel (print the best correlation per channel and stop).

## Report

`docs/prompts/changes/reports/datasets-derive-report.md`: **Assumed**; the inference rules in plain words; the
scripts' usage; tests; what the manager must run and in what order.
