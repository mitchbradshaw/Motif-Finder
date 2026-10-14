# W3-A — `catalogue.multiscale_entropy`: a complexity fingerprint per window (Costa, Goldberger & Peng 2005; Wu et al. 2014)

Read [`00-common.md`](00-common.md) first, including **both** "Lessons" sections. Commit prefix **`w3-a:`**. Plan:
`docs/research/analysis-blocks-from-literature.md` §4 A1 ("accept, adapted"); facts:
`docs/research/analysis-blocks-primary-sources.md` §1 (read it: r is fixed across scales from the **original** series'
SD, as the authors' `mse.c` does; the exact RCMSE equation of Wu 2014 is **unverified** — only Azami et al. 2017's
restatement was reached). Round 1 of wave 3.

## In plain words

Entropy asks "how surprising is the next value?". Pure noise is maximally surprising and a metronome not at all, yet
neither is *complex*. Multiscale entropy (MSE) blurs the signal more and more — averaging 2, 3, … many points at a time
— and measures the surprise at every blur level. White noise loses its surprise as you blur it; a signal with structure
at many time-scales keeps it. The shape of the curve, not one number, is the fingerprint. It needs hours of signal per
curve, so it describes **recordings, species and conditions — not events** (round B: "conditions and organisms").

Two things this project has measured make the null the heart of this block:

- **Our backgrounds are coloured** (wave 1: sample-to-sample noise 3–46× smaller than the level's spread). Coloured
  noise has an MSE curve of its own — pink noise's is flat — so the question is never "what is the curve?" but "how does
  it differ from noise with the same spectrum?". The manager answers that with phase-randomised surrogates (same
  spectrum, no nonlinear structure); your block must make that comparison possible and stable.
- **The √t preprint reports "mean MSE 0.0028"** on the same four-species data we hold (plan §4 A3). That is almost
  certainly the collapse Costa warns about (App. B): drift inflates the SD, r grows with it, nearly every template
  matches, and entropy falls towards 0 for a reason that is not the signal's. The block must catch that on its face.

## The block

`catalogue.multiscale_entropy`, **WindowSet → WindowSet** (`page_name="Multiscale entropy"`, `category="encode"` like
MiniRocket). Core `Working/Catalogue/multiscale_entropy.py`; adapter `Adapters/catalogue_multiscale_entropy.py`.
**Why not extend `preprocessing.window_matrix`:** its entropy families are single-scale
(`Working/Detection/analysis/entropy_analysis.py:163`), they are RQ1's feature arm, and changing them moves RQ1's numbers
and recipe hashes — write that paragraph in your docstring.

1. **Windows.** Slice each window from `x` as MiniRocket does (`Working/Catalogue/minirocket.py::_slice_x`: starts are
   channel-absolute, the pool path reads stored windows) — import it, or promote it to a shared helper and re-export it
   (one move, named in your report); do not write a third slicer.
2. **The algorithm.** Coarse-grain by non-overlapping means (Costa eq. 16). `method`: `"rcmse"` (default; Wu 2014 as
   restated by Azami 2017 — at scale τ pool the m- and (m+1)-match counts over all τ offset series and take
   −ln(Σn^{m+1} / Σn^m); name the source and that the original equation was not reached) or `"mse"` (Costa's original,
   for fidelity checks). m = 2 (param, bounds 1–3).
3. **Tolerance.** r = `r_frac` (default 0.15, the paper's) × a scale of the **window as it arrives**, fixed across
   scales (`mse.c`). `r_scale`: `"mad"` (default — 1.4826 × the median absolute deviation, robust to the outliers and
   drift Costa's App. B warns about) or `"sd"` (Costa's). The block never detrends; the template does, upstream.
4. **Scales in seconds**, so a 1 Hz and a 10 Hz recording mean the same thing: `scale_min_s`, `scale_max_s`, `n_scales`,
   geometric, τ = round(scale × fs), deduplicated. Propose the defaults and justify them (the plan suggests 1 s → 20 min).
   A scale whose coarse series is shorter than `min_coarse_len` (default **1,000**, Costa §VI: 2 × 10⁴ points for scales
   up to 20) is **NaN, counted, never extrapolated**. RCMSE is meant to tolerate shorter series; you may lower the
   default for it **only with a measurement** of its bias and spread at the lower length on your synthetic sets, stated
   in the help text. An undefined SampEn (no m+1 match) is NaN with its own reason.
   **Reach and cost pull against each other — design for both.** A scale of s seconds needs `min_coarse_len` × s
   samples of window: at 1 Hz and 1,000 points, a 24 h window reaches about 86 s, a 72 h window about 4 min, a whole
   721 h M2_aug channel about 43 min — while fungal events last minutes to hours. But SampEn is O(N²) in the coarse
   series' length, so the small scales of a long window are the expensive ones (2.6 M points at τ = 1). Costa used
   N = 2 × 10⁴ at every scale; propose a cap — evaluate each coarse series on at most `max_points` points (e.g. 2 × 10⁴,
   a contiguous stretch or several pooled stretches — choose and justify) — so that every scale costs about the same and
   is estimated about equally well, and say what the cap does to the estimate's spread. Put the arithmetic for 4 h,
   24 h, 72 h and 721 h at 1 Hz and 10 Hz in your report.
5. **Collapse guard** (the √t number). Per window and scale, when r is so large against the coarse series' own spread
   that nearly every template matches, entropy collapses for a reason that is not the signal's: flag it (state the
   rule; `meta["collapse"]` counts per scale; a warning on the face). Also report each window's **drift share** (e.g.
   SD ÷ (1.4826 × MAD), or the variance share of a straight-line fit — pick one, state it) so a user can see when r was
   inflated.
