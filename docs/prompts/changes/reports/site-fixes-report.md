WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\agent-a0d961b095baf8c05
BRANCH: worktree-agent-a0d961b095baf8c05

# site-fixes (`ux-1019`) — report

Base: `32bef5b` (main with the AR speed pass `5a20070` merged, plus the docs commit after it).

## 1. Assumed

- **Item 3 (AM drop default), the main call.** The setting is **shown, not switched automatically**. A B.2 template
  is Window pool → Trace shape → Shape clustering. A Window pool is a source block, so no detector can come before
  it: a chain holding `detection.drop_detection` and `preprocessing.trace_shape` fails `validate_recipe_steps`.
  That means a pool chain holds nothing that says "drop work". I tried two rules and dropped both:
  (a) a drop-detector step in the chain can never fire, because no valid chain has one;
  (b) a rule keyed on the template's name would be read by Launch but not by the Analyse run (`/api/runs` carries no
  name). The tree and the model would then be cut at different alignments, and the mapping would point at the wrong
  clusters. On top of that, Analyse already writes `align: centre, anchor_frac: 0.5` into every new Trace shape step
  (`validateParams({})`), so a default that only applies when the field is empty would never fire from the UI.
  What I built: the core holds the drop setting (`shape.DROP_ALIGN = "trough"`, `DROP_ANCHOR_FRAC = 0.333`). The
  bridge's B.2 setup carries the anchor and that setting. Launch's setup line shows `align … · anchor …` with a tip
  that names the drop setting and says where to set it. The block's anchor description names it too. The block
  defaults and every shape key are unchanged.
- **Item 2:** the eye buttons and show all / hide all are in the "Where each run fires" card: an eye on each drawn
  row's label, and the hidden runs on one line under the rows. I put no eye on `chrome.tsx` `RunRow`, which the later
  `discovery-coverage-and-gauge` prompt edits. The shown set is keyed by the session's name in the demo store
  (`discovery.shown`): it survives moving between Discovery pages but not a reload, like `discovery.picks`. The
  Scoreboard still counts every run; "counted everywhere" is read as this card's read and drawing.
- **Item 2, show all / hide all are never disabled.** Both are idempotent, so the smoke click can never hang on a
  disabled button.
- **Item 4:** "the card" is read as the chain row's caption (`analyse/captions.ts`). The block page's parameter
  panel already listed `baseline_window_s`.
- **Item 5:** the control is the topbar's disabled "display · detrended (display only)" dropdown (`:216`), not the y
  dropdown. It is now a Seg named "detrend". Leaving it unset keeps the window's own default (linear, or raw for a
  Library edge's window).
- **Item 6:** "Header path strip: awaiting the researcher's look" is recorded as "kept as built".

## 2. In plain words

Think of the open app as a book whose chapters are fetched on demand. When the client is rebuilt, the old chapter
files disappear, and a page left open used to crash with a red card when it asked for one. Now it reloads itself
once and opens what you clicked.

- **Discovery:** Discovery's timeline starts with only the human row; you turn each run on with its eye (or all at
  once), so a fresh session opens with less clutter.
- **Launch, Decompose and Cross-channel:** Launch now says where in each window the aligned point sits and names the
  drop setting (trough a third in). Decompose's card names its baseline window and its 600 s default. Cross-channel's
  detrend switch (raw, linear or cubic) now changes the numbers.

## 3. Files

Created:
- `webui/client/src/shell/chunkReload.ts`: `loadChunk`, `lazyNamed`, `installChunkReload` (item 1).
- `docs/prompts/changes/reports/site-fixes-report.md`: this report.

Modified:
- `webui/client/src/App.tsx`: uses `lazyNamed` from `chunkReload` and installs the preload listener (item 1).
- `webui/client/src/analyse/index.tsx`: the two lazy pages go through `lazyNamed` (item 1).
- `webui/client/src/discovery/session.ts`: `shown`, `isShown`, `toggleShown`, `setShown` (item 2).
- `webui/client/src/discovery/RunsPage.tsx`: in `WhereFires` only, the shown-set filter, the eye buttons, the hidden
  line and show all / hide all (item 2).
