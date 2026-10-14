> Filed by the manager session, 2026-10-14 08:22 — the final message of critic agent `ad171620a734fc43f` on branch
> `worktree-agent-a976297f07092286e` (146845d..24459c7), verbatim.

## Critic report: W2-A `catalogue.event_windows` (branch `worktree-agent-a976297f07092286e`, 146845d..24459c7 on 04948e3)

### 1. In plain words
The block does what it says. It cuts one equal-length piece of the recording around each detected event, with the event's onset at exactly the same place in every piece. It carries each event's measurements onto its piece and leaves out, with a count, any event too close to the ends of the recording. I checked the geometry, the edge cases and the channel offsets myself and could not break them.

Two claims around it are weaker than they read:
- **The automatic window length does not "hold the whole event".** It is cut well before the recovery ends, on every drop I tried.
- **The `event_clusters` template reports pure noise the same way it reports real structure.** It always returns "3 clusters" with their sizes and nothing else. A meaningless split looks exactly like a real one.

### 2. Verdict
**Merge after fixes.** Nothing in the block itself blocks a merge. Fixes 1 and 2 below should land before `event_clusters` goes into CANONICAL and before W2-C/W2-E build on the auto length.

### 3. Findings

**1. should-fix: the auto-length rationale is false; the window clips the recovery on every drop.**
- **Where:** `Working/Catalogue/event_windows.py:36-43` (docstring rule 2), `:131-151` (`auto_length_s`), and the `rules()` text.
- **What is wrong:**
  - The docstring says the window "must hold the whole event with room for … the return to baseline". But Event shape's `duration_s` is onset → **half** recovery (`recovery_frac=0.5`, `event_shape.py:296-297`).
  - With `pre_frac=0.2`, the room after the anchor is only 1.6 × that duration. Even an instant-recovery drop is never in the window to baseline.
  - `:138` takes the median over the **finite** durations only. The events that never reached half recovery are the longest ones, and they are silently left out of the median, which biases it short.