6. **Columns added per window:** `mse_<scale>s` per scale (stable names for a given parameter set), `mse_ci` (the
   complexity index: the sum over the scales defined in **every** window of the set — state the rule; report how many
   scales it covers), `mse_slope_small` / `mse_slope_large` (least-squares slopes of entropy against log scale over
   the lower and upper halves of the defined scales — Costa Fig. 8's two slopes, restated in seconds), `mse_r` (stored
   units), `mse_n_scales`. Upstream features pass through.
7. **Gaps.** Interpolate NaN runs up to `max_gap_s` (default a placeholder, e.g. 30 s, labelled); a window with a
   longer gap is left out (a NaN row), counted, with its reason. Upstream, the rolling-mean detrend is NaN-aware on
   `main` since 2026-10-14 (`e4a5373`: it averages the finite samples, so one gap no longer blanks the whole trace),
   and the drop detector skips gaps (`1019cf6`) — so a gap reaches your block as a gap, and your block decides.
8. **Speed.** numba SampEn with the sorted-template trick (sort on the first template coordinate, compare only
   neighbours within r) — **exact counts**, pinned against a naive O(N²) loop. Declare `should_cancel` and
   `on_progress` keyword arguments on `_run` (checked and fired between windows) the way
   `Adapters/preprocessing_window_matrix.py` does; `Working.execution` forwards them as `run_kwargs` when a caller
   passes them, and W3-F makes the bridge do so. On cancel raise the executor's cancellation (read
   `Working/execution.py::RecipeCancelled` and window matrix's own) — one exception, named.
9. **Cost.** `register_cost_model(name, exponent, run_once, warm_up=…)` with the numba compile in the untimed warm-up
   (wave 2: an import timed as work made an 8 s run look like 6,370 s). The estimate sees the span and your params, not
   the upstream windows: state the assumption (e.g. windows of the template's length tile the span) and how wrong it
   is otherwise. Report estimate vs actual, cold process and warm, on 24 h and 73 h at 1 Hz and 24 h at 10 Hz. Give
   the manager a `COSTED` line.
10. **`meta`:** `scales_s`, τ per scale, `method`, `m`, the r rule, defined-window counts per scale, collapse counts,
    left-out windows by reason, timing, `rules`, and a **drawing payload for W3-F**, `meta["curves"]`: per window the
    entropy at each scale (at most 64 windows — beyond that a seeded sample plus the median curve), NaN where undefined.

## The template `complexity_fingerprint`

In `tests/test_template_complexity_fingerprint.py`: `preprocessing.detrend` (`rolling_mean`; propose the window and
justify it against Costa's warning that detrending reshapes multiscale structure — a window much longer than the
largest scale removes the drift that inflates r while barely touching scales ≤ 20 min; **measure** that on a synthetic
signal) → `preprocessing.sliding_windows` (`gap_s` 0; `window_s` long enough that the curve reaches minute scales —
from your arithmetic above, e.g. 72 h, which also gives one curve per channel of the 73 h *S. commune* recordings; say
what a shorter recording gets) → `catalogue.multiscale_entropy` (defaults). Kind as `kind_for_steps` implies
(training). Its description names the first knob (the scales, or r) in plain words and says what a curve can and cannot
show.

**How the manager will judge it** (design so this can pass): per recording, the window-median curve against the same
chain on 20 phase-randomised surrogate draws. Statistic: the real curve's distance from the mean of the 20 surrogate
curves, over the scales defined in every run, against each draw's distance from the mean of the other 19 (real
farthest → p = 1/21). Then the species table (do the fingerprints of *S. commune*, *C. militaris*, *F. velutipes*,
*O. nidiformis* and M2_aug separate better than their surrogates' do?) and the √t check (no detrend, `r_scale="sd"`:
does the 0.0028 collapse reproduce, and does the guard fire?). So: seeded and stable on surrogates, and loud when too
few scales are defined to compare.

## Deliver

`Working/Catalogue/multiscale_entropy.py`, `Adapters/catalogue_multiscale_entropy.py`, `tests/test_multiscale_entropy.py`,
`tests/test_adapter_multiscale_entropy.py`, `tests/test_template_complexity_fingerprint.py`, and **one `COSTED` line in
`tests/test_block_standard.py`** (handed to you; nothing else in that file).

## Acceptance

- [ ] SampEn and RCMSE counts equal a naive implementation's on short series (several m, r, τ).
- [ ] `method="mse"` reproduces the paper's two benchmark shapes: white noise falls with scale, 1/f noise stays roughly
      flat (Costa 2005 Fig. 1: N = 2 × 10⁴, m = 2, r = 0.15 SD) — within a tolerance you state.
- [ ] RCMSE leaves fewer scales undefined than MSE at the same short N (Wu 2014's point), shown.
- [ ] The same synthetic process at 1 Hz and at 10 Hz gives the same curve at shared scales, within tolerance.
- [ ] Coloured backgrounds (detrended random walk, AR(1) φ 0.95–0.99, a slow drift): with `r_scale="sd"` on a drifting
      window the collapse guard fires; with `"mad"` on the detrended window it does not.
- [ ] Structure vs its null: sharp drops with slow recovery on AR(1) give a curve outside the spread of their own
      phase-randomised copies; two phase-randomised copies agree within that spread.
- [ ] Undefined scales are NaN and counted; gappy windows are left out with their reason; every refusal is in words.
- [ ] Cancel between windows stops the run with the named exception; `on_progress` fires once per window.
- [ ] The template runs end to end; `tests/test_block_standard.py` and `tests/test_adapter_spec.py` pass.
