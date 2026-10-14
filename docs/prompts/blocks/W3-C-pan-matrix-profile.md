# W3-C — `detection.pan_matrix_profile`: at which window lengths does anything repeat? (Madrid et al. 2019, matrix profile XX)

Read [`00-common.md`](00-common.md) first, including **both** "Lessons" sections. Commit prefix **`w3-c:`**. Plan:
`docs/research/analysis-blocks-from-literature.md` §5 row 11 ("accept as optional"); facts:
`docs/research/analysis-blocks-primary-sources.md` §13b — read it: stumpy scales each length by 1/(2√m) clipped at 1
(the paper gives no rule), and `stimp`'s `PAN_` is **binarised at 0.2 by default**: a picture, not distances. Round 1 of
wave 3. Look at `Working/Detection/matrix_profiling/fluss.py` and `Adapters/detection_fluss.py` first — the nearest
sibling.

## In plain words

The matrix profile finds repeated shapes, but only at one window length chosen in advance. The pan matrix profile
computes it at many lengths and shows them as a heat-map: lengths up the side, time along the bottom, bright where
something repeats. It removes a guess this project has made by trial and error:

- On the supervisor's spiking-families recording (rec 385, 4 h, 1 Hz) the 1-minute window served individual spikes;
  3 and 10 minutes were mostly baseline with the spike squeezed against an edge.
- Wave 1's FLUSS used a 300 s window. Re-run on spans the researcher knows (2026-10-14), its strongest change beat the
  null on three of four spans but sat 3.4–10.5 h away from the known boundaries (rec 6: 372.5 h and 455.5 h for a chain
  at 383–445 h). The window is a suspect, and this block is the tool to pick it.

It does not answer RQ3 by itself: two occurrences must have the same length to match, so "the same shape at two
durations" stays the seed search's scale bank.

## The block

`detection.pan_matrix_profile`, **Signal → Encoding** (an image; `page_name="Pan matrix profile"`, `category="encode"`).
Core `Working/Detection/matrix_profiling/pan.py` (beside `fluss.py`); adapter `Adapters/detection_pan_matrix_profile.py`.

1. **Lengths in seconds:** `min_window_s` (default 30), `max_window_s` (default 3600), `n_lengths` (default 12),
   geometric; m = round(s × fs), deduplicated. The paper's SKIMP visits lengths breadth-first so the picture is
   "anytime"; `stumpy.stimp` takes a linear `step`. Choose — per-length `stumpy.stump` / `scrump` calls on your
   geometric list, or `stimp` — and justify it (cost, fidelity, what an octave-like question needs).
2. **Exact or approximate:** `percentage` (1.0 = exact `stump`; below 1 = `scrump` with `pre_scrump`, approximate — said
   on the face and in `meta`).
