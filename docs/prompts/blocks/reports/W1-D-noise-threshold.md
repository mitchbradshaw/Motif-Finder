# Report — W1-D: `detection.noise_threshold` (implementer)

Filed by the manager from the implementer's returned report, 2026-10-13. Branch `worktree-agent-adc2b5354f31d535c`
(base 3cc2f62), commits `f344234` (tests, red: 22 failed / 27 passed) and `774aa60` (implementation).

## In plain words

The block marks stretches of the trace that stand out from the channel's ordinary background jitter. It measures that
jitter with a median, which a few big spikes barely move (the ordinary SD is inflated by the very spikes we look for),
then keeps every stretch more than `k_sigma` times the jitter from the trace's middle (4 by default, as in the paper).
No level in volts or millivolts is ever typed, so one setting works on every channel and species, stored in V or mV.

On synthetic data: the template recording (three 20 mV drops on a −0.44 V trace, 0.2 mV noise, slow drift, baseline
removed) gives exactly the three drops at ~15.6 σ past the cut, no false events. White noise: σ_n within 3 %; with 5 %
of samples replaced by big spikes σ_n stays within 10 % while the plain SD more than triples.

## Files

- `Working/Detection/analysis/noise_level.py` (new): `noise_level`, `noise_sigma`, `rolling_noise` — wraps the
  existing `drop_motifs.detect.robust_sigma` (left unchanged: the drop detector's frozen numbers depend on it).
- `Adapters/detection_noise_threshold.py` (new): `category="detect"`, `page_name="Noise threshold"`, a `derive` hook.
- `tests/test_adapter_noise_threshold.py` (19 tests), `tests/test_template_noise_threshold.py` (3, with `TEMPLATE`).
- Out of the prompt's list: `tests/test_adapter_spec.py` (shipped-adapter count 42 → 43); `Working/discovery/compare.py`
  (`ALGORITHM_GLYPH["detection.noise_threshold"] = "threshold"`, so Discovery › Compare draws it like its siblings;
  pinned by a test).

## Algorithm as implemented

centre = median(x); σ_n = 1.4826·median|x − centre|; z = (x − centre)/σ_n; `signal_threshold`'s own
`_mask_and_excursion` on z at ±k (imported); `spans_from_mask`; score = peak excursion past the cut in σ_n units;
`tidy_spans` with `min_duration_s` / `merge_gap_s` (imported). Optional `noise_from='rolling'` (median and MAD over
`noise_window_s`, default 3600 s, evaluated every window/4, interpolated). Meta: `sigma`, `centre`, `cut_above`,
`cut_below` (stored units), `plain_sd`, `fraction_past_cut`, `n_nan`, `n_unjudged`, `warnings`, `rules`; derive rows
print σ_n and the cut.

Deviations: deviation from the median (not median|x|) and a cut around the median, because a detrended 1 Hz trace can
keep an offset; no band-pass inside (the paper's 300–6000 Hz band does not exist at 1 Hz); a rolling noise option
(days-long recordings); the >20 % past-cut warning checks the paper's own assumption; a zero σ_n is never divided by;
default `direction='either'` (the template sets `below`). Implemented from the published equation only.

## Integration (manager)

Template `noise_threshold` (detrend rolling_mean 600 s → noise_threshold k 4 below); glyph (noise band ±kσ, one dip
below kept); a smoke state; no `COSTED` entry (whole-span O(n log n); rolling 0.45–0.62 s on 1 M samples). A view could
draw the computed cut read-only from `meta.cut_above` / `cut_below`; `meta["warnings"]` is new and not yet shown.

## Open questions and risks

- **The 600 s rolling-mean detrend inflates σ_n ~5×** on the template recording (1.0 mV vs 0.2 mV true noise): the
  rolling mean leaves +2 mV steps around each long drop. Weaker events near big ones would be missed on real data — a
  robust baseline (rolling median, or BEADS once W1-A lands) would avoid it.
- Rolling mode with short windows over-detects (60 s window: 425 spans per 1 M samples of pure noise vs 57 whole-span).
- The `test_adapter_spec.py` count collides with every other new block (final = 42 + blocks merged).