- `webui/client/src/discovery/discovery.css`: `.dsc-fires-eye` and `.dsc-fires-hidden` (item 2).
- `webui/smoke_pages/discovery.json`: the `discovery.runs--default` state's actions (item 2).
- `webui/smoke.py`: **shared file.** A 4-line insertion before the discovery flow's `fires-cell` count, which clicks
  `fires-show-all` (item 2). It is not append-only, but it is a local insertion.
- `Working/training/shape.py`: `DROP_ALIGN` and `DROP_ANCHOR_FRAC` added (item 3).
- `Working/training/shape_forest.py`: `launch_shape(shp)` added (item 3).
- `webui/server/shape_routes.py`: `b2_setup`'s `shape` comes from `sf.launch_shape` (item 3).
- `Adapters/preprocessing_trace_shape.py`: the `anchor_frac` description names the drop setting (item 3).
- `webui/client/src/api/shape.ts`: **shared, append-only.** Optional `anchor_frac` and `drop_default` on
  `B2Setup.shape` (item 3).
- `webui/client/src/models/B2Launch.tsx`: the setup line shows the anchor and has a tip (item 3).
- `webui/client/src/analyse/captions.ts`: a `preprocessing.decompose` case (item 4).
- `webui/client/src/api/explore.ts`: **shared.** A new optional last parameter `detrendSel` on `getCrossChannel`,
  and the cubic wording of its open-question line (item 5).
- `webui/client/src/explore/CrossChannelPage.tsx`: the `?detrend=` read, the detrend Seg replacing the display
  dropdown, and the wording of the note and tips (item 5). The action row is untouched.
- `webui/smoke_pages/zzzzzzzzzzz_aq_cross_channel.json`: one state appended (item 5).
- `docs/prompts/fixup/BACKLOG.md`: §1 and §5 (item 6).
- `tests/test_webui_shape_b2.py`: one test appended.

## 4. What was built