- **How shown** (`exp2.py`, the template's first four steps; 20 mV drops every 60 min on AR(1), 20 s fall):

  | recovery τ | auto window | after anchor | depth still missing at window end | `recovery_win` NaN |
  |---|---|---|---|---|
  | 50 s | 90 s | 72 s | 35 % | 0/12 |
  | 200 s | 150 s | 120 s | 61 % | 0/12 |
  | 600 s | 180 s | 144 s | 81 % | 3/12 |
  | 1200 s | 180 s | 144 s | 90 % | 4/12 |

  - With mixed events (10 with τ = 30 s, 5 with τ = 1200 s), auto picked **70 s**. All 5 long events were clipped, 2 of them with NaN durations that never entered the median.
  - Part of why durations come out short is upstream: the template's 600 s rolling-mean detrend shortens the recovery. Measured duration was about 70 s for τ = 200 s.
- **Is the default defensible?** Not as a "whole event" claim.
  - It does not hurt clustering on the carried measures: Event shape measures those on the span, not the window.
  - It does hurt every waveform consumer: `window_images` now, and MiniRocket (W2-C) and families (W2-E) next.
- **Fix:**
  - Restate the rule honestly in the docstring, in `rules()` and in the help text ("covers onset to about half recovery; a placeholder").
  - Label the multiplier a placeholder.
  - Count and report in `meta` the windows whose `recovery_win` is NaN or whose `duration_s` is NaN (e.g. `n_recovery_outside_window`). That is one line, since `*_win` already holds it.
  - Better: base auto on onset → `recovery_win`, or on `duration_s / recovery_frac`. Do not exclude NaN durations from the median without counting them; a NaN means "longer than measurable", not "absent".
  - Ask the manager to check auto lengths against real recoveries (M2_aug rec 3, 500–530 h).

**2. should-fix: the template reports noise exactly as it reports structure.**
- **Where:** `Adapters/catalogue_cluster.py` `_run` meta.
- **What is wrong:** `catalogue.cluster` always cuts k = 3. Its meta holds only `cluster_counts` and `n_features`. `ClusterResult` already computes `silhouette` and `cophenetic_r`, but they are dropped.
- **How shown** (noise only, with `noise_threshold` loosened to k_sigma 2–2.5 so the noise produces "events"):

  | input | windows | clusters reported | silhouette |
  |---|---|---|---|
  | AR(1) φ = .97 | 65 | {17, 33, 15} | 0.19 |
  | detrended random walk | 41 | {6, 10, 25} | 0.26 |
  | AR(1) φ = .99 | 59 | {2, 13, 44} | 0.20 |
  | one kind of drop only (no families exist) | 15 | {7, 4, 4} | 0.30 |
  | the implementer's three real depth classes | 15 | {5, 5, 5} | **0.62** |

  The meta for every row looks identical apart from the sizes.
- **At the template's own k_sigma = 4, noise yields no events.** That part is honest: Event windows' meta says "the SpanSet holds no events…". But the run then fails at the cluster step with a misleading message: `catalogue.cluster requires a WindowSet with an attached feature matrix … (a `split` column alone is not a feature)`.
- **Fix:**
  - Surface `silhouette`, `cophenetic_r` and `feature_names` in the cluster meta. The implementer already touches this file.
  - Give the cluster step its own message for a WindowSet with 0 windows ("no windows to cluster: the step before produced none — see its meta").
  - Without a quality figure, the template's description ("Detected events grouped by their shape measures") overclaims on noise.

**3. should-fix: what the template actually clusters on depends on chance, and can include the detector's own score.**
- **How shown:** I printed `preprocess_window_matrix`'s output on the template run.
  - **Three depth classes.** Clustered on `event_amplitude_mv, event_width_s, duration_s, onset_slope_mv_s, peakedness`. Dropped:
    - constant: `polarity`, `precursor_height_mv`, `onset_win`;
    - all-NaN: `rise_time_s`;
    - correlated |r| > 0.99: `fwhm_s`, `recovery_time_s`, `max_slope_mv_s`, `chord_slope_mv_s`, `span_ptp_mv`, `extremum_win`, `recovery_win`, `span_score`.
  - **One depth class.** The same filter kept 9 features, **including `span_score` and `span_ptp_mv`**.
- **Columns to flag:**
  - `span_score` is noise_threshold's peak excursion in σ_n units: the detector's own decision, scaled by the local noise level.
  - `span_ptp_mv` is measured over the detector's span, so it depends on where the detector cut.
  - With `anchor="start"`, or for fallback events, `onset_win` becomes onset − span start: a detector-decision position.
  - Nothing that encodes absolute time survives in this template.
  - Other chains are exposed, though. `interrogation.trains` writes `train_id` and `word_id` (time-ordered integers) and `position_in_train`. `interrogation.intervals` writes `interval_before_s`/`interval_after_s`. All of these ride straight into clustering, because the block carries every numeric column.
- **Fix (minimum):**
  - Do not carry `scores` as a numeric feature by default. Name it something consumers skip, or put `span_score` in a "not shape" list.
  - Add identifier columns (`train_id`, `word_id`) to the bookkeeping list.
  - Report `feature_names` in the cluster meta (finding 2) so the researcher can see what was used.
  - Longer term: give cluster a `features` include list, set by the template.

**4. nit / design: where `NOT_FEATURES` lives, and the stale error wording.**
- **Where:** `Working/Catalogue/event_windows.py:87`; `Adapters/catalogue_cluster.py:48`; `Adapters/catalogue_classifier.py:100`.
- **The change itself is correct and complete:**
  - I grepped every producer: no existing WindowSet emits `event_index`, `anchor_offset` or `overlaps_next`, so existing chains behave identically.
  - The only WindowSet consumers that read features are `cluster` and `classifier`. `shape_cluster` reads only its shape-file column; `manual_labels`, `window_images` and `trace_shape` use no features.
  - Adapters → Working is the allowed direction.
- **Where it should live:** the list is a WindowSet-contract fact, not an event-windows fact. `split` is already owned by `SPLIT_COLUMN` in sliding_windows. Moving it to `Working/types/windowset.py` (a `BOOKKEEPING_COLUMNS` constant or a `feature_frame()` helper) would stop cluster, classifier and W2-C depending on the event-windows module. Not required for merge.
- **Stale message:** the cluster error still says "a `split` column alone is not a feature"; it should name the whole bookkeeping set.

**5. nit:** `Adapters/catalogue_event_windows.py:94` cuts `omitted_rows` at 4096 entries without saying so. Add a count or a note.

**Checked and fine:**
- **Spec acceptance:** every item is met, and the tests would fail on a wrong implementation. The window_images test uses an offset `t`, and window_images subtracts `t[0]·fs`.
- **Coloured backgrounds:** random walk, AR(1) and sine drift are all covered in the tests.
- **Test-first:** `git show --stat 146845d` touches only `tests/`, and the commit body carries the red summary.
- **Scope:** the only files outside the list are the two `NOT_FEATURES` edits; `views.py`, `registry.tsx` and `test_block_standard` were handed over. `npx tsc -b` was not run on the branch (no node_modules); the manager should run it.
- **Paper:** there is none for this block; the prompt deviations (`span_score`/`span_label`, `allow_random_split`, `n_split_leaks`) are named in the docstring.

### 4. What I ran
**Branch tests** (`event_windows`, `adapter_event_windows`, `template_event_clusters`, `block_standard`, `adapter_spec`, `import_boundaries`, `templates`, `end_to_end`): **265 passed in 238 s**. Slow because the machine is loaded by another job.

**`exp1.py`:** the template on the implementer's synthetic (preprocessed columns above), on a single depth class, and on pure noise at k_sigma 4 (AR(1) φ = .97, random walk, AR(1) φ = .99; 30 h each). Pure noise gave 0 events, so the WindowSet was empty with a note.

**`exp2.py`:** the τ sweep and the mixed-duration case (table in finding 1); noise with a loosened detector (table in finding 2); the full template on noise, which ends in the cluster error.

**`exp3.py`, core and adapter edge cases — all correct:**
- **Short span:** counted as `past_start`, with a note.
- **Constant signal with no features:** span-start fallback, with the Event-shape note.
- **NaN:**
  - a 300-sample NaN block makes its window `too_much_nan`;
  - a 5-sample gap is kept.
- **Anchors:**
  - per-event NaN onset falls back to the span start and is counted, with `onset_win` NaN;
  - `extremum_win` is correct.
- **Offset t0 = 50 000 s:** starts are exactly onset − offset + 50 000, and `cut()` puts `x[onset]` at column `anchor_offset` for every window.
- **Duplicate onsets:** 2 windows, flagged as overlapping.
- **Dense 10-min chain:** 0 leaks with a blocked split.
- **Window longer than the span:** counted, not an error.
- **Timing:** 2.6 M samples with 3000 events took **0.10 s**; `cut` gives (3000, 1200), 29 MB, in 0.04 s. The machine was loaded, so real times are likely lower.

Scripts are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\9b41764a-ced2-4e05-857c-547103bce7fb\scratchpad\critic_w2a\` (`exp1.py`, `exp1b.py`, `exp2.py`, `exp3.py`). I edited nothing in the worktree or the repo.
