> Filed by the manager session, 2026-10-14 08:38 — the final message of implementer agent `a976297f07092286e`,
> resumed for fix round 1 against `W2-A-event-windows.critic.md`, verbatim.

## W2-A fix round 1: report

I fixed all five critic findings. Each fix is a pair of commits: a tests-only commit that fails, with the failure pasted in its body, then the fix. On the final head, 369 tests passed and 4 were skipped. That covers the three W2-A test files, the cluster, classifier and sliding-windows tests, `manual_labels`, `block_standard`, `adapter_spec`, `import_boundaries`, `templates`, `end_to_end`, `webui_serialize` and `webui_block_views`.

To get the five findings I read the critic report at the main-checkout path you named, read-only, because it isn't committed on any branch. I wrote nothing outside the worktree, and did not merge or rebase onto 8ee3cd4.

### In plain words
- **Window length (findings 1 and 5).** The automatic length is unchanged (twice the median event duration), but it now says honestly what it covers. Event shape's "duration" stops when the trace is only halfway back up. So the default window holds the start of the drop, the bottom and about the first half of the climb back, not the full return to baseline. The 2× multiplier is labelled a placeholder until you check it on real recordings.
  - An event whose duration could not be measured now counts as "longer than every measured one" instead of being silently ignored.
  - The block counts windows that end before their event has recovered, and warns when that is more than a quarter of them.
  - It also now says when its list of left-out events was cut at 4096 rows.
- **Clustering report (finding 2).** `catalogue.cluster` used to report three clusters on pure noise exactly as it did on real structure. It now also reports how well separated the clusters are (silhouette and cophenetic r) and which columns it actually clustered on.
- **Bookkeeping columns (findings 3 and 4).** The list of columns that must never be clustered on (time order, train/test role, train/word ids, the detector's own score) now sits beside `WindowSet` itself, not inside the event-windows module.

### Files changed
- `Working/Catalogue/event_windows.py`:
  - docstring rule 2 rewritten (what the window covers, placeholder, unmeasured durations, coverage); the false "must hold the whole event" rationale is gone;
  - `auto_length_s` treats a NaN duration as +inf in the median: a median that is itself infinite gives the 7200 s ceiling, and if no duration is finite the span lengths stand in;
  - new `duration_unmeasured(spans)`, `recovery_outside(spans, ew)` and `OWN_COLUMNS`;
  - `EventWindows` gains a field `n_duration_unmeasured` (default 0, appended last, so W2-C/W2-E code that reads fields by name keeps working);
  - `NOT_FEATURES` is now an alias of `BOOKKEEPING_COLUMNS`;
  - `rules()` length text rewritten.
- `Adapters/catalogue_event_windows.py`: the `length_s` help text rewritten, `RECOVERY_WARN_FRAC = 0.25`, `OMITTED_ROWS_MAX = 4096`, and the new meta keys.
- `Working/types/windowset.py`: `BOOKKEEPING_COLUMNS = (split, event_index, anchor_offset, overlaps_next, train_id, word_id, span_score)`, each with its reason. It is deliberately not in `Working.types.__all__`, because `TYPE_KINDS` is built from that list.
- `Adapters/catalogue_cluster.py`:
  - imports the list from `Working.types.windowset`;
  - new meta keys;
  - its own refusal for a zero-window set;
  - the stale wording now names the whole set;
  - `_cluster_window_set` now returns `(ClusterResult, PreprocessResult)`; its only callers are `_run` and `_derive`.
- `Adapters/catalogue_classifier.py`: imports the list from `Working.types.windowset`, and its refusal message names the set.
- Tests: `tests/test_event_windows.py`, `tests/test_adapter_event_windows.py`, `tests/test_grouping_adapter.py`.

### Red → green pairs
1. **`274252f` → `c4e05b5` (auto length).** Red: 6 failed.
   - The NaN-dropped median gave 620 where 630 was expected.
   - `recovery_outside` and `n_recovery_outside_window` did not exist.
   - The rules and help text had no "half … placeholder" wording.
   - One existing test changes its expected value on purpose (620 → 630 s), as the commit says.
2. **`e142ed4` → `e8c742b` (cluster meta).** Red: 2 failed — `KeyError: 'feature_names'`, and the zero-window set got the "a `split` column alone" message.
   - No existing test asserted `catalogue.cluster`'s exact meta. Only this branch's own test reads `n_features`.
3. **`2d8b0de` → `7f91334` (bookkeeping list).** Red: 3 failed — `BOOKKEEPING_COLUMNS` could not be imported; `feature_names` included `span_score`, `train_id` and `word_id`; a bookkeeping-only table failed inside StandardScaler instead of giving a named refusal.
   - One test in that commit passes on arrival on purpose: it guards that `span_score` and upstream `train_id`/`word_id` still ride on the windows.
4. **`61d60ed` → `af9dbd7` (`omitted_rows` cap).** Red: 1 failed, `KeyError: 'omitted_rows_cut'`.

### New meta keys and warnings
- `catalogue.event_windows`:
  - `n_duration_unmeasured` (int);
  - `n_recovery_outside_window` (int, or None when there is no `recovery_idx` column);
  - `warnings` (a list; it holds a plain-words warning naming `length_s` when more than 25 % of windows end before their recovery);
  - `omitted_rows_cut` (`{reason: rows not listed}`, `{}` when nothing was cut), plus a note in `notes` naming the 4096 cap;
  - `length_basis` now states the NaN handling and that the 2× is a placeholder.
- `catalogue.cluster`:
  - `silhouette` and `cophenetic_r` (float or None);
  - `feature_names` (the preprocessed columns actually clustered on);
  - these are outputs, not params, so no recipe hash moves;
  - new refusal for an empty set: "catalogue.cluster: no windows to cluster: the step before produced none — see its meta for why."

### Commits
`git log --oneline 04948e3..HEAD`:
```
af9dbd7 w2-a: fix 5 - meta says when omitted_rows is cut at 4096
61d60ed w2-a: tests (fix 5) - say so when omitted_rows is cut at 4096
7f91334 w2-a: fix 3 - BOOKKEEPING_COLUMNS beside WindowSet; train_id, word_id and span_score are not clustered on
2d8b0de w2-a: tests (fix 3) - the bookkeeping list beside WindowSet, with train_id, word_id and span_score
e8c742b w2-a: fix 2 - catalogue.cluster meta: silhouette, cophenetic_r, feature_names; its own refusal for zero windows
e142ed4 w2-a: tests (fix 2) - catalogue.cluster reports its quality and its columns; an empty window set has its own refusal
c4e05b5 w2-a: fix 1 - the auto length says it covers onset to about half recovery; NaN durations counted
274252f w2-a: tests (fix 1) - auto length says what it covers; NaN durations counted; recovery outside the window
24459c7 w2-a: catalogue.event_windows - a window around every detected event (SpanSet -> WindowSet)
146845d w2-a: tests - catalogue.event_windows, a window around every detected event
```

### Still open for you
- Check the auto length against real recoveries (M2_aug rec 3, 500–530 h).
- `npx tsc -b` has still not been run on this branch, because the worktree has no `node_modules`. The only client change is the one-line `registry.tsx` mapping from round 0.
- The template's description ("Detected events grouped by their shape measures") is unchanged. The new `silhouette` in the cluster meta is what tells real structure from noise; you may want to name it in the description when you move the template into CANONICAL.