1. **Stale chunk → reload once.** A stale-chunk error (the message matches the prompt's regex) with no
   `ub:reloaded-for-chunk` flag sets the flag, reloads, and leaves the promise pending so Suspense keeps its loading
   card. The flag is cleared once any chunk loads. A failure after the reload reaches the red card as before.
   `vite:preloadError` takes the same road; any preload failure counts as stale, including CSS's "Unable to preload
   CSS" wording.
2. **Shown-off by default in Discovery.**
   - A new session draws the human row alone. The card head reads "n of m runs drawn", with show all / hide all.
   - A drawn run's label has an eye with a filled swatch: click it to hide the run. Hidden runs wait under the rows
     as buttons with a hollow swatch and an eye-off icon: click one to draw it.
   - The fires read asks only for drawn runs.
3. **AM: anchor shown, drop setting named.** See Assumed for why the default is not switched by itself. This
   deviates from the prompt's "make the default depend on the template kind".
4. **AO baseline window on the card.** The caption reads "baseline window 600 s (default) · running median · noise
   above ¼ Nyquist · signal goes on". The default comes from the adapter card's ParamSpec.
5. **AQ cubic control.**
   - The control is a raw · linear · cubic Seg, written to `?detrend=` and passed to `/api/cross/{id}?detrend=`.
   - The detrend note now reads "lag · r on the cubic-detrended window", with a matching title. A raw page window
     that is not an edge's gets its own title.
   - The r tip, the classification tip and the read's open-question line cover the cubic case.
6. **BACKLOG.** §1's six rows are now resolutions, and §5's two rows are closed.

## 5. Tests

- **Red commit `3be210e`** (`tests/` only): `test_launch_setup_names_the_anchor_and_the_drop_default` failed on the
  base with `KeyError: 'anchor_frac'` (1 failed, 1 passed, 4 deselected; webui/.venv). It pins that the B.2 setup
  carries `anchor_frac` 0.5 for a centre pool chain, and `drop_default == {"align": "trough", "anchor_frac": 0.333}`.
- **Green, run with webui/.venv:**
  - `tests/test_webui_shape_b2.py`: 6 passed.
  - `tests/test_webui_cross_window.py`: 7 passed.
  - `tests/test_webui_cross_channel.py`: 9 passed.
- **Green, run with conda:**
  - `tests/test_shape_forest.py`: 8 passed.
  - `tests/test_training_shape_align.py`: 20 passed.
  - `tests/test_block_standard.py`: 222 passed.
  - `tests/test_import_boundaries.py`: 4 passed.
- **No test for items 1, 2, 4 and 5.** The client has no unit runner. Item 1 cannot be exercised headless. Items 4
  and 5 change no bridge or block spec.

## 6. Smoke states

- **`discovery.json` › `discovery.runs--default`:** I chose to seed the shown set from the state's actions rather
  than change its expectation. The state waits for `fires-show-all`, clicks it, waits 1.5 s, then expects
  `runs-card`, `fires-cell` inside `where-fires`, and `browser-trace svg` as before.
- **`smoke.py` discovery flow:** clicks show all before counting `fires-cell`.
- **`zzzzzzzzzzz_aq_cross_channel.json` › `ux1019-cubic-detrend`** (`explore/cross-channel/4?detrend=cubic`): must
  show `detrend-seg`, `detrend-note[data-detrend="cubic"]`, and an `r-raw-*` (the as-recorded r).
- **The existing AQ states** still expect `linear` / `none` on their default paths. They should pass unchanged, since
  no `?detrend=` means the old default.
- **To check on real data:** open a fresh Discovery session and confirm only the human row is drawn, then press one
  eye and confirm that run's row is read and drawn. Open Launch from Analyse › Train model and confirm the setup line
  reads `align centre · anchor 0.50 (the middle) · …`.
- **Item 1 by hand:** open the app, rebuild the client, then click another workspace. The page should reload once
  and open it.

## 7. Gates I ran

- `tsc -b`: clean, run twice.
- `vite build`: built. Its one INEFFECTIVE_DYNAMIC_IMPORT warning about `kit/Gallery.tsx` is not caused by this
  change.
- The test files listed in section 5.
- No browser smoke: there is no database in the worktree.

## 8. Open questions and risks

- **AM, plain words first.** Lining up windows on the bottom of a drop (a third of the way in) suits drops; centring
  suits everything else. The app cannot tell which kind of work a pool chain is for.
  - Options: (a) leave it as built — the researcher sets trough / 0.333 on the Trace shape block, and Launch names
    the setting; (b) add an explicit "for drops" switch on the Window pool or the chain that both Analyse and Launch
    read; (c) key it on the template's name, which is unsafe: Analyse and Launch would disagree.
  - Recommendation: (a) now, (b) if the researcher wants it automatic.
- **Item 2:** the shown set lives in the in-memory demo store, so a reload empties it (as with picks). The Scoreboard
  still lists every run.
- **Item 1:** a stale chunk whose error wording matches none of the three patterns still shows the red card. With
  the flag set, a second stale failure in the same tab shows the red card until any chunk loads.
- **`webui/smoke.py`:** the insertion is not append-only. Merge it by hand if another branch edits the same lines
  around `discovery_fires_cells`.

## 9. Commits

    baf367c ux-1019: BACKLOG - the six section-1 decisions recorded as resolved, section-5 rows closed
    4d1a921 ux-1019: Cross-channel's detrend control is raw · linear · cubic and reaches the read (AQ)
    3807395 ux-1019: Decompose's card names its baseline window and the default (AO)
    3a41c5c ux-1019: Discovery draws no run until its eye is on
    75f4cc5 ux-1019: a page open across a rebuild reloads once instead of dying
    8aba7ab ux-1019: Launch's setup line shows the anchor and names the drop-work setting (AM)
    3be210e ux-1019: test - Launch's B.2 setup names the anchor and the drop default (red)
    (+ this report's commit)
