# span-plot report: the Signal page's bands

Prompt: `docs/prompts/changes/explore-span-plot.md`. Branch `worktree-agent-a9376090dbf373475`, base `9504e38`.

## 1. Assumed

- **The pile's real cause is in the client, not in `_absolute`.** The fixtures for (a), (b) and (c) all came out clean (below). The pile is the whole-channel spans read, which is capped at 5 000 rows sorted by start. Since `getSignalDemo` became `getSignalLive`, the page treated that read as the channel's full detection list.
- **Legacy ambiguous runs: stopped and reported, not guessed.** The database can tell that a run is ambiguous and that it was written before the fix. It cannot tell which of that run's rows are span-relative. The read keeps the existing heuristic and logs one warning per run, naming its detector and date. The one-time migration is proposed in §8.
- **Fix date cutoff:** a run is "before the fix" if `runs.started_at < "2026-09-22"` (UTC). The fix is commit a8cea40, 2026-09-21 07:05 UTC. Comparing whole days means the rest of the 21st also counts as before, so at worst those runs get an extra warning. Nothing changes how they are drawn.
- **Colours:** the existing seed colour is the same green as interesting, so seed got teal. Teal is the one new token, `--teal: #0d9488`. Not interesting uses the theme's `--purple`. Unsure uses grey (`--muted-2`), even though the coverage ribbon draws unsure in amber, because amber means "selected" in the span view.
- **Toggles are remembered** in `localStorage` key `ub.explore.span-bands`. The setting is per browser, for the Explore workspace, and applies to every channel. If storage is unreadable or broken, every kind shows.
- **‹ N / M › skips a kind that is switched off.** The prompt did not say; walking to bands you have hidden seemed wrong.
- **The density ribbon follows the run picker only when the whole-channel read is complete.** When that read is capped, the ribbon shows the bridge's own count over the whole channel, for every run. A run filter on the server's ribbons would be needed to have both; that is out of scope.
- `api/explore.ts` is unchanged. The `getSignalDemo` alias still works; only the page's double use of it was the bug.

## 2. In plain words

Picture a spreadsheet that only shows its first 5 000 rows, sorted by time. If you made a chart from that, every point would sit at the start of the year. That is what the overview's blue detection bars were doing on busy channels. They now show the real count over the whole channel.

The span plot's legend is now a row of six switches: detected, interesting, not interesting, unsure, artifact and seed. Each has its own colour, and each can be turned off. Interesting and not-interesting are no longer the same green.

The span's start and end are now number boxes (seconds, three decimals, with the hours beside them). You can type into them, and the plot follows as you type.

## 3. Files

Created:
- `Working/discovery/spans.py` — not new, but it gains `legacy_ambiguous`, `warn_if_ambiguous`, `ambiguous_legacy_runs`, `detector_of` and `EXECUTOR_ABSOLUTE_FROM`.
- `webui/client/src/explore/bandModel.ts` (new) — the six kinds, their colours, verdict → kind, the run filter, band geometry, and edge parsing and stepping. It has no imports.
- `webui/smoke_pages/zzzzzzzzzzz_span_plot.json` (new).
- `tests/test_span_plot_absolute.py` (new, conda), `tests/test_webui_span_plot.py` (new, venv).

Modified:
- `webui/server/corpus.py`:
  - `_absolute` is now an alias of `spans.absolute_bounds`.
  - `spans()` also selects `r.span_end, r.started_at`, warns once per ambiguous legacy run (new `_warn_ambiguous`), and returns the new key `detections_complete_to_s`.
  - This is localized to `_absolute`, `spans` and a new helper; AR's coverage-cache changes are elsewhere in the file.
- `webui/client/src/explore/SignalPage.tsx` — detection and band paths only:
  - the toggle hook;
  - motifs filtered by the toggles;
  - the run filter always applies;
  - the second (demo) band push is gone;
  - verdict-keyed bands;
  - the density ribbon follows the cap rule;
  - drawer row keys are `a:`/`d:`;
  - two new props on `SpanView`.
  - The action-strip wiring is not touched.
- `webui/client/src/explore/SpanView.tsx` — `Band` gains `toggle` and `kind: SpanKind`; adds `EdgeField`, `BandToggles` and the legend popover rows; `BandLayer` uses `bandGeometry`; the axis carries `data-testid=span-axis data-t0 data-t1`.
- `webui/client/src/explore/signalModel.ts` — `buildMotifs` no longer adds the demo copy and always applies the run filter. This file is not in the prompt's list; it is the motif half of the same double push.
- `webui/client/src/explore/explore.css` — append-only block.
- `webui/client/src/theme.css` — one token, `--teal`.

