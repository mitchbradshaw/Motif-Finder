# RQ4 — Does band decomposition followed by symbolic encoding surface regions raw-signal methods miss?

**Status (2026-10-03): closest of the six.** The whole walk works by hand, one template per band, and `L` has made the
remainder sendable to Review. Owner of the rest: fixup `Z`, with `T` for the true null count.

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
- **Band fan-out has no caller.** It exists in the core (`Working/run_groups.py`, `fan_out` of `kind: "bands"`) but
  nothing in the app reaches it.
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

## Decisions already made

- **Q43 (2026-10-03):**
  - A named band list lives in Settings › Analysis defaults. It is `Z`'s band scope and every bandpass block's presets.
  - It is seeded with ~0.001–0.01, 0.01–0.1 and 0.1–0.5 Hz, editable, and recorded in each run's recipe.
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
| Band scope on *Apply template* (one template, run per band) | `Z` |
| Compare takes the set of band runs as one side; overlap split by verdict; *Send only-B unjudged to Review* | `Z` |
| True surrogate count | `T` |
| Wavelet-decomposition block and the wavelet kind in the band scope | `AC` |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q4:

1. Apply the raw-signal template and the band scope over a Discovery scope.
2. Compare raw (A) against all bands (B).
3. Send only-B to Review and judge.
4. Read *only B · judged n · accepted k* beside the null count.

## Open decisions

None.

## Log

- 2026-10-03 · grilling · file created; Q43 and Q-W3 recorded; `AC` written.
- 2026-10-03 · fixup-dsax-seed · learned dSAX / pSAX seeded by a fixed constant: one recipe, one span set; stored counts need one forced re-run
