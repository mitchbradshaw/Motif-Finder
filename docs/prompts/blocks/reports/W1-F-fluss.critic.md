# Critic report — W1-F: `detection.fluss` + `fluss_regimes`

Filed by the manager, 2026-10-13. Verdict: **merge after fixes**.

## In plain words

The block is a faithful, well-documented wrapper around stumpy's FLUSS: on its own synthetic recording it finds the
change exactly and stays quiet on drift. The template's settings (60 s window, 0.38 cut) were tuned on two near-clockwork
regimes with almost no noise; with realistic irregularity the template finds the change 1 time in 4, and 0 in 4 with
moderate noise. A long gap of missing data can also show up as a false "change".

## Findings

- **should-fix** — template calibration. Two regimes with jitter, chain detrend 600 → fluss → threshold 0.38:
  noise 0.05 → peaks 0.35–0.40 at the boundary, 1 / 4 found; noise 0.3 → peaks 0.12–0.17, 0 / 4. Window sweep: 60 s
  0.35–0.40 / 0.12–0.17 (nulls ≤ 0.23); 120 s 0.49–0.55 / 0.26–0.30 (≤ 0.34); **300 s 0.70–0.81 / 0.53–0.70 (≤ 0.35)**,
  found in every seed but 2–3 spans when `merge_gap_s` (600) < 5·L. The paper's L ≈ one period. Null maxima 0.21–0.34
  (pink noise, random walk, jittered single regime, raw drift).
- **should-fix** — windows without a neighbour (NaN data) are still scored: a 4000-sample NaN gap in one regime → peak
  0.90 and a false span. Score NaN where the index is −1; correct the IAC for missing arcs. Related, out of scope:
  `preprocessing.detrend` rolling_mean spreads one NaN sample over ~9,700 samples, so a 20-minute NaN gap through the
  template gives a score of 1.0.
- **nit** — the readout pads with location 0 (CAC 1.0) once exclusions exhaust the span.
- **nit** — off-by-one between the adapter's and the core's span-length checks.
- **nit** — the beta IAC costs 1.4 s at 4 h and 4.9 s at 24 h.

## Checked and correct

The arc count with −1 entries (stumpy draws zero-length arcs); NaN never becomes a span through `detection.threshold`;
the drift fail-safe after detrend (sinusoids 0.01–0.17, random walks 0.21–0.33, no spans); cost and ceiling identical to
`detection.matrix_profile`; deviations named; test-first; 232 passed.

## Manager decision

The template moves to a window of about one event period (~300 s), a recalibrated cut, and `merge_gap_s` ≥ 5 × window.