3. **Values and layout.** Per subsequence the z-normalised nearest-neighbour distance d, normalised d / (2√m) and clipped
   at 1 (stumpy's rule; name it as stumpy's, not the paper's); the image holds 1 − that, so **bright = repeated**. Read
   the distances, never `PAN_`. **Rows long first** (row 0 = the longest window — the convention of
   `preprocessing.wavelet_transform`, so `detection.wavelet_summation`'s `row_from` / `row_to` fractions read the same
   way). **One column per sample of the span, start-aligned** (column i holds the subsequence starting at i; each row's
   last m − 1 columns are NaN — no-data grey), so the Encoding view locates every frame in time
   (`docs/BLOCK_INTEGRATION.md` §2, "emits an image with one column per sample"). `meta["lengths_s"]` names the rows;
   `meta["alignment"] = "start"`.
4. **Which length repeats — against noise of the same colour.** Per length, in `meta`: the best motif distance and the
   5th percentile and median of the normalised profile. With `null_draws` > 0 (default 1 — measure the cost), the same
   profiles on phase-randomised copies of the span (spectrum kept, seeded), and per length the gap between real and null
   in units of the null's spread (state the rule). `suggested_window_s` = the length with the largest gap, **only if it
   clears the null** (state that rule too); otherwise `meta` and the summary say "no length stands out". Never default
   to the shortest length: shorter windows find chance matches more easily (RQ3 measured about twice as many matches per
   null draw at 0.8× as at 1×). And at long lengths coloured noise repeats too: a z-normalised hour of a random walk is
   a smooth ramp or hump, and smooth curves match one another well — wave 2's "smooth shapes" blind spot again. Only
   the gap to the null, never the raw profile, may decide.
5. **Gaps.** stumpy pads with NaN internally; fill short gaps before the call with snippets' own gap handling
   (`Working/Detection/matrix_profiling/snippets.py::fill_nan` — import it), mark long ones, and leave every subsequence
   that touches a long gap NaN, counted. The rolling-mean detrend upstream is NaN-aware on `main` (`e4a5373`), so a gap
   arrives as a gap.
6. **Cost and stopping.** Use the matrix-profile cost model (`Working/Detection/matrix_profiling/cost.py::
   estimate_seconds`; k ≈ 3.5 × 10⁻⁹ s × n² on this machine: ~0.7 s per length for 4 h at 1 Hz, ~26 s for 24 h, ~6.5 h for
   a whole 721 h channel) summed over lengths, × (1 + `null_draws`), × your measured factor for `percentage` < 1. Using
   that model is what lets the bridge calibrate it on first need (`webui/server/chain.py::_uses_mp_cost`) and refuse an
   over-limit run with a SLURM script instead of hanging, as FLUSS once did. `max_span_samples` is a **hard memory
   guard** (n_lengths × n × 8 bytes plus stumpy's own working set) — do not derive it from the calibration at import time
   (FLUSS does, so its guard stays `None` until the bridge restarts). Declare `should_cancel` and `on_progress` keyword
   arguments on `_run`, checked and fired between lengths and between null draws, as
   `Adapters/preprocessing_window_matrix.py` does; W3-F makes the bridge pass them, so a long pan run can be stopped
   between lengths. On cancel raise the executor's cancellation (`Working/execution.py::RecipeCancelled` or window
   matrix's own — one exception, named).
7. **Proposing a window to another block.** The spec's `recommend` hook sets *this* block's own parameters, so it is not
   the tool: put `suggested_window_s` and its rule in `meta` and the summary line (W3-F may add "use this window" on the
   page). A `recommend` for this block's own `max_window_s` from the span length is welcome.
8. **Downstream.** `detection.wavelet_summation` (Encoding → Scores) sums a band of rows: test pan → wavelet_summation end
   to end, and say in the description what the summed score means (repetition across a band of lengths).

## The template `motif_lengths`

In `tests/test_template_motif_lengths.py`: `preprocessing.detrend` (`rolling_mean`; propose the window — longer than the
longest length — and justify it) → `detection.pan_matrix_profile` (30 s → 1 h, 12 lengths, exact, `null_draws` 1). Kind
encoding. The description names `max_window_s` (or the null) as the first knob and says plainly what "no length stands
out" means.

**How the manager will judge it:** rec 385 (4 h) — does it suggest about one minute, as the supervisor found, and does
that length beat all 20 surrogate draws? Then 8 h spans of known chains (M2_aug rec 2 296–304 h sharkfins, rec 6
400–408 h, rec 3 512–520 h). If it suggests a window on a chain, the manager re-runs the experimental FLUSS template with
it.

## Deliver

`Working/Detection/matrix_profiling/pan.py`, `Adapters/detection_pan_matrix_profile.py`, `tests/test_pan_matrix_profile.py`,
`tests/test_adapter_pan_matrix_profile.py`, `tests/test_template_motif_lengths.py`, and **one `COSTED` line in
`tests/test_block_standard.py`** (handed to you; nothing else in that file).

## Acceptance

Keep the suite fast — synthetic spans of a few hours at 1 Hz, or longer ones decimated; the 24 h timings go in your
report, not in a test.

- [ ] A 4 h AR(1) φ 0.97 background with a 90 s motif planted 12 times and a 20 min motif planted 6 times: bright at
      both lengths at the planted positions, both lengths beat the null, and the 90 s motif does not light the ≥ 20 min
      rows except where it sits inside the long motif.
- [ ] No structure: a detrended random walk, AR(1) φ 0.95–0.99 and pink noise → "no length stands out", on at least two
      span lengths (say which and why those).
- [ ] A test that would fail if the binarised `PAN_` were read instead of distances.
- [ ] Start alignment, the NaN tail of each row and rows long first are pinned.
- [ ] pan → `detection.wavelet_summation` runs, and its band maps onto the intended lengths.
- [ ] Cancel between lengths stops the run with the named exception; `on_progress` fires per length.
- [ ] Estimate vs actual reported for 4 h and 24 h at 1 Hz (within 2×, cold and warm).
- [ ] The template runs end to end; `tests/test_block_standard.py` and `tests/test_adapter_spec.py` pass.
