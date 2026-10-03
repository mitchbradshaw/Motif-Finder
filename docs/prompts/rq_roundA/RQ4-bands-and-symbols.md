# RQ4 — Does band decomposition followed by symbolic encoding surface regions raw-signal methods miss?

**Status (2026-10-03, after `Z`): answerable in the app, bandpass bands.** The whole walk is now one action per step:
a band scope on *Apply template*, the band set as one side of Compare, the overlap split by verdict, and *Send only-B
unjudged to Review*. Still owed: the true null draw count (`T` — today one surrogate per band per channel) and the
wavelet kind of band (`AC`).

## In plain words

A recording is like a song with bass, middle and treble mixed together. Split it into layers (slow, medium, fast), turn
each layer into a string of letters (a "symbolic encoding": up, down, flat), and search the letters for patterns. Does
that find things the plain, un-split signal hides? You check the extra finds by hand to see whether they're real.

## What is known

- **The route** (readiness 2026-10-02): bandpass → detrend → `detection.sax_dsax` → `detection.symbol_search`.
  - Without the band: *"0 spans"*. With 0.01–0.1 Hz: *"5 spans"*.
  - Discovery over 3 channels: raw `drop_detection_v1` vs band gives **only A 3 · both 0 · only B 74**.
- **At untuned defaults, the single surrogate per channel produced more spans than the real signal did**, so nothing yet
  beats chance.
- ~~**Band fan-out has no caller.**~~ Closed by `Z` (2026-10-03, `docs/prompts/fixup/reports/Z-band-scope-and-compare-by-verdict.md`):
  - *Apply template* has a **Bands** scope beside *Channels in scope*. Each band is **one Discovery run across the
    channels in scope** — the template's chain with that band's bandpass prepended, built by the core's own
    `run_groups.band_recipes` → `materialize_target`. A band run's recipe **hashes the same as the chain built by hand**
    (insert the bandpass in Analyse, save, apply): measured on the sandbox, hash `1e2f3567…`, and the hand-built twin
    reused the band run's own runs 82 / 88 / 94.
  - Each band run is paired with its own surrogate, bandpassed the same way (the surrogate step goes ahead of the band).
  - A band is a **typed entry** (`{kind: "bandpass", low_hz, high_hz}`), so `AC` adds `{kind: "wavelet", level}`.
  - Compare takes the band runs of one application as one side (`set:<bandSet>`): their **union**, de-duplicated by
    the matching rule, per-band rows beneath, the band that fired named in the stepper.
  - The set overlap is **split by verdict** (judged · accepted · rejected · other · unjudged) live from
    `adjudications`, and ***Send only-B unjudged to Review*** makes a queue over exactly those regions, one detection each.
  - Compare names the **like-for-like** comparison (the same template with no band) and switches to it in one click.
- **Measured on the sandbox (2026-10-03, `Z`)**, M2_aug 452–456 h × CH2_A1 · CH6_B1 · CH7_B2, `symbol_search` × the three
  seeded bands: 1 · 75 · 17 found (0.001–0.01 · 0.01–0.1 · 0.1–0.45 Hz), a union of **92 regions**. Against
  `drop_detection_v1`: **only A 3 · both 0 · only B 92**; 3 of 5 roles differ (not attributable). The bands' nulls
  expect **297** on the same scope (8 + 249 + 40, one surrogate per band per channel) — again more than the real
  signal found. Five demonstration verdicts (not a researcher's) moved the only-B row to *judged 5 · accepted 2*.
- ~~**Found by `Z` — the symbolic encoder is not reproducible.**~~ Closed by fixup-dsax-seed: see *The symbolic chain is reproducible* below. `detection.sax_dsax` (default `threshold_mode="learned"`)
  draws its symbol boundaries from an unseeded random start, so one recipe gives different spans run to run (11 · 11 ·
  13 · 11 on M2_aug CH1_A1 80–84 h, 0.01–0.1 Hz band). Any RQ4 count on this chain carries that noise until it is
  seeded (its own task). This bears directly on the answer.
- **Found by `Z`:** Compare drew "0 of 5 roles differ" for a template against its banded twin (a role holding two stages
  drew only the last); fixed — it now reads 1 of 5, attributable.
- **Wavelet blocks that exist today:**
  - `preprocessing.wavelet_transform`: Signal → Encoding, a Morse scalogram (Dehshibi stage 1).
  - `detection.wavelet_summation`: Encoding → Scores, a band of rows summed.
  - `detection.wavelet_scattering`: Signal → Encoding, but its kymatio dependency is broken against the installed scipy.
- **No block turns a wavelet decomposition back into a band-limited Signal** that the symbolic blocks could encode. See
  Q-W3.
- **The symbolic chain is reproducible** (fixup-dsax-seed, 2026-10-03,
  `docs/prompts/fixup/reports/dsax-seed-learned-thresholds.md`):
  - `detection.sax_dsax`'s learned boundaries (and pSAX's) used to start from an unseeded random guess, so one recipe
    gave different spans run to run: 11 · 11 · 13 · 11 on M2_aug CH1_A1 80–84 h, 0.01–0.1 Hz, found by `Z`.
  - The guess now comes from a fixed private seed: that chain reads **11 every time**, and no recipe hash changed.
  - Counts stored before the fix keep their old draw. **Re-run the band runs once with *force* before reading them.**
  - The fixed seed picks one answer, not the right one. A seed sweep (`random_state=` from a script) measures how
    sensitive a count is to it.
  - `detection.sax_csax` had the same defect in its Mean-Shift (6 strings from 8 runs on CH1_A1 80–84 h) and now uses
    the same fixed seed (fixup-csax-seed, `docs/prompts/fixup/reports/csax-seed-meanshift.md`). Its **alphabet size is
    seed-sensitive** there: 3–6 letters over 32 seeds, 4 in 24. Seed-sweep any finding that leans on it.

