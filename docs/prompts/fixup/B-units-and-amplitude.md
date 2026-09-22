# Fixup B — the amplitude the app prints is wrong by a factor of 1000

**Ready to run.** This is the highest-priority item in the Fixup Wave and it blocks prompt `C` (the
plot-domain rule), because a correctly scaled plot of a mislabelled quantity is worse than the current
one — it is more convincing.

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; the Bash tool is Git Bash; python is
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md` first — every rule binds you, especially
rule 1, rule 2 and the Web UI gate. Then read `docs/prompts/fixup/QUESTIONS.md` **Q-X2.4** (the finding
this prompt implements, with its proof), `docs/DATA_REGISTRATION.md`, and `docs/prompts/fixup/README.md`.

Commit prefix `fixup-b:`. Work test-first; your first commit must touch only `tests/` and must fail.
Take the default over asking; record every default in your report.

## The finding

**The `.npy` channel files under `DATA/derived/channels/` are in VOLTS. The entire web UI labels them
"mV" and never converts.** Every amplitude, every y-axis label, every depth figure the app has ever
shown a researcher is a factor of 1000 too small.

Proven bit-exactly, and reproduced twice:

    events.csv row id001_r1_1213252  ·  drop_depth_mv = 15.0617
    npy  DATA/derived/channels/M2_aug_concat_fs1/CH0.npy[1212809:1213520][:3]
         = [-0.45839212 -0.45842311 -0.45842109]
    npz  DATA/library_seed/drop_motifs5/motifs/snippets.npz["id001_r1_1213252__raw_mv"][:3]
         = [-458.39212 -458.42311 -458.42109]
    np.allclose(npy * 1000.0, npz)  ->  True        max|ratio - 1000| = 1.14e-13

The core already knows. `Working/Detection/drop_motifs/detect5.py:81-82` states *"`x` is in the
recording's native units (volts); amplitudes on the returned events are in mV"* and multiplies by
1000.0 at `:833-836`; `store.py:113,129` says the same and writes `__raw_mv = x * 1000.0`;
`Working/Detection/analysis/wavelet_analysis.py:102` independently says *"signal in volts"*. **The core
converts. The web UI does not.** The seed store's 410 events run 1.22 – 97.9 mV with a median of
9.06 mV, exactly the physics the researcher describes; read as the app reads them they are microvolts.

**The root cause is not a missing `× 1000`. It is that the unit is recorded nowhere on the data.**
`Pipelines/materialize_channels/materialize_channels.py` writes a sidecar manifest with no `units` key,
while `Working/registration/kinds.py:310` already calls `man.get("units")` — the reader expects a field
the writer never emits. `recordings` has no units column. Fix the missing declaration, not just the
arithmetic, or the next importer reintroduces this.

## Work (test-first per seam)

### 1. Record the unit on the data, and make an undeclared unit impossible to ignore

Add a unit to the recording — an additive column on `recordings` (rule 3: additive, through
`init_db()`, idempotent) and the `units` key the manifest writer never emitted. Backfill every existing
row to `V`, because that is what the measurement above proves they are. Registration must carry a
declared unit through, and a recording whose unit is unknown must be **loud** — refused or flagged in
words, never silently assumed (CLAUDE.md: never catch an error into a blank).

**Do not guess a unit for a file you cannot verify.** `Fig2A_dt0p1.csv` is a synthetic fixture and
`MJu26a.mat`, `M1/M100/M101_t.mat` and `L_LM_Jul_26_J_raw.mat` came from other sources. Verify each
against something — a `__raw_mv` snippet, a catalogue depth, a documented instrument floor — and where
you cannot, **mark it unknown and say so in your report.** A wrong unit asserted confidently is worse
than an honest `unknown`, because it is a research claim.

### 2. Convert once, at one named seam

Every display path reads the memmap raw:

- `webui/server/library.py::_span_amplitude` (~:348-370) — docstring says "Peak-to-peak mV", returns
  `np.ptp` of raw volts. Feeds `amplitudeMv`, `depthMv`, `depthLabel`.
- `webui/server/library.py::_trace` (~:319) — "Real decimated mV", straight off the memmap. Feeds
  `exemplarTrace` / `medoidTrace`.
- `webui/server/corpus.py::load_channel` (~:48) — bare `np.load` mmap.
- `webui/server/corpus.py::y_range` (~:309) — raw `nanmin`/`nanmax`; this is Explore's y axis.
- `webui/server/review.py` (~:111) — "Decimated mV", same unscaled read.

**Pick one seam and convert there.** The recommended one is the loader: a channel read returns
millivolts and declares it, so no downstream caller can forget. Whatever you choose, the rule must be
that **a raw-volt array and a millivolt array are never both in circulation under the same name.**

**Three things must NOT shift, and each needs a test proving it did not:**

- **Detections and annotations are stored in sample indices, not amplitudes** — nothing in
  `detections`, `annotations`, `motif_entry` or `motif_member` carries an amplitude column (verified
  2026-09-23). No stored row should change. If one does, you have converted in the wrong place.
- **The core must keep receiving volts.** `detect5.py` and `store.py` multiply by 1000 themselves; a
  converted array reaching them yields amplitudes 1000x too large. Rule 1 cuts both ways here — the
  core does not know the web UI exists, and the web UI must not change what the core is handed.
- **Step-cache keys must not silently change meaning.** If a cached step's input units change, a stale
  cache entry is now wrong rather than merely old. Check `Working/config.py`'s cache-key derivation and
  say in your report whether existing cache entries are still valid.

### 3. Fix the comments that wrote the bug down as a fact

Each of these is a true number shrunk 1000x, and each is a developer meeting the bug and explaining it
away. Leaving them makes the next reader re-derive the wrong conclusion:

- `webui/server/library.py:393-395` — *"the real depths run about 0.006 to 0.015 mV"* → **6–15 mV**.
- `webui/client/src/library/chrome.tsx:281-283` — *"the motifs riding on them are micro-volts"* →
  **millivolts**; baselines are **−3.67 V**, not mV.
- `webui/client/src/library/FamilyPage.tsx:~194-196` — *"F-01's exemplar spans −1.148…−1.131 mV … a
  real 17.6 µV drop rendered as a dead-flat line"* → **−1.148…−1.131 V**, and a **17.6 mV** drop.
- `webui/client/src/explore/SpanView.tsx:21` — the *"−0.2016 mV"* example → **−201.6 mV**.
- `webui/client/src/explore/CrossChannelPage.tsx:9,150,200-202` — *"~3.9 mV tall … windows spanning
  0.001–0.03 mV"* → **~3.9 V** of inter-channel DC offset, windows spanning **1–30 mV**.

### 4. Review's `Y_MV` is a correct volt domain wearing the wrong label

`webui/client/src/review/parts.tsx:12` `Y_MV = [-0.44, 0.44]` and `review/Shell.tsx:18`
`THUMB_Y = [-0.45, 0.45]` were hand-measured off unconverted data — they are *right in volts*. Once §2
lands they are 1000x too small and every Review trace goes off-axis.

**Update the constants so Review is not broken by this change, and STOP THERE.** Whether those domains
should be hard-coded at all is Q-R1.1, owned by prompt `C`. Do not make them data-driven here; that is
`C`'s job and doing it twice produces two rules.

### 5. Say what changed, on screen, once

A researcher who has been reading these numbers for months needs to know they moved. Put the declared
unit somewhere a reader can see it — beside the axis label, or in Settings › Datasets — so "mV" is
something the data claims rather than something the page assumes.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **Making any y-domain data-driven**, the reference-bar rule, the Family page's shape sketch | Prompt `C`. Q-X2.1/Q-X2.3 are answered but `C` owns the implementation, and one rule implemented twice is the failure this split exists to prevent |
| **`Plots/drop_motifs10`'s sub-noise-floor entries** (§below) | Q-X2.5, a research decision, unanswered |
| **Re-running any detector, or re-importing the Library** | same |
| **`DEFAULT_CHAIN`, the demo chain, Review classes, the cluster/classifier redesign** | unchanged from prompt `A`'s table |

## The finding you are NOT fixing, and must not obscure

Measured over a 600-span random sample of `motif_member`, peak-to-peak converted to mV:

| Source store | n | p25 | median | p75 | max | under 0.1 mV |
|---|---|---|---|---|---|---|
| `DATA/library_seed/drop_motifs5/motifs` (410 entries) | 72 | 5.14 | **13.31** | 16.93 | 119.6 | **0.0 %** |
| `Plots/drop_motifs10/motifs` (3,189 entries) | 528 | 0.117 | **0.324** | 0.912 | 135.9 | **22.2 %** |

**88 % of the Library is `drop_motifs10`, whose median motif is 41x smaller than the seed store's, and
22 % of it sits at or below the stated 0.1 mV instrument floor.** That is not a units bug — it is a
detector run whose output is substantially noise, and the units error has been hiding it by making
everything look equally tiny.

Your change makes it visible. **Do not smooth that over.** When the axis reads 4.3 mV instead of
0.0043 mV, the sub-floor tail must read as a tail. If your work gives you a cheap way to show a
researcher which entries fall below the floor, take it and report it; do not filter, re-run or delete
anything.

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client`;
2. `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" webui/smoke.py --url http://127.0.0.1:8765`
   against a bridge started with `--sandbox` **and restarted immediately beforehand** — the page walk is
   not idempotent against its own writes and a second run against a served bridge gives three extra
   failures (prompt `A`'s report §7);
3. `pytest` — baseline is now **1660 passed / 6 skipped / 0 failed** (prompt `A`'s report §7), not the
   969 in `webui/PYTEST_GATE_FINAL.txt`. Compare failure **sets**. The FastAPI-only files skip under
   conda and must be run under `webui/.venv`, where one pre-existing failure in
   `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` is **not yours**.

**Evidence, not assertion.** Screenshot the same Library family, the same Explore channel and the same
Review candidate before and after, into `webui/screenshots/fixup/B/`. The Library family that read
`±0.0043 mV` must read `±4.3 mV`, and the numbers must match the seed store's `events.csv` for a span
that appears in both. That last check is the claim this prompt exists to make: **a depth the app prints
equals the depth the detector recorded.** Put the comparison in your report as a table.

## Report

`docs/prompts/fixup/reports/B-units-and-amplitude.md`, house style:

- the seam you converted at and why, and what you proved did not move (stored rows, the core's input,
  the step cache);
- **the unit you assigned to each of the eleven registered source files, with the evidence for each,
  and an honest `unknown` for any you could not verify**;
- the before/after table for the depth check;
- every default taken, every item left, every out-of-scope file touched with its reason;
- the gate output, and a short chat summary.

Then update the symptom rows this closes in `docs/prompts/fixup/0*.md` and the answer in
`QUESTIONS.md` **Q-X2.4**.
