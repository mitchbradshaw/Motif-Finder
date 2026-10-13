# W2-D — `catalogue.snippets`: the few typical pieces of a recording, and where each one dominates (Imani et al. 2018)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w2-d:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 10; facts: `docs/research/analysis-blocks-primary-sources.md` §13c (read it — the installed `stumpy.snippets`
has a default that silently changes the method). Round 1 of wave 2. The researcher chose FLUSS + snippets as the two
matrix-profile methods (§8 Q2); FLUSS shipped in wave 1 as experimental, so snippets is the matrix profile's best
remaining chance to earn a template.

## In plain words

Summarise a long recording with its two to four most typical pieces, and colour the recording by which piece each
stretch most resembles — like the handful of thumbnail frames that best represent a film, plus a bar under it showing
which frame each scene is closest to. It answers the first question on a new recording: *where should I look, and how
many kinds of behaviour are there?*

## The block

`catalogue.snippets`, **WindowSet → Grouping**. The input windows are the pieces: run it after
`preprocessing.sliding_windows` with `gap_s = 0` (contiguous, non-overlapping), so `m` = the window length. Core in
`Working/Detection/matrix_profiling/snippets.py` (beside `fluss.py`), wrapping `stumpy.snippets` (1.14.1).

1. **MPdist must be switched on.** `stumpy.snippets(T, m, k, percentage=1.0, …)` sets the MPdist sub-length
   `s = ceil(percentage·m)`; at the default 1.0, MPdist degenerates to plain z-normalised Euclidean distance and loses
   the robustness to "linear trends … wandering baseline" that is the reason to use it. Param `subseq_frac`
   (default **0.35**, the paper's example: sub-length 70 of 200) → `percentage`. Pass `s` explicitly if that is
   clearer, and test that the value reached stumpy.
2. **Params:** `k` (default 0 = auto: the paper's knee of `change_k = Area_{k−1}/Area_k − 1` over k = 1…`k_max`;
   state the knee rule exactly), `k_max` (6), `subseq_frac`, `mpdist_percentage` (0.05, stumpy's default — say what it
   does). `m` comes from the WindowSet; refuse in words if `m > n // 2` (stumpy's limit) or if fewer than `2·k_max`
   pieces exist.
3. **Labels per window.** stumpy's `regimes` give, for each snippet, the sample ranges where it is the overall nearest.
   Each window gets the snippet that owns most of its samples (1…k). If the windows are not contiguous and
   non-overlapping, compute on the span's `x` with `m = length` all the same and label windows by majority, and say so
   in `meta`. Windows that are mostly NaN: label −1, counted. **NaN handling:** stumpy pads with NaN internally; a NaN
   in your input must be handled before the call (interpolate short gaps, mark long ones) — test it.
4. **The exemplar is the snippet itself** — a real piece of the recording, never an average (`BLOCK_INTEGRATION.md`
   §2). Put `meta["exemplar_windows"] = {"<label>": <window index>}` and `meta["exemplar_rule"] = "the snippet itself:
   the piece whose MPdist profile …"`. The serializer does not read this yet — W2-F adds it; describe what it needs.
5. **`meta`:** `k`, `k_chosen_by`, the areas curve and `change_k` per k, each snippet's `fraction` (coverage),
   `snippet_starts_s`, `subseq_frac`, `m_s`, regime **run lengths** (mean and median length of a run of consecutive
   windows with the same label — the manager's null statistic, see below), timing, `rules`.
6. **Cost:** O(n²) overall. Declare `estimate` with the matrix-profile cost model (`Working/Detection/matrix_profiling/
   cost.py`) or a measured one, and `max_span_samples` if a 26-day channel (2.6 M samples) is out of local reach — time
   a 24 h and a 72 h run at 1 Hz with `m` = 3600 and report both.

## The template `recording_snippets`

In `tests/test_template_recording_snippets.py`: `preprocessing.detrend` (`rolling_mean`, window long enough to keep the
pieces' shape — propose and justify a value, e.g. 6 h for 1 h pieces) → `preprocessing.sliding_windows` (`window_s`
3600, `gap_s` 0) → `catalogue.snippets` (k 0). Kind as `kind_for_steps` implies.

**How the manager will judge it (design your tests so this can pass):** on real recordings, snippets' regimes should
be **persistent** — long runs of the same label — where on phase-randomised surrogates (same spectrum, no real
regimes) they flicker. The statistic is the mean regime run length; the template ships only if real beats all 20
surrogate draws on most recordings.

## Deliver

Core, `Adapters/catalogue_snippets.py` (`page_name="Snippets"`), `tests/test_snippets.py`,
`tests/test_adapter_snippets.py`, the template test, a `COSTED` entry.

## Acceptance

- [ ] A synthetic recording made of three regimes (e.g. 8 h of sawtooth drops, 8 h of quiet AR(1), 8 h of a slow
      oscillation), concatenated twice in a different order, with drift on top: k auto = 3, and the window labels follow
      the regimes with ≥ 90 % agreement.
- [ ] With `subseq_frac = 1.0` the drift test does measurably worse than with 0.35 (show it: that is the reason for the
      default).
- [ ] **No-structure check:** stationary coloured noise (one AR(1) process throughout) gives short regime runs, and the
      knee rule says so (k = 1, or k > 1 with a flat areas curve reported plainly).
- [ ] The exemplar of each label is one of that label's own windows.
- [ ] Refusals (m too large, too few pieces, NaN-only) are in words.
- [ ] The template runs end to end; the block passes `tests/test_block_standard.py` and `tests/test_adapter_spec.py`.