## 4. What was built

1. **The pile, bridge side.**
   - `corpus._absolute` is `Working.discovery.spans.absolute_bounds`. Before, it was a second copy, even though spans.py's docstring said it delegated.
   - `corpus.spans` now returns `detections_complete_to_s`: the start of the last row returned when the read was capped, otherwise `t1`. Any reader can now tell a capped prefix from the whole channel.
   - An ambiguous legacy run is named once per process. The warning text is: `legacy detections: run N (detector, started YYYY-MM-DD) spans [a, b) … drawn as absolute`.
   - `spans.ambiguous_legacy_runs(conn)` lists those runs (run id, detector, date, `n`, `n_at_or_above_span_start`) for the migration below.
2. **The pile, client side.**
   - **Density ribbon:** `demoDensity` was built from `getSignalLive`'s capped read whatever its size. It is now built from the whole-channel read only when that read is not capped, and then it follows the run filter. Otherwise the ribbon is `ch.ribbons`, the bridge's whole-channel histogram.
   - **Second push removed:** the same capped copy was pushed as a second set of bands (with viewport filtering, so the bands themselves sat at the right x) and as `f:` motifs. Both are gone.
   - **Run filter:** it was skipped whenever `demo` was truthy, which was every live channel. It now always applies (`visibleDetections`). Consequence: the picker's default (the first three non-surrogate runs, which the chip already announced as "3 of N runs") is now what actually draws.
3. **Band kinds you can switch.** Six toggles (`band-toggle-<kind>`, `aria-pressed`, `data-on`), each showing an in-view count. Band rects carry `data-kind` (the verdict for an annotation), `data-toggle`, `data-start-s` and `data-in-view`. The selected motif stays amber whatever its kind, and still draws when its kind is switched off. The legend popover lists the six kinds plus "selected".
4. **Editable edges.**
   - `span-range` holds `span-left-input`, `span-right-input`, the hours beside each (4 decimals), and `span-duration`. It also carries `data-left` and `data-right`.
   - **Typing:** commits after 150 ms; Enter commits at once; Escape reverts; leaving the field commits a valid value.
   - **↑ / ↓:** step by the last digit typed (3 decimals → 0.001).
   - **Rules:** the left edge must be ≥ 0 and the right edge ≤ the channel's duration, at least 60 s apart, or the whole channel if it is shorter (the viewport's `MIN_SPAN_S`). A value that breaks a rule shows `span-<side>-error` under the field and moves nothing.
   - The page's keyboard map already ignores input fields. The overview box, drag, wheel and buttons are unchanged.

## 5. Tests

**Red commit `985ae8d`:**
- conda, `tests/test_span_plot_absolute.py`: 3 failed, 4 passed (no `legacy_ambiguous`, `warn_if_ambiguous` or `ambiguous_legacy_runs`).
- venv, `tests/test_webui_span_plot.py`: 4 failed, 2 passed (`corpus._absolute` was a copy; no warning; `detections_complete_to_s` missing twice).
- (b) and (c) pass on arrival. They are findings (the suspects are clean), not new behaviour.

**Green, as of the last commit:**

| Interpreter | File | Result |
|---|---|---|
| conda | `tests/test_span_plot_absolute.py` | 7 passed |
| conda | `tests/test_legacy_detections_migration.py` + `tests/test_import_boundaries.py` | 16 passed |
| venv | `tests/test_webui_span_plot.py` | 6 passed |
| venv | `tests/test_webui_corpus.py` | 10 passed |

There are no `tests/test_webui_explore*.py` files.

**What the tests pin:**
- **(a)** A non-ambiguous legacy row is shifted into its span. An ambiguous one is left to the heuristic, named once (detector and date), and listed by `ambiguous_legacy_runs`. A post-fix run and a short span are never flagged.
- **(b)** The schema refuses a NULL `span_start`, and a missing offset reads as a whole-channel run.
- **(c)** `cwt_ridges.detect` finds a bump at sample 3000 at about 3000. Its decimation is of the noise estimate only.
- **The pile:** 12 000 detections spread evenly give a capped read whose last row sits before 45 % of the channel, and `detections_complete_to_s` equals that row. `ribbons` counts all 12 000, with every bucket above 8 %.
- **Placement:** every detection lands inside its run's span at the right second.
- **Verdicts:** they are served uncollapsed.

