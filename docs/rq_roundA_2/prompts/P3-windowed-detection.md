# P3 — Windowed detection: window length and overlap as a run setting, the windows stitched into one result

Read [`00-common.md`](00-common.md) first. Commit prefix **`a2-p3:`**. Runs after P2 if both are queued: windows are
ordinary runs, so P2's cluster import carries them.

## In plain words

Today a detector looks at the whole stretch it is given at once, and most detectors set their bar from all of it. On a
721-hour recording a loud week can set the bar for a quiet hour, so weak events are missed at the top scale. The
researcher wants drop detection, and any detector, run over **sliding windows with overlap**: each window is judged on
its own scale, and the windows' detections are stitched into one result, with nothing counted twice where windows
overlap. Choosing a window length and an overlap becomes a step of setting up a detection run, with an overlap
recommended.

## What is true today (the windowing check, 2026-10-17)

### Nothing runs per window

- `Working/execution.py:105-115` slices one span, and each block's `spec.run(x, …)` gets all of it.
- Discovery's apply fans out over channels or bands only (`fan_out.kind`, `Working/recipes.py:262-266`), never over time.
- `preprocessing.sliding_windows` is a training block (a WindowSet with a blocked train/test split, overlap forbidden by
  P12). It is not this.
- The only route today is by hand: one apply per section.

### What already exists and should be reused

- Detections are channel-absolute (`execution.py:505-519`).
- A run is keyed by (config, recording, span), so re-running a window reuses its run (`execution.py:376-387`).
- The Map stitches overlapping runs newest-wins, but it only counts (`Working/discovery/detection_map.py`).
- Two de-duplication tools:
  - Compare's matching rule: IoU ≥ 0.5 and onset gap ≤ 0.25 × duration, paired greedily
    (`Working/discovery/matching.py:41-45, 114-184`);
  - `union_span_sets` (`Working/discovery/compare.py:427-463`).

### What changes per window, because each block fits to its span

- **drop_detection_v1:**
  - its dSAX cutlines (quantile mode: 60 % "same" by construction, `Working/Detection/drop_motifs/detect5.py:334-343`);
  - its slope σ, the MAD of the second difference (`:352`);
  - the `min_depth_frac` gate, which is relative to the deepest drop in the span (`:845-853`);
  - morphology `auto`, decided per span.
- **noise_threshold:** σ_n, unless `noise_from='rolling'`.
- **SAX:** z-normalisation and cutlines. cSAX can even change its alphabet size.
- **Matrix profile:**
  - a twin in another window is invisible, so a motif can read as a discord;
  - `mp_threshold`'s absolute cut fires more on short windows.

  Matrix profile is the one family that should keep the whole span (RQ4b decision; P2).
- **Detrend edges:** drop_detection_v1's 4,916.67 s rolling mean distorts about 41 min at each window edge.

## The change

1. **A window scope on a detection run**, beside the channel and band scopes:
   `{kind: "windows", window_s, overlap_frac}`, recorded in the run's recipe so it is part of the run's identity.
   - The default overlap is **0.5** (recommended).
   - Bounds: `window_s` at least 4 × the chain's longest internal window, e.g. the detrend window. Refuse a shorter one
     and name the step that sets the minimum. `overlap_frac` lies in 0–0.9.
2. **Targets.**
   - Cut the section into windows starting every `window_s × (1 − overlap)`; the last window ends at the section end.
   - Each window is one target per channel through the existing fan-out, so every window is a normal run: cached and
     reused on re-application.
3. **Stitching**, a core function (e.g. `Working/discovery/windowed.py::stitch`):
   1. Keep a window's detection only if its onset lies in that window's **core**, the middle not shared with a
      neighbour. The first and last windows keep their outer edges.
   2. Merge any remaining duplicates with Compare's matching rule.
   3. Record on each kept span which window produced it.
   4. State the rule in `meta["rules"]`.
4. **One Discovery run row per window application** (as a band set is). Its detections are the stitched set, so Runs,
   Compare, *Send to Review*, the Scoreboard and the Map read it as one algorithm row.
   - The window scope joins the Map's row key (`detection_map.steps_key`), so "drop_detection_v1 · 24 h windows · 50 %"
     and the whole-span run are two rows.
5. **Null:** each window draws its own null at the Settings count (it can now be 1). The plan's estimate counts
   windows × (1 + draws).
6. **UI:** *Apply template* gets *Windows: off · length · overlap (50 % recommended)* beside Channels and Bands. The
   plan shows the number of windows and the estimate.
7. **Say the trade-off on the face**, in a plain sentence near the scope: "each window sets its own thresholds; a
   quiet window finds weaker events than the whole-span run would". Where a block exposes its fitted σ or cutlines,
   keep them per window in `meta`.

### The researcher's sweep scales (2026-10-17, evening)

- **Every detection template runs at three scales in the RQ4 sweep:** 10-minute windows, 1-hour windows, and the
  whole signal. Duplicates where windows overlap are handled by the stitch above.
- **"Treat each scale as a new version of the detection algorithm."** Point 4 already does this: the window scope
  joins the Map's row key, so each scale is its own row beside the whole-span one. Keep it that way.
- **The windowed sweep goes to the cluster.** The whole-signal sweep ran there on 2026-10-17 as P2 chain jobs
  (`scripts/rq4_overnight.py` on branch `rq4/sweep-code`). A windowed application must therefore export through
  `Working/discovery/chain_job.py` like any other run, each window one target. Check that its spec, cache keys and
  import hold with windows × channels targets, possibly thousands per run.
- **The bound in point 1 refuses the researcher's 10-minute scale.** Most of these templates detrend over 600 s, so
  4 × 600 s is a 40-minute minimum. Do not decide this silently. Put it to the researcher in plain words with the
  options (refuse and say why; shorten the detrend window for that scale, which makes it a different chain; or allow
  it with a warning), and recommend one.
- **`dehshibi_spikes` and its two variants can only run windowed.** `preprocessing.wavelet_transform` refuses spans
  over 320,000 samples, a memory cap, so they were left out of the whole-signal sweep. 1-hour windows (3,600 samples
  at 1 Hz) fit.

### Defaults for the drop detectors

For `drop_detection_v1`, `drop_detection_v5` and `wavelet_encoded`, measure on synthetic data which window length
recovers the events a whole-span run misses without inflating noise detections. Try 12, 24, 72 and 168 h. Recommend
one per block in the report.

## Tests (test-first; include the coloured backgrounds from the lessons)

- **The windowed run finds what the whole span misses.** Synthetic: a weak drop train in a quiet stretch beside a loud
  stretch. The whole-span run misses the weak drops; the windowed run finds them.
- **No double counting:**
  - no event is reported twice inside an overlap;
  - an event straddling a window boundary is found exactly once.
- **Reuse:** re-applying the same scope reuses every window's run and computes nothing.
- **Map:** the windowed application is its own row, and counts are not doubled where windows overlap.
- **Noise:** on pure AR(1) (φ 0.97) and random-walk noise, the windowed run finds no more events per hour than its null.
- **The window bound:** a window shorter than the chain's minimum is refused, naming the step.

## Acceptance

- [ ] Window length and overlap are a run setting. 50 % overlap is the default and is labelled recommended.
- [ ] The stitched result is one Discovery run on Runs, Compare, Review and the Map, its own row there, with no
      duplicates.
- [ ] Each window is a normal cached run.
- [ ] Per-window refitting is said on the face and recorded in `meta`.
- [ ] Smoke states in `webui/smoke_pages/a2_p3_windows.json`: the scope offered, the plan's window count and estimate,
      and a windowed row on the Map.
