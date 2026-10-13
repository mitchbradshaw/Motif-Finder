# W1-C — `detection.cwt_ridges`: multi-scale peaks and troughs by CWT ridge lines (Du, Kibbe & Lin 2006)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w1-c:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 2; facts: `docs/research/analysis-blocks-primary-sources.md` §7 (read it: scipy's `find_peaks_cwt` is **not**
the paper's algorithm — do not use it; write the paper's steps).

## In plain words

Slide a "Mexican hat" template along the trace at many sizes, from tens of seconds to hours. A real event lights the
template up over a whole run of neighbouring sizes; noise only at the smallest. Join the bright points across sizes
into ridge lines and keep the long, strong ones. The size at which a ridge is brightest is that event's own duration —
so one pass finds the ~24 s, ~8 min and ~43 min spike families reported in *S. commune* (two of them found by hand in
the paper), each with its scale. The hat has zero mean and zero slope, so slow drift cancels without a detrend window.

## The algorithm (Du et al. 2006)

1. Continuous wavelet transform with the Mexican hat (Ricker) over a geometric range of scales. scipy's public
   `cwt`/`ricker` are gone in 1.17: write the Ricker yourself and convolve by FFT (per scale, or via
   `scipy.signal.fftconvolve`), truncating each wavelet to a stated multiple of its scale.
2. Local maxima per scale in a window proportional to the scale.
3. Ridge lines: link maxima from the largest scale down to the nearest maximum at the next scale within a distance
   proportional to the scale, with a gap tolerance (a ridge may skip a few scales).
4. A peak needs: the ridge long enough (`min_ridge_scales`), the scale of its maximum inside the range, and SNR ≥
   `min_snr` where **signal = the maximum coefficient on the ridge** and **noise = the 95th percentile of |coefficients|
   at the smallest scale in a local window** around the peak (with a floor so a flat stretch cannot divide by zero).
5. Location from the ridge at its smallest scale; **width from the scale of the ridge maximum**.

## Adaptations our data force (name each in the docstring)

1. Scales in seconds: `min_scale_s` (default 10), `max_scale_s` (default 7200), `n_scales` (default 40, geometric).
2. `polarity`: `spike` (positive coefficients), `drop` (negated), `both` (default `both`; each event records which).
3. Long spans: process in **overlapping chunks** (overlap ≥ the largest wavelet's support) so a 2.6 M-sample channel
   neither exceeds memory nor loses events at chunk edges; or, if you choose a hard cap instead, use
   `max_span_samples` and say why. Edges of the span: reflect-pad, and flag events whose wavelet support crosses the
   span edge.
4. Asymmetric events (a sharkfin) put the ridge centre toward the slow side; the block reports the scale and an
   approximate extent and leaves onset timing to `interrogation.event_shape` downstream — say so in the description.
5. Convert scale to an event duration with a stated rule (e.g. the FWHM of a Gaussian bump whose response peaks at
   that scale — calibrate it in a test) and print the rule in `meta["rules"]`.

## Deliver

- Core `Working/Detection/cwt_ridges.py`; adapter `Adapters/detection_cwt_ridges.py`, Signal → SpanSet,
  `category="detect"`, `page_name="CWT ridges"`.
- SpanSet: one span per accepted peak, centred on it with the duration rule's extent, `scores` = SNR, `features` with
  `peak_idx` (span-relative), `best_scale_s`, `duration_s`, `ridge_scales`, `snr`, `polarity`, `edge_flag`.
  `meta`: counts by polarity, the scales used, the rules, and **the ridges** (each a short list of (time_s, scale_s)
  points, capped and say so) plus a coarse scalogram (≤ 4096 columns × n_scales, float32) for a future drawing.
- `estimate` via `register_cost_model`.
- Tests `tests/test_cwt_ridges.py`, `tests/test_adapter_cwt_ridges.py`, `tests/test_template_cwt_events.py` with
  `TEMPLATE = {"name": "cwt_events", …}` = `detection.cwt_ridges` → `interrogation.event_shape` →
  `interrogation.intervals`.

## Acceptance

- [ ] A 1 Hz trace of 24 h with linear + quadratic drift (drift amplitude ≥ 10× the smallest event), noise, and
      events of three widths (≈ 24 s, 8 min, 43 min; both polarities; a sharkfin-like asymmetric drop among them):
      every event found, `best_scale_s`-derived duration within a factor of 1.5 of the truth, polarity right.
- [ ] The same drift and noise without events: at most the expected false-positive rate at the default `min_snr`
      (measure it over seeds and pin a bound).
- [ ] A fast event riding on a slow one gives two events at two scales.
- [ ] Chunked and unchunked processing give the same events on a trace that fits in one chunk.
- [ ] 2.6 M samples complete (measure time and memory; report).
- [ ] The template runs end to end through `execute_recipe`; the block passes `tests/test_block_standard.py`.