## Decisions already made

- **Q43 (2026-10-03):**
  - A named band list lives in Settings › Analysis defaults. It is `Z`'s band scope and every bandpass block's presets.
  - It is seeded with ~0.001–0.01, 0.01–0.1 and 0.1–0.5 Hz, editable, and recorded in each run's recipe.
  - *As built (`Z`):* the third band is **0.1–0.45 Hz** — 0.5 Hz is Nyquist at 1 Hz and a Butterworth edge must lie
    below it. A band reaching a recording's Nyquist is refused when applied, by name. The band is recorded in each
    run's recipe as its bandpass step; its label lives on the Discovery run row.
- **Q-W3 (2026-10-03):** wavelet decompositions are wanted too, built in their own prompt `AC`:
  - `preprocessing.wavelet_bands` uses a stationary wavelet transform, so each layer stays sample-aligned with the
    recording.
  - The user picks which layer goes on down the chain; the block's view shows every layer.
  - A wavelet level is a band in the band scope.
- **Q35 / Q36:** a template run draws 20 phase-randomised surrogates (Settings key), and the count drawn is printed.
- **Q37:** multiple-comparison correction is wired from Settings, default `none`.

## What is still needed

| Step | Owner |
|---|---|
| ~~Band scope on *Apply template* (one template, run per band)~~ | done, `Z` |
| ~~Compare takes the set of band runs as one side; overlap split by verdict; *Send only-B unjudged to Review*~~ | done, `Z` |
| True surrogate count (today one per band per channel; the per-band rows print the count drawn) | `T` |
| The SLURM modal writes the script of the **first** pending run only, so an over-ceiling band application gets one script, not N | open (pre-existing; `AB` owns the `/slurm` writer) |
| Wavelet-decomposition block and the wavelet kind in the band scope | `AC` |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q4:

1. Apply the raw-signal template with no band, and the symbolic template with the band scope (Discovery › Runs ›
   *Apply template* › Bands), over a Discovery scope. Apply the symbolic template with no band too, for the
   like-for-like comparison.
2. Tick the raw run as A and the band-set row as B → *Compare*.
3. *Send only-B unjudged to Review* → judge them → *Refresh after reviewing*.
4. Read the sentence under the verdict split — *of the n regions only a band found, a human has judged j and accepted k*
   — with the bands' null count beside it. Then *Compare like for like* for the part attributable to the band alone.

## Open decisions

None.

## Log

- 2026-10-03 · grilling · file created; Q43 and Q-W3 recorded; `AC` written.
- 2026-10-03 · fixup-Z · band scope on Apply template, band set as a Compare side, verdict split, only-B to Review, like-for-like; Q43 built (third band 0.1–0.45 Hz); sandbox numbers recorded; the role-count Compare fix
- 2026-10-03 · fixup-dsax-seed · learned dSAX / pSAX seeded by a fixed constant: one recipe, one span set; stored counts need one forced re-run
- 2026-10-03 · fixup-csax-seed · cSAX's Mean-Shift seeded by the same constant: one recipe, one string; its alphabet size is seed-sensitive (3–6 over 32 seeds)
