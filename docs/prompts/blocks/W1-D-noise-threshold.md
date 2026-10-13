# W1-D — `detection.noise_threshold`: a cut in multiples of the channel's own noise (Quian Quiroga et al. 2004)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w1-d:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 4; facts: `docs/research/analysis-blocks-primary-sources.md` §4.

## In plain words

To set a spike threshold you need the noise level, but the spikes themselves inflate the ordinary standard deviation.
The median of the absolute deviation hardly notices a few spikes, so σ_n = median(|x − median(x)|) / 0.6745 is the
noise level as if there were no spikes; cut at k × that (4 in the paper). The researcher then never types a level in
volts or millivolts: the same k works on every channel and dataset, whose amplitudes span 0.03–2.1 mV across species.

## The algorithm

Quian Quiroga, Nadasdy & Ben-Shaul 2004, eq. 3.1: Thr = 4σ_n, σ_n = median{|x| / 0.6745}, on a band-passed,
zero-mean signal; the rationale assumes "spikes amount to a small fraction of all samples". Use the median absolute
**deviation** (subtract the median first) so a residual offset after detrending cannot bias it.

## Adaptations (name each in the docstring)

1. `k_sigma` (default 4.0), `direction` with the **same choices and semantics** as `detection.signal_threshold`'s
   `direction` (read `Adapters/detection_signal_threshold.py` — reuse its mask/excursion logic or import it), and the
   tidy parameters `min_duration_s` / `merge_gap_s` **imported** from `Adapters/detection_threshold.py`
   (`tidy_param_specs`, `tidy_spans`, `spans_from_mask`) — do not write a second copy.
2. `noise_from` = `whole_span` (default) or `rolling` with `noise_window_s` (a rolling MAD for channels whose noise
   changes over days); keep it simple and correct.
3. The cut and σ_n in **stored units** go to `meta` (`sigma`, `cut_above`, `cut_below`) and a `derive` row prints
   them; when more than ~20 % of samples lie past the cut, `meta` carries a warning that the noise estimate is
   inflated because events are not a small fraction of the trace (the paper's own assumption).
4. Span scores = the peak excursion past the cut **in σ units**.
5. No parameter is named `threshold` (that name makes a view draw an absolute, draggable level); say in the report
   whether a view should draw the computed cut from `meta`.

## Deliver

- Adapter `Adapters/detection_noise_threshold.py` (`category="detect"`, `page_name="Noise threshold"`), the σ
  estimator as a small function in `Working/` (grep first — a robust-noise helper may already exist, e.g. in the stage
  encoding's `noise_estimator`).
- Tests `tests/test_adapter_noise_threshold.py`, `tests/test_template_noise_threshold.py` with
  `TEMPLATE = {"name": "noise_threshold", …}` = `preprocessing.detrend` (`rolling_mean`, 600 s, as the
  `signal_threshold` template) → `detection.noise_threshold` (`k_sigma` 4, `direction` below).

## Acceptance

- [ ] White noise of known σ: σ_n within 3 % of σ (many samples); with 5 % of samples replaced by large spikes, σ_n
      stays within 10 % while the plain SD is far off (pin both).
- [ ] Multiplying the input by 1000 (V → mV) gives the same spans.
- [ ] `direction` behaves exactly like `signal_threshold`'s on the same signal and equivalent cut.
- [ ] The > 20 % warning fires when events dominate and not otherwise.
- [ ] The template runs end to end; the block passes `tests/test_block_standard.py` and `tests/test_adapter_spec.py`.
