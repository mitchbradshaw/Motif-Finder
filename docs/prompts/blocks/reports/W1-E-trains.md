# Report — W1-E: `interrogation.trains` (implementer)

Filed by the manager from the implementer's returned report, 2026-10-13. Branch `worktree-agent-a9fc53ad447c40651`
(base 3cc2f62), commits `e48a2da` (tests, red: 17 failed / 28 passed) and `5df2237` (implementation).

## In plain words

Think of events as cars on a road: in convoys, the gaps are of two kinds — short inside a convoy, long between
convoys — and on a log scale the gaps make two humps. **logISI** (default) finds the valley between the humps and uses
it as the cut; one hump → "no trains", in words. Beside it: **MaxInterval** (five fixed thresholds; fungal values
unknown, defaults are stated placeholders) and **Adamatzky's words** (same word while the gap ≤ θ = 1× or 2× the mean
gap).

On synthetic data: Poisson event times → no trains in all 300 draws (30–500 events); clear trains (gaps 20–40 s inside,
2000–4000 s between) → every train with exactly the right members in all 300 draws; the template on a recording with 4
trains of 4 drops → all 16 drops, the 4 trains, and Intervals measuring 12 s inside each train, none crossing trains.

## Files

`Working/interrogation/trains.py` (core), `Adapters/interrogation_trains.py` (SpanSet → SpanSet, `category="control"`,
`page_name="Trains"`, cost model), `tests/test_trains.py`, `tests/test_adapter_trains.py`,
`tests/test_template_event_trains.py`; out of list: `tests/test_adapter_spec.py` (count 42 → 43),
`Working/interrogation/__init__.py` (one docstring line).

## Algorithm as implemented

Event times by the Intervals anchor rule (imported; `gap_before_s` from its `measure()`); trains found per upstream
`group`, ids unique across groups; NaN onsets in no train, counted.
- **logISI**: Gaussian KDE of log10(gap), Scott bandwidth, 512 points; peaks with prominence ≥ 5 % of the maximum; the
  intra-train peak is the largest at or below `max_core_gap_s`; the first valley to its right with void
  1 − g(min)/√(g(p₁)g(p₂)) > 0.7 is the cut; a train is ≥ `min_events` (3) events joined by gaps below the cut;
  core-and-extend when an explicit `max_core_gap_s` is exceeded by the cut.
- **MaxInterval**: begin / end / minimum IBI / minimum duration / `min_events`; placeholders 60 / 120 / 180 / 0 s.
- **Adamatzky**: θ = `theta_mult` × the group's mean gap; every event gets a `word_id`; words of ≥ `min_events` are
  trains.
- Meta: `rule`, `cut_s`, `void`, `intra_peak_s`, `density` (+ `bandwidth_log10`), `n_trains`, `fraction_in_trains`,
  `train_size_distribution`, `lz_complexity` (the existing LZ76 routine on the train-size sequence, normalised n/log₂n
  — not bounded by 1 beyond two symbols, said in the rule), `word_length_distribution`, `refused`, `no_trains_reason`,
  `warnings` (Buffi 2025 when the median within-train gap is 150–250 s), `rules`, `groups`, `anchor_used`.

Named deviations: KDE instead of bins (tens to hundreds of events); `max_core_gap_s` 0 = auto = the median gap (with
one bandwidth of slack) for the neuronal 100 ms; core-and-extend skipped in auto mode; no valley → no trains (the paper
falls back to 100 ms); the 5 % prominence floor (a ripple in one hump's tail otherwise passes the void test); fewer than
10 gaps → refuses.

## Integration (manager)

Template `event_trains` = drop_detection_v1's steps → `event_shape` → `trains` (`rule="logisi"`,
`write_group=True`) → `intervals`; glyph (clusters of ticks with blue brackets, amber dashed cut); smoke state (Trains
block page, `spanset->spanset`); `COSTED` += `interrogation.trains`.

## Open questions and risks

`write_group` with an upstream group writes `<group>/<train_id>` and keeps `group_upstream`; isolated events share key
`-1`, so Intervals reports a "-1" group; auto mode's slack and skipped core-and-extend are tested only on synthetic data;
the 5 % floor is the implementer's constant; the void formula and smoothing are as Cotterill restates them; MaxInterval
defaults are placeholders; the template sets `write_group=True` though the block default is false; LZ imports the
private `_lz76_complexity` (its module imports `matplotlib.pyplot`); nothing yet run on real data.

## Fix round (after the critic), commits `f9e711a` (red) and `7764bcb`

- **F1:** in auto mode the median-gap ceiling is gone; every prominent peak is tried left to right with every later
  one, and the first valley with void > 0.7 is the cut (the median also failed on flat-topped within-train humps under
  Silverman's bandwidth). An explicit `max_core_gap_s` keeps the original rule with core-and-extend.
- **F2:** Silverman's robust bandwidth 0.9·min(sd, IQR/1.349)·n^-1/5 on log10 gaps; the description says irregular
  trains need between-train gaps ~30–100× those inside, and "no trains" can mean "not resolvable".
- **F3/F4/F5:** sub-floor humps named; grouping vectorised; the private LZ76 kept (train sizes are many-symbol strings),
  with a comment.
- **Measured (300 seeds):** false-train rate Poisson 1.3 / 1.0 / 0 % at n = 30 / 60 / 300; 100× rate ramps ≤ 1.7 %.
  Irregular trains at ratio 100: 0.99 (n = 300) and 0.87 (n = 60) of train events found (Scott: 0.85 / 0.19); ratio 30:
  0.46; ratio 10: 0. Sparse trains (the critic's F1 case): 100 % exact (was 0 %).
- Merged into `main` as `3c40946`.
