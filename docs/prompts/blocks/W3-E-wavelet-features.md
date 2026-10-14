# W3-E (optional) — `catalogue.wavelet_features`: the Wave_clus sorter's features, ten wavelet coefficients that split the events (Quian Quiroga, Nadasdy & Ben-Shaul 2004)

Read [`00-common.md`](00-common.md) first, including **both** "Lessons" sections. Commit prefix **`w3-e:`**. Plan:
`docs/research/analysis-blocks-from-literature.md` §5 row 4 ("accept the detector, adapt the sorter") and §7.1 (wave 3,
"optional Quiroga sorter"); facts: `docs/research/analysis-blocks-primary-sources.md` §4 — read it: the KS statistic is
the Lilliefors-modified one on values **within ±3 SD**, the 10 most non-normal coefficients are kept, and the paper
warns that KS also picks skewed one-humped coefficients (3 of its 10). Wave_clus is licensed "free for non-commercial
use": write from the paper, never port it. **Round 2 of wave 3, optional.** You start from a `main` holding W2-A's
`catalogue.event_windows` and wave 2's clustering blocks: read their reports.

## In plain words

Wave 1 took Wave_clus's spike detector (`detection.noise_threshold`). Its sorter has two halves. The first describes
each event by wavelet coefficients — numbers saying how much of the event's shape sits at each scale and position — and
keeps the ten that look least like a bell curve across events: a coefficient that is two-humped across events is one
that splits them into two kinds. The second half, superparamagnetic clustering, was replaced by HDBSCAN in wave 2. This
block is the first half: it turns each event window into those few coefficients, for any clustering block after it.

## The block

`catalogue.wavelet_features`, **WindowSet → WindowSet** (`page_name="Wavelet features"`, `category="encode"`). Core
`Working/Catalogue/wavelet_features.py`; adapter `Adapters/catalogue_wavelet_features.py`.

1. **Windows** are sliced from `x` with MiniRocket's slicer (`Working/Catalogue/minirocket.py::_slice_x`, or the shared
   helper if W3-A promoted it — grep first; never a third slicer).
2. **Length and alignment.** Resample each window to `n_samples` (default 64, the paper's; a power of two). The paper
   aligned spike maxima at sample 20 after cubic-spline upsampling to 256 points; our windows arrive anchored by Event
   windows (W2-A), so name what replaces that alignment and what it costs.
3. **Haar decomposition**, `pywt.wavedec(w, "haar", level=4)` → 64 coefficients for 64 samples (paper §2.1, §3.2).
4. **`normalise`:** `"none"` (default, the paper's — amplitude separates neurons, and the supervisor found amplitude
   regimes that define fungal spike families: ~7–14 mV against ~0.4–0.6 mV on rec 385) or `"z"`. Say which question
   each answers.
5. **Choosing coefficients.** Per coefficient, across windows: the Lilliefors-modified KS statistic, max|F − G| on the
   values within ±3 SD (paper). **Its yardstick is a null, not a table:** windows on our coloured backgrounds are
   correlated, so the textbook KS critical value over-rejects; compare each coefficient's statistic with the same
   statistic on phase-randomised copies of the windows (each window's spectrum kept, a few seeded draws), and keep only
   coefficients that beat it, up to `n_coeffs` (default 10). If fewer clear the null, keep fewer and say so — "no
   coefficient departs from normal beyond the null" is an answer. Beside each kept coefficient report a bimodality
   measure (a simple bimodality coefficient — no dip test is installed), because KS also keeps skewed one-humped
   coefficients.
6. **Output columns** `wc_<level>_<index>` for the kept coefficients; `keep_upstream_features` as MiniRocket's (default
   true). `meta`: the kept coefficients with their level, position, KS, null KS and bimodality; NaN and flat windows
   counted; timing; `rules`.

## The template `wavelet_sorted_events`

In `tests/test_template_wavelet_sorted_events.py`: the `noise_threshold` template's two steps (read
`webui/server/templates.py`; do not edit it) → `interrogation.event_shape` → `catalogue.event_windows` (defaults) →
`catalogue.wavelet_features` (`keep_upstream_features` false) → `catalogue.cluster` (its meta carries the silhouette
since W2-A's fix). It is `event_clusters` (W2-A) with the features swapped, so the manager can put the two side by side
on the same events.

**How the manager will judge it:** as `event_clusters` — the silhouette against the shape null (the same real events,
each waveform replaced by a phase-randomised copy of itself) — and against `event_clusters` on the same spans.

## Deliver

`Working/Catalogue/wavelet_features.py`, `Adapters/catalogue_wavelet_features.py`, `tests/test_wavelet_features.py`,
`tests/test_adapter_wavelet_features.py`, `tests/test_template_wavelet_sorted_events.py`.

## Acceptance

- [ ] Three synthetic event shapes on coloured backgrounds (reuse W2-B's generator, `tests/_shape_families.py`): the
      kept coefficients beat the null and separate the shapes (adjusted Rand ≥ 0.8 with `catalogue.cluster` at k = 3).
- [ ] One shape at two amplitudes: separated with `normalise="none"`, not with `"z"` — and the description says so.
- [ ] No structure (windows of AR(1) φ 0.95–0.99 and detrended random walk): no coefficient, or almost none, beats the
      null, and the block says so.
- [ ] The ±3 SD Lilliefors statistic is pinned against a direct computation on the clipped values.
- [ ] The template runs end to end; `tests/test_block_standard.py` and `tests/test_adapter_spec.py` pass.