**Client check (there is no client test runner):** `bandModel.ts` was run under plain `node` 25 with type stripping, using a scratch script outside the repo. It confirmed:
- a detection at 1000 s draws at x = 400 on [900, 1100] at 800 px, i.e. at x(1000);
- the run filter and its no-runs case;
- verdict → kind for five verdicts plus unknown;
- six distinct colours;
- toggle parsing, the edge rules and the edge stepping.

All passed. `BandLayer` draws through that same `bandGeometry`.

## 6. Smoke states

File: `webui/smoke_pages/zzzzzzzzzzz_span_plot.json`, channel 4. It sorts last because it zooms.

1. `span-plot-six-toggles` — six toggles; detected is on; both edge inputs and the duration are present.
2. `span-plot-detected-off` — click detected off: `aria-pressed=false`, and no `rect[data-kind="detected"]` remains in `span-bands`.
3. `span-plot-detected-back-on` — after a reload the toggle is still off (localStorage). Clicking turns it back on, so later states are not affected.
4. `span-plot-type-edges` — fit the channel, type left 995040.000, then right 1000000.000. Expect `span-range[data-left=995040.000][data-right=1000000.000]`, `span-axis[data-t0][data-t1]` with the same values, the duration "82.7 min", and no error.
5. `span-plot-bad-edge-says-why` — after fit, type right −5. Expect `span-right-error`, `aria-invalid`, and the view unchanged (left 0.000).
6. `span-plot-detection-at-its-second` — on [995040, 1002240], no band rect with `data-in-view=0`; the density ribbon is present.

**For the manager on real data:**
- Before and after, open a busy channel's overview. The blue density bars should spread over the channel, not sit in its first hours.
- `density-ribbon[data-demo]` should be 0 when that channel has more than 5 000 detections.
- If the bridge log shows `legacy detections: run N (…)` warnings, those are the runs §8 is about.

## 7. Gates I ran

- `tsc -b`: pass.
- `vite build`: pass (only the existing INEFFECTIVE_DYNAMIC_IMPORT notice).
- The four test files above, each with its interpreter.
- No browser smoke (there is no database in a worktree), no full suite and no `pytest -n`.

## 8. Open questions and risks — and the migration proposal

