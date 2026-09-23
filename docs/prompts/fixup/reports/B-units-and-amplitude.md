# Report — Fixup B: the amplitude the app prints was wrong by a thousand

Run 2026-09-23 on `main`, in the main checkout, from base `099e30b`. Commit prefix `fixup-b:`. The first commit,
`3549779`, touches only `tests/` and fails 27 tests; the implementation is `7af7065`. The bridge ran in `--sandbox`
throughout. Nothing here wrote to the real `DATA/db/annotations.sqlite` or to anything under `DATA/`: the real
database was only read, through a `mode=ro` URI, to measure the recordings.

**The fix, in one line:** the unit is now recorded on the data (`recordings.units`, the manifest's `units` key),
and the bridge converts to mV at one named seam from it. For every recording whose unit is declared, the depth the
app prints now equals the depth the detector recorded — **38 of 38** seed-store spans checked, to the fourth
decimal (§4). Six of the eleven source files could not be verified and are recorded as **undeclared, with the
reason**; the pages say "unit undeclared" for them instead of "mV", and the researcher can declare each one in one
click in Settings › Datasets (§2, §6).

---

## 1. The seam, and what did not move

### Where the conversion happens

`webui/server/corpus.py` now has two loaders and nothing else:

| name | returns | who calls it |
|---|---|---|
| `load_native(npy_path)` | the stored samples, memmapped, byte for byte | everything that hands data **to the core**: Analyse's derive rows, cross-channel lag/r, seeded search, the distance profile, a window's score curve, Compare-every-stage's two chains, the Library's grouping engine |
| `display_channel(rec)` → `DisplayChannel` | slices in **mV** when `rec["units"]` is declared; the stored numbers with `unit = None` when it is not | everything that **draws**: Explore's window and y-extent, Review's traces, the Library's traces and amplitudes, Discovery's signal/overview/detection/seed traces |

`corpus.load_channel` is **deleted** — it was the one name that did not say which of the two it returned, and the
1000x error lived behind it. A raw array and a mV array are never in circulation under the same name: the core
path only ever sees `load_native`, and `DisplayChannel` never exposes its memmap. Where one route needs both
(Discovery's distance profile, Compare-every-stage), the core gets `load_native` and the drawn copy is multiplied
by the same `DisplayChannel.factor`. A chain's `Signal` payload (`serialize._signal`) is converted with the
recording's unit from the job context: every Signal-producing block (detrend, band/high/low-pass, surrogate)
preserves units, so this is the same factor, applied to the drawn copy only — the core's value is not mutated
(pinned).

**Why the loader and not the payloads:** the prompt's recommendation, and it is the only place that knows the
recording. Every drawn number passes through it, so no caller can forget; every core number bypasses it by name.

### What I proved did not move

| invariant | how it is pinned |
|---|---|
| **No stored row changes.** Detections, annotations and Library members are sample indices. | `test_recording_units.py::test_the_backfill_moves_no_detection_annotation_or_library_row` snapshots `detections`, `annotations`, `motif_entry`, `motif_member` before and after `init_db()` runs the backfill: identical. No amplitude column exists on any of them (re-verified: none of the four carries one). |
| **The core keeps receiving what it received.** `detect5`/`store` multiply by 1000 themselves. | `Working/execution.py::_load_signal` is untouched and `test_the_core_still_receives_the_stored_samples` pins it returning the volts. Every bridge call site that hands data to a core function uses `load_native` (listed above); `grep load_channel` over `webui/`, `Working/`, `Adapters/` is empty. The Library's regroup job and the editor's merge-height fit get `_native_waveform`, exactly the traces they got before. |
| **The step cache keeps its meaning.** | The key is `_recipe_prefix_hash` — recording id, span, steps, params, side inputs (`Working/execution.py:108`). The unit is not in the recipe and the core's input did not change, so **every existing step-cache entry is still valid**: same key, same input, same output. `test_the_step_cache_key_does_not_see_the_unit` pins it. The bridge's meta sidecars hold adapter meta, not drawn values, and are unaffected. |

---

## 2. The unit of each of the eleven registered source files

Measured 2026-09-23 on the real channels (read-only). "MAD" is the median absolute first difference, a
sample-to-sample noise estimate in the file's own units. The table is also the backfill: it lives in
`Working/units.py::RECORDING_UNITS_EVIDENCE`, and `init_db()` writes each row's unit and note onto every channel
row that carries neither — so a unit a person declares later is never overwritten.

| source file | unit | evidence |
|---|---|---|
| `M2_aug_concat_fs1.mat` | **V** | All **386** of its seed-store events: `__raw_mv` = samples × 1000, max \|ratio − 1000\| = 1.1e-13. Read as volts, motif depths run 1.2–98 mV (median 9.1) and the noise is 0.025 mV — the band and the 0.1 mV floor the researcher states for M2. |
| `M2_aug_concat_fs2.mat` | **V** | The same experiment at 2 Hz: CH0 median −0.437 vs the fs1 file's −0.430, noise 0.030 vs 0.025. Read as mV it would sit 1000x away from a verified file of the same experiment. |
| `M2_concat_fs1.mat` | **V** | By scale only: baselines −0.11 to −0.63 and noise 0.010–0.013 mV if volts — the verified M2 range. No store snippet covers it; this is the weakest "V" in the table and the note on the row says so. |
| `Mushroom_260720_0509_4hrs_CH14_fs1.mat` | **V** | All **24** of its seed-store events: `__raw_mv` = samples × 1000 (1.1e-13). Independently: L_LM CH2 block-meaned 10:1 at sample 15,777,590 = **998.2 ×** these samples + 298, r = 0.9995. |
| `L_LM_Jul_26_J_raw.mat` | **mV** | The same regression read the other way: it is ~1000x a volts file. `lionsmane12.py` reached the same answer; its manifest's free text ("millivolts as stored…") now parses to `mV`. Noise 0.03–0.25 mV. |
| `M4_aug_concat_fs1.mat` | **undeclared** | Held out (D6). Not opened for this check; not asserted by analogy with M2. |
| `Fig2A_dt0p1.csv` | **undeclared** | The CSV carries no unit and is a synthetic fixture. Every detector run assumed volts, which `Plots/drop_motifs8_fig2a/PROVENANCE.md` §5 already says was never confirmed. |
| `M1.mat` | **undeclared** | Another source; nothing to check it against. Read as volts: baseline −0.10 V, noise 0.046 mV — plausible, not verified. |
| `M100.mat` | **undeclared** | A high-passed M1 (first differences correlate 0.986, gain 0.977): M1's unit, whichever that is. |
| `M101_t.mat` | **undeclared** | Same quantisation and scale as M100: M1's unit. |
| `MJu26a.mat` | **undeclared** | Samples are quantised in exact 1e-6 steps (1 µV if volts, 1 nV if mV) — suggestive of volts, not verified. |

**One thing the snippet check does not prove, said plainly.** `__raw_mv = samples × 1000` holds for *any* file a
drop-motif store was run over, because the store multiplies by 1000 whatever it is handed. The check proves the
app now agrees with the store; it is the physics (the researcher's floor and motif band, the L_LM regression) that
proves the store was right for M2_aug and Mushroom. For Fig2A the snippet relation holds too (`drop_motifs10`,
exact) and proves nothing about its unit, which is why it is undeclared.

### What "undeclared" does on screen

The bridge serves the stored numbers with `unit: null`, and nothing prints "mV" beside them: Explore's axis prints
"?" and the Signal page carries a callout naming the file and the reason; the Library withholds the waveform
(a trace on an mV axis is a claim about its unit), prints no mV amplitude, and says which recording and where to
declare it (`unitNote`); Review draws nothing for it (no Review queue holds such a recording today).
**Fig2A is 2,425 of the Library's 3,603 members (67 %)**, so until its unit is declared most Atlas cards read
"unit undeclared · not drawn in mV". That is the cost of not guessing, and it is one click to undo (§6).

---

## 3. §2b — the slopes: verified, V/s, one `fs`

`store11.py`'s note holds. On `Plots/drop_motifs10/motifs` at **fs = 10 Hz** (the seed store is all 1 Hz, where a
second `fs` factor would be invisible), for **338 of 338** events:

    min( np.gradient(__detrended_mv) × fs  over [onset, trough] )  ==  max_slope_raw × 1000      (ratio 1.000000)

So `max_slope_raw` is **V/s with `fs` applied exactly once**; mV/s = `max_slope_raw × 1000`, no second `fs`. A
second factor would have given a ratio of 0.1. **No web display prints a raw slope**: Interrogation's slopes are
computed from the store's `__detrended_mv` snippets and are already mV/s; the only other "mV/s" strings are the
adapters' own derive rows (`detection_drop_detection`, `detection_stage_encoding`), which multiply volts by 1000
themselves and are handed the stored samples.

---

## 4. The depth check — a depth the app prints equals the depth the detector recorded

`scripts/fixup_b_units_evidence.py --depth` → `webui/screenshots/fixup/B/depth-check.json`. Every member of F-01,
F-02, F-37 and F-64 whose span is a seed-store snippet span: 38 members on M2_aug CH1/CH2/CH6 and Mushroom_260720.
`before` is what the old bridge printed (peak-to-peak of the raw memmap slice), `app` is `amplitudeMv` off the
running bridge now, `store` is peak-to-peak of the store's own `__raw_mv` for the same samples.

| family | member | seed event | before ("mV") | **app (mV)** | **store ptp (mV)** | detector `drop_depth_mv` | detector `peak_to_peak_mv` |
|---|---|---|---|---|---|---|---|
| F-01 | m-249 | id028_r6_1464360 | 0.02071 | **20.7097** | **20.7097** | 15.21 | 22.44 |
| F-01 | m-234 | id028_r6_1407613 | 0.02048 | **20.4790** | **20.4790** | 13.50 | 24.24 |
| F-01 | m-247 | id028_r6_1459761 | 0.01775 | **17.7519** | **17.7519** | 12.50 | 18.87 |
| F-01 | m-238 | id028_r6_1418129 | 0.02105 | **21.0453** | **21.0453** | 15.32 | 23.94 |
| F-01 | m-240 | id028_r6_1426649 | 0.02364 | **23.6407** | **23.6407** | 14.75 | 28.52 |
| F-64 | m-394 | id385_r385_5164 | 0.01407 | **14.0701** | **14.0701** | 13.76 | 14.00 |
| F-64 | m-390 | id385_r385_2374 | 0.01399 | **13.9940** | **13.9940** | 13.68 | 13.95 |

**38 of 38 agree** (app = store to 1e-4 mV; `before` = store / 1000 every time). The detector's own
`drop_depth_mv` and `peak_to_peak_mv` are measured on the *detrended* trace between onset and trough, so they are
a different quantity over a shorter window — they are in the table as the physics check (same order, same band),
not as the equality.

### Before / after, on screen

`webui/screenshots/fixup/B/` — `before-*`, `after-*`, `after-fig2a-declared-*`, each with its `*.json` of the
numbers read back off the DOM.

| surface | before | after | after, Fig2A declared V (sandbox) |
|---|---|---|---|
| Library Atlas, shared scale | `−0.0041…+0.0041 mV · 37 clipped` | `−15.00…+15.00 mV · 11 clipped` | **`−4.10…+4.10 mV · 37 clipped`** |
| Library F-01, measured peak | `0.016 mV` | `15.61 mV` | `15.61 mV` |
| Library F-117 (Fig2A only) | `peak 0.000025 mV` | `unit undeclared` | `peak 0.025 mV` |
| Explore channel 1 (M2_aug CH1_A1), y labels | `−0.112 / −0.156 / −0.200 mV` | `−112.23 / −156.20 / −200.17 mV` | same |
| Review q2 · detection 100 | axis ±0.4, trace at −0.42 | axis ±400, trace at −420 | same |

The last column is the prompt's acceptance, exactly: with every recording in the Library declared, the shared
domain the page computes is **±4.10 mV where it was ±0.0041**, with the same 37 families clipped — the same
drawing, 1000x the number. With Fig2A left undeclared the domain is set by the declared families only and reads
±15 mV. (The prompt quoted ±0.0043; the page measured ±0.0041 on this database both before and after.)

---

## 5. The fossil comments (§3), and three more of the same kind

Every comment the prompt listed now states the true number and says the old one was stored volts printed as mV:
`library.py::_amp_domain` (6–15 mV), `chrome.tsx::centreTrace` (−3.67 **V** baselines, **millivolt** motifs),
`FamilyPage.tsx` (−1.148…−1.131 **V**, a **17.6 mV** drop), `SpanView.tsx` (−201.60 mV), `CrossChannelPage.tsx`
lines 9, 150, 200–202 (~3.9 **V** of DC offset, windows spanning 1–30 mV). The same error was written down in
**`explore/crossScale.ts`**'s header (−0.10…−3.79 "mV" baselines, 0.001–0.03 "mV" windows, a 0.0017 "mV" row),
**`AtlasPage.tsx:128-133`** (−3.67…+0.0004 "mV", median peak 0.0009 "mV"), **`chrome.tsx::fmtMv`** (peaks
2e-5…0.07 "mV"), **`MvLabels.tsx`** and **`charts/primitives.tsx`** (a 60 s viewport spanning 0.0005 "mV"); all
are corrected. The ratios in those comments were always right, so no conclusion drawn from them changes — only the
unit.

`SpanView`'s label gutter used the label's *decimal* count; with baselines now in the hundreds and thousands of mV
the integer digits matter, so it measures the printed label. And the kit's tick formatter printed 400 as
`+4.0e+2` (`toPrecision`), which Review's axis showed as soon as its domain was in mV; it now prints `+400`.

---

## 6. Where the unit is visible (§5)

- **Settings › Datasets**: a *stored in* column (green `V`/`mV`, amber `undeclared`, the evidence note on hover),
  and in the recording's card a *stored in* field — locked with its evidence when declared, a select +
  **Declare** when not. `PUT /api/registry/recording/{id}/units` sets every channel of the recording together,
  refuses a unit it cannot read (422) and the held-out file (423), and appends an audit entry.
- **Explore**: the axis prints the window's own unit ("?" when undeclared, with a tooltip); the Signal page's
  display menu says what the raw view is in; an amber callout names an undeclared recording.
- **Library**: an amber `unit?` badge on every family with undeclared members (hover: which file, where to fix it).
- **Registration**: an undeclared unit is a warning in words on scan, check and the registered row; a supplied
  `units` override answers it; an unreadable one fails the `units` check. Both manifest writers
  (`materialize_channels.materialize_arbitrary_file`, `kinds.derive_channels`) always write the `units` key, null
  when unknown — the reader that expected it (`kinds.py:310`) now has a writer.

---

## 7. Defaults taken

1. **The backfill is per file, not "every row to V".** The prompt says both "backfill every existing row to V"
   and "do not guess a unit you cannot verify"; the second wins, because L_LM is *measured* to be mV and six files
   cannot be measured at all. A blanket V would have made L_LM 1000x too large and asserted six unknowns.
2. **Undeclared is flagged, not refused.** Registration still accepts a recording with no unit (it is readable
   data, and refusing would have broken the Datasets import flow); it warns in words, stores NULL and every page
   says so. "Refused or flagged in words" — flagged.
3. **Undeclared draws as stored with no unit on the axis in Explore, and is withheld in Library and Review.**
   Explore is where a researcher inspects a raw file, so it shows the numbers and says "?"; the Library and Review
   compare traces against each other on shared mV axes, where an unconverted trace would be the original error.
4. **The Library's grouping engine keeps the stored samples.** It is the core; converting its input would have
   changed amplitude-basis groupings silently. The editor's *amplitude histogram* is drawn in mV and counts
   declared members only; its frequency and timescale histograms and the merge heights are unchanged.
5. **L_LM's core input is left as it is (mV).** See §8.1.
6. **No sub-floor marker.** The prompt invited a cheap one. The only cheap measure is peak-to-peak over the stored
   span, and Q-X2.5 established that is the wrong measure for `drop_motifs10` (the detector's `drop_depth_mv` is
   the right one, and the Library does not import it — that is prompt D's `motif_features`). A count built on the
   wrong measure would be a finding nobody should act on, so I did not add one. What this change does do: the
   sub-floor tail is now visible as numbers — Atlas peaks print 0.025 mV beside 15.61 mV instead of 0.000025
   beside 0.016.

---

## 8. Left, and found

1. **L_LM hands the core millivolts.** The core's loaders (`execution._load_signal`, `side_inputs`) read the stored
   samples, and for `L_LM_Jul_26_J_raw.mat` those are mV. Any web-UI chain run on L_LM gives the drop detector mV
   where it expects V, so its depths and mV/s rows come out 1000x too large. `lionsmane12.py` divides by 1000 for
   its own runs; the web UI does not. Fixing it means the core converting from `recordings.units` to volts — which
   changes the core's input for one recording and the meaning of any L_LM step-cache entries, so it is a decision,
   not a default. No L_LM run exists in this database today. **Raised as `QUESTIONS.md` Q-X2.8.**
2. **Declaring Fig2A** (and M1/M100/M101_t/MJu26a) is the researcher's call; until then two-thirds of the Library
   cannot draw. If Fig2A is volts — which every detector run assumed — one click restores it and the Atlas reads
   ±4.10 mV (§4, last column).
3. **Review's `Y_MV` / `THUMB_Y`** are ×1000 (`[-440, 440]`, `[-450, 450]`) and nothing more; whether they should
   be hard-coded is Q-R1.1, prompt C. The before/after shots show the geometry is unchanged.
4. **`Plots/drop_motifs9_fig2a`'s snippets are not samples × 1000** of the current Fig2A files (max difference
   1.35 mV), unlike `drop_motifs10`'s (exact). Not investigated; noted because D will read snippets.

**Out-of-scope files touched, with reasons:** `webui/client/src/kit/plots.tsx` (the `4.0e+2` tick, visible only
because Review's domain is now mV); `webui/client/src/explore/crossScale.ts`, `AtlasPage.tsx`, `charts/primitives.tsx`,
`MvLabels.tsx` (the same fossil comments as §3's list); `webui/client/src/discovery/{SeedPage,ComparePage}.tsx`,
`webui/client/src/analyse/{Renderer,BlockPage,ChainPage}.tsx` (they print "mV" beside channel values and needed the
unit); `webui/server/runs.py` (one key in the payload context); `Working/database/queries.py`,
`Pipelines/materialize_channels/materialize_channels.py` (the manifest writer the prompt names).
`scripts/fixup_b_units_evidence.py` is new: the evidence, reproducible.

---

## 9. The gate

| gate | result |
|---|---|
| `npx tsc -b`, `npm run build` (`webui/client`) | clean |
| `pytest -n auto` (conda), full suite | **1683 passed / 6 skipped / 0 failed** — baseline 1660 / 6 / 0 re-measured on `099e30b` this morning; +23 are this ticket's. No test that passed before fails. |
| FastAPI-only files under `webui/.venv` (`tests/test_webui_*.py -n auto`) | 234 passed, 2 failed: `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` (the pre-existing one the prompt names, not mine) and `test_webui_decimate.py::test_decimation_is_not_quadratically_slow`, a wall-clock test that fails under `-n auto` load and **passes 13/13 run alone**; `decimate.py` is not in this diff. The new Library/Review route tests pass. |
| `webui/smoke.py` against a bridge restarted immediately beforehand, nothing else running | **543 screenshots, 4 failures, 0 console errors, 0 unexpected server tracebacks.** The four are exactly prompt A's §7 four — `settings.datasets--import-check-fails-fs-unknown`, `…--import-check-passes-MJu26a`, `settings.models-registration--check-a-joblib`, `settings.storage-backups--scan-check-a-matrix-profile` — registration state in the database this sandbox copies, not code. |

**A first smoke run gave 23 failures and is not the result.** It ran while the full pytest suite had every core
busy: each workspace's *first* state timed out and Chromium logged `ERR_NETWORK_IO_SUSPENDED`, with no server
traceback behind any of them. The rerun above, alone on a fresh bridge, is clean but for the four known. Worth
knowing for the next agent: smoke and `pytest -n auto` must not run together on this machine.

The regenerated numbered flow screenshots and the per-page state shots are **not** committed (restored to the
tracked set, as prompt A did); the only screenshots this work commits are in `webui/screenshots/fixup/B/`.

---

## Chat summary

The app's amplitudes were 1000x too small because nothing on the data said what unit it was in, and the
units turned out not to be uniform: M2_aug, M2_concat and Mushroom_260720 are volts, but **L_LM_Jul_26_J is
millivolts**. The unit now lives on `recordings` (and in every manifest a writer produces), and the bridge
converts at one seam — `display_channel` for what is drawn, `load_native` for what the core gets. For 38 of 38
seed-store spans the app now prints exactly the store's mV peak-to-peak (it printed 1/1000 of it). With every
recording declared, the Atlas reads ±4.10 mV where it read ±0.0041. No stored row, core input or step-cache key
moved.

Six files could not be verified — **Fig2A** (a synthetic fixture), M1, M100, M101_t, MJu26a and the held-out M4 —
and are recorded as undeclared with the reason; the pages say "unit undeclared" rather than "mV". Fig2A is 67 % of
the Library, so most Atlas cards are blank until the researcher declares it in Settings › Datasets (one click; if
it is volts, as every detector run assumed, everything draws). Slopes are verified V/s with `fs` applied once.
One new decision is raised as Q-X2.8: the core still hands L_LM's millivolts to a detector that expects volts.

Gate: tsc/build clean; pytest 1683/6/0; smoke 4 failures, all the pre-existing Settings ones.