**Legacy ambiguous runs (the prompt's "Stop and report if").** These are runs with `span_start > 0`, `span_end − span_start > span_start` and `started_at < 2026-09-22`. The init-time migration refuses them as "ambiguous". The executor at that time added no offset to any detection, so every row of such a run is span-relative, including the rows at or above `span_start` that the read path leaves where they are.

Proposed one-time script, for the manager to run, modelled on `scripts/migrate_legacy_detections.py`:
- **`--dry-run`:** print `Working.discovery.spans.ambiguous_legacy_runs(conn)`, i.e. run, detector, date, `n` and `n_at_or_above_span_start`.
- **Refuse any run that:**
  - was not written by the local executor (for example a manifest import — check `audit_log` and the `artifact_path` / manifest origin), or
  - has a row that would land past `span_end` after shifting.
- **`--apply`:** in one transaction, `UPDATE detections SET start_idx = start_idx + span_start, end_idx = end_idx + span_start WHERE run_id = ?` for every row of each accepted run (not only the rows below `span_start`). Then assert every row lies in `[span_start, span_end]`, and write one `audit_log` row of kind `migration`.
- **Idempotence:** the init-time `migrate_legacy_detections` would not then touch these runs, because no row is below `span_start`. But a second `--apply` would shift them again. The script must mark migrated run ids, for example in the audit row's detail, and skip them next time.

I could not name the real runs; there is no database in a worktree. The warning and the dry-run will name them on the real database.

**Other risks:**
- **Fewer detections on screen by default:** the run filter now applies on live channels, so the picker's default of three runs is what draws.
- **`detections_complete_to_s` is not yet read by the client.** The client uses `detections_capped`. The new field is there for a "detections shown up to X h" note (polish-pass).
- **The "demo" chip** still shows on every live channel, because `getSignalDemo` is the live read. This is not my scope; it is for polish-pass.

## 9. Commits

```
75658c4 span-plot: six band switches, verdict colours, editable edges; no second push
fa07d78 span-plot: one absolute rule; a capped spans read says where its detections stop
985ae8d span-plot: red - the pile's suspects as fixtures, and the capped whole-channel read
(+ the commit adding this report)
```

## Critic round (2026-10-18)

**In plain words first.** The branch fixed the small overview strip but not the main span plot. The span plot asks
the bridge for "the detections in this view", and the bridge answered with the first 5 000 by time. On a channel with
~300 000 detections, any view wider than about 12 hours got only its opening hours' detections, so every blue band
sat at the left of the plot: the researcher's complaint, still there after the branch. The span plot now asks for an
even sample across the view instead, and says so in a sentence under the plot.

### Findings

| # | Severity | Where | What | Status |
|---|---|---|---|---|
| 1 | blocker | `webui/explore/useViewport.ts:50` → `corpus.spans` | The span view's bands come from the viewport read, which is capped at the view's first 5 000 detections by start. Any view holding more than 5 000 piled into its left edge. The branch fixed only the overview ribbon and the second push. | FIXED `6d3861a`: `GET /spans?spread=1` / `corpus.spans(spread=True)` thins a capped read evenly (every k-th row in time order) and returns `detections_total` and `detections_spread`. The default read is unchanged. `api.ts::getViewSpans` is append-only. A sentence under the plot says "N of M drawn, spread evenly; zoom in". 4 red tests, then green. |
| 2 | should-fix | `explore/SignalPage.tsx` | "No runs picked" drew an empty span with no word. | FIXED `6d3861a`: `span-band-note` gives the sentence. |
| 3 | should-fix | `explore/signalModel.ts::defaultPicker` | Now that the run filter applies, the default was the live read's `defaultRuns`: the three newest runs of *any* kind (`run_methods` lists runs without detections too). A channel whose newest runs found nothing would draw no detections on first open. | FIXED `aad1bf9`: the default is the three newest non-surrogate runs holding detections, falling back to `defaultRuns`. `CrossChannelPage` reads the same default. |
| 4 | should-fix | `corpus.spans` | `legacy_ambiguous` was evaluated on every row of every non-ambiguous run, which is 300k Python calls on a wide view, on every pan. | FIXED `aad1bf9`: each run is tested once per read. The warning is still once per run per process. |
| 5 | should-fix | `SignalPage.tsx` bands | Bands were not cut to the current view, so until a new view's read landed, the previous view's rows drew off-plot. Smoke state 6 (`data-in-view=0` absent) could flake on a slow bridge. | FIXED `6d3861a`. |
| 6 | nit | `SignalPage.tsx` totals | On a busy channel the Ribbons card showed the capped copy's length (5 000) as the channel's detection total. | FIXED `9b55f5d`. |
| 7 | nit | `explore.css` `.ex-band-toggle.off` | The off state is a grey pill with strike-through. This is a state, not a secondary button, so it is left as is. | NOT FIXED (judgement) |
| 8 | note | nav / drawer | ‹ N / M › and the drawer still walk the whole-channel read, which is a prefix of 5 000 on a busy channel, so nav cannot reach past the first ~12 h there. This predates the branch and is outside the prompt. | for polish-pass |

Checked and clean:
- `_absolute` is the one rule, and post-fix runs draw exactly as before.
- The warning is once per run per process (tested).
- The edge fields do not rewrite themselves while typing: `text` holds the typed value until blur, Enter or Escape. The debounced commit does not re-fire, because `parsed` is stable. Valid values pass through `clampView` unchanged, so there is no feedback loop.
- The smoke JSON is valid, uses only actions `smoke.py` knows (`fill`, `reload`, `wait_for`, `click`), and states share the tab, so state 3's reload sees state 2's `localStorage`.
- Channel 4 is `M2_aug` CH4_A2 at 1 Hz, and smoke already sends 995040–1067040 s on it, so the typed windows exist.

Out of the prompt's file list (critic):
- `webui/server/app.py` (one route parameter, `spread`);
- `webui/client/src/api.ts` (append-only: an interface merge and `getViewSpans`);
- `webui/client/src/explore/useViewport.ts` (one call).

### Gate after the critic round

| Interpreter | File | Result |
|---|---|---|
| venv | `tests/test_webui_span_plot.py` | 10 passed |
| venv | `tests/test_webui_corpus.py` | 10 passed |
| conda | `tests/test_span_plot_absolute.py` | 7 passed |
| conda | `tests/test_legacy_detections_migration.py` | 12 passed |
| conda | `tests/test_import_boundaries.py` | 4 passed |

`tsc -b` passes, and `vite build` passes.

### Merge risk

- `app.py`'s `get_spans` gains one parameter. The AR speed pass has `app.py` changes in flight, so check that hunk.
- `SignalPage.tsx`'s band block and the `SpanView` props line are where `explore-review-actions` also edits; expect a textual conflict there.
- `corpus.spans` sits below the coverage-cache region the AR pass changes.
