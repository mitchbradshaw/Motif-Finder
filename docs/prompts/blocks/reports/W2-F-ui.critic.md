> Filed by the manager session, 2026-10-14 15:12 — the final message of critic agent `abb17c18c4c6812d1` (a relaunch:
> the first W2-F critic, `a2f719e6738de2b64`, died mid-review on an API error) on branch
> `worktree-agent-adc5c4378118b320a` (base `c2e6e05`), verbatim.

# Critic report: W2-F, the UI for wave 2 (branch `worktree-agent-adc5c4378118b320a`, base `c2e6e05`)

## 1. In plain words

The branch does draw the new blocks, and mostly draws them honestly:
- event windows on the trace with the anchor marked;
- the block's own chosen member as each family's example;
- the method choice in the Library;
- coherence and the noise badge.

It does not merge cleanly in meaning, even though git merges it without conflicts. The branch was cut before W2-B's fix 2 and main's `beyond_noise` change, so:
- the Family page uses the old yardstick for "no more coherent than noise". Pure noise that sits a hair under its null is then shown as coherent, which is exactly the case main fixed.
- One Library smoke state will fail every time.
- W2-E's families (not yet merged) send their exemplars as a list, and this serializer will reject that list with a cryptic error.

## 2. Verdict

**Merge after fixes.**

## 3. Findings (most severe first)

**1. should-fix (near-blocker): the coherence verdict ignores `beyond_noise`.** `webui/client/src/library/FamilyPage.tsx:224`
- **What is wrong:** the line is `const noisy = c.null_p05 != null && v >= c.null_p05`, a bare comparison. Main `4db3684` returns `beyond_noise = score < 0.9 × null_p05` (`NULL_MARGIN`) and `null_margin`.
- **Why it matters:** in main's own verification, pure AR(1) φ 0.99 noise scored 0.805 against a p05 of 0.806, and a random walk 0.807 against 0.810. On this branch both are *below* p05, so the page shows no "no more coherent than noise" badge: it calls pure noise coherent. Any score in [0.9·p05, p05) is misreported the same way.
- **How shown:** read `Working/library/coherence.py:98-115, 188, 246` on main against `FamilyCoherence`. The UI pin test only greps for the phrase, so no test catches this.
- **Fix:**
  - `noisy = c.beyond_noise === false`, with "no null" when it is `null`.
  - Add `beyond_noise` and `null_margin` to `LibFamilyCoherence`.
  - Say the margin in the badge title.
  - Ideally surface the smooth-shape caveat. Today it only reaches the collapsed "the rule" details.

**2. should-fix (blocker for the smoke gate): `w2-method-ward-unchanged` will fail every time.** `webui/smoke_pages/library.json` (last two states)
- **What is wrong:** both states use the identical hash `library/grouping?from=atlas`. `smoke.py:1375` does `page.goto(#hash)`, which is a same-document navigation, and to an identical hash it changes nothing. The `g-05` pin is skipped because it is already set (`pin_grouping`, `smoke.py:1224`).
- **Result:** the editor stays mounted with the draft still on `hdbscan`. So:
  - `param-cut`, `param-nearest` and `feature-histogram` are absent;
  - `no-tree-line` is present, which is in this state's `expect_absent`.
- **How shown:** read `smoke.py` 1366-1400. Draft `method` lives only in component state (`GroupingPage.tsx`, `set({ method: v })`), not in the URL or the store.
- **Fix:** any one of:
  - put the Ward state *before* the HDBSCAN state;
  - give it `"cold": true`;
  - select `ward` back explicitly as an action.

**3. should-fix (blocker when W2-E merges): the exemplar format does not match W2-E.** `webui/server/serialize.py::_named_exemplars` (`dict(named)`)
- **What is wrong:** the serializer accepts only `{"<label>": idx}`, which is snippets' format. W2-E's `catalogue.shape_families` (commit `e7ef98b`, `Adapters/catalogue_shape_families.py:164`) writes `meta["exemplar_windows"]` as a **list** of `{family, window, start, start_s}`.
- **Result:** every shape-families Grouping row would render "render payload failed" with an unhelpful message. It is loud, so not silent, but the view is broken.
- **How shown:** my scratch run (`exp_exemplars.py`) gave `w2e-list -> RAISES ValueError dictionary update sequence element #0 has length 4; 2 is required`.
- **Fix:** either accept both shapes explicitly, or settle one format with W2-E before it merges. In either case, raise a clear "exemplar_windows must be {label: window} or [{family, window}]" message on anything else.

**4. should-fix: some exemplar cases are silently incomplete.** `serialize.py::_named_exemplars`
- **What is wrong:**
  - A block that names exemplars for some labels but not others gets none for the missing ones, with no note. Only −1 should be exempt.
  - A named label that is not in the grouping is silently ignored.
  - A non-integer index such as 3.7 is truncated to 3.
- **What is correct:** the centroid rule never covers a block that named its own exemplars (it is never used once `exemplar_windows` is present); out-of-set and wrong-label indices raise. Those two cases are tested.
- **How shown:** the same script:
  - `partial` gave `[(1,0),(2,3)]`, with label 3 silently missing;
  - `ghost-label` gave label "7" dropped with no error;
  - `float-idx` gave 3.7 → 3.
- **Fix:**
  - raise, or emit a per-cluster "the block named no exemplar" note, for an unnamed label ≥ 0;
  - raise on a named label not in the grouping and on a non-integral index.
  - `GroupingView.tsx:114`'s fallback text ("the WindowSet … is not at hand") would otherwise be the wrong explanation.

**5. should-fix: the coherence count text is stale after fix 2.** `FamilyPage.tsx:218`
- **What is wrong:** it reads "shifted more than a quarter of the length to align". After fix 2, `MISALIGNED_FRACTION = 0.4`.
- **Also stale:** the comment and tooltip still describe the null as "phase-randomised"; it is now trend-kept (`null_kind`).
- **Fix:** read the fraction from the payload, or say "0.4 of the length"; optionally show `null_kind`.

**6. should-fix: a lost verdict reads as confident.** `webui/client/src/library/chrome.tsx:401-410` (`NoiseBadge`)
- **What is wrong:** with no flags, the badge shows nothing. The comment claims "that is said in the tooltip of the grouping", but nothing in the diff says it.
- **Result:** a k-Shape/HDBSCAN grouping saved without a fit summary, or a family whose label is missing from `family_flags` (for example a hand group), shows no badge, which reads as confident.
- **Fix:** when the grouping's method has a null but `fitSummary` or the label's flags are absent, show a grey "verdict not saved" badge. Otherwise drop the false claim from the comment.

**7. should-fix: reopening a saved HDBSCAN/k-Shape grouping loses its string params.** `GroupingPage.tsx::seedFromGrouping` / `parseParamsText:97`
- **What is wrong:** only numeric tokens are parsed, so `cluster_selection_method=leaf` and `distance=euclidean` reseed silently as `eom` and `sbd`.
- **Why it matters:** this is the "from g-NN opens on somebody else's settings" bug the function's own docstring warns about.
- **Fix:** parse string tokens too, against the method's declared `str` params.

**8. should-fix (smoke viability): two template states cannot run yet, and one is slow.**
- **Unseeded templates:** `w2-minirocket-*` and `w2-recording-snippets-*` click `template-minirocket_manual_labels` and `template-recording_snippets`. Neither is in `webui/server/templates.py::CANONICAL`; both exist only as constants in their tests. Until the manager seeds them, all four states fail at the first click.
- **No state for `event_clusters`:** it is not seeded either. The branch instead hand-builds its first four steps (noise_threshold + Event shape + Event windows, no cluster step), which is reasonable but should be said in the merge notes.
- **The snippets run is slow:** zooming 2 h × 1.5⁷ gives [0, 34.2 h] (`clampView` shifts rather than clips, so I confirmed this holds). At 1 Hz (`M2_aug`, recording 1) the O(n²) estimate is about 49 s, plus the numba compile, so it is not "seconds" and will be slower on a loaded bridge.
  - Five zoom-outs (15.2 h, ≥ 12 pieces = 2 × k_max) would cost about 10 s.
  - The run is not refused: the surrogate is off by default (`toolbar.tsx`), and `zzz_surrogates` runs later. Snippets is uncalibrated, so the route is `unknown` and the run proceeds.
- **The view-history assumption is low risk:** this state relies on channel 1 opening at its default [0, 2 h]. No earlier smoke state visits channel 1, and `explore.view` is only reused when `channelId` matches.
- **The event-windows state can come up empty:** if the 2 h example span gives noise_threshold no events, `window-anchor` will be absent and the block state fails. I could not check without the DB.
- **Selectors:** I verified every selector exists in the components (`insert-N`, `modal-card-*`, `modal-insert`, `delete-step-4` = the classifier, `analyse/block/N` 0-based, `feature-heatmap`, `windowset-key`, `cluster-strip`, `exemplar-1` because snippets labels are 1-based, `label-rules`, `param-method` as a native `<select>`, `preview-uncomputed`, `omit-outside`).
- **Fix:**
  - seed the two templates, or mark the states as pending;
  - shorten the snippets zoom to 5 clicks;
  - for event windows, add a fallback expectation for zero events, or check the example span.

**9. nit: the type still lists HDBSCAN's removed flag fields.** `webui/client/src/api.ts` `LibFamilyFlags` declares `null_max_separation` / `null_max_size` and lacks fix 2's `ratio` / `margin`. Nothing reads them: the tooltip uses only `flags.why`, which on main carries ratio, p05 and the smooth caveat. Update the type.

**10. nit: snippets' −1 label can be misnamed.** `serialize.py` names −1 "unlabelled · mostly NaN" whenever `"n_windows_nan" in meta`, and snippets always sends that key. Snippets' −1 also covers "no vote" windows (`snippets.py:645`, `labels[labels == 0] = -1`). Name it by count instead, for example "unlabelled (N mostly NaN)".

**11. nit: event windows past the omitted-rows cap are not explained.** `WindowSetView.tsx::EventWindowsKey` draws `warnings` but not `notes`. When `omitted_rows` is capped (`OMITTED_ROWS_MAX`), the events past the cap are drawn as plain bands with no window and no red outline, and the note that explains the cap never appears. Render `notes`, and outline any event that has no window, by event_index set-difference.

**12. nit: a stale refusal card.** The 422 refusal card stays visible after the user edits params, so it still describes the old settings. Clear `refusal` when the signature changes.

**13. Scope (item 5).** The files outside the Deliver list are all justified:
- `GroupingView.tsx`: the two-line caption is required by the acceptance item "with the block's rule as caption".
- `AtlasPage.tsx`: the tile badge is W2-B item 1.
- `api/library.ts`: without the `methods` pass-through the select only ever showed Ward. A pin test guards it.
- `chrome.tsx`: W2-B item 6 names this file.
- `WindowSetView.tsx`: the prompt allows "a small sibling component".
- `library.json`: the prompt allows a Library smoke page.

**What checked out:**
- **Ward's editor (item 3) is unchanged in behaviour:**
  - the `linkage` label became `method`, listing the registry with Ward first;
  - `paramsFor` / `validate` and the cut/nearest controls are the same for Ward;
  - the existing Library tests pass.
- **HDBSCAN `epsilon` is never wired to the tree cut:**
  - non-Ward methods get `MethodParams` from the registry spec;
  - the cut slider is not rendered for them, and `d.cut` is not sent.
- **The six W2-B wiring items are present:**
  1. the badge appears in the editor preview from `result.families[].flags`, and in the atlas and Family page from `fitSummary.family_flags[label]`;
  2. `fit_summary` round-trips on save;
  3. the 422 card shows `message`, the estimate and one-click `cheaper[]`, and no script. `cheaper`'s `sample` lands in the method params.
  4. epsilon is its own input, never the tree cut (above);
  5. coherence shows beside "noise like these members' scores X", with the squared variant, `top_share`, the reason, an error card, `heldOut` and `notOnDisk`. The verdict logic is wrong, as finding 1 says.
  6. the three omission labels are added.
- **Test-first:** the first commit `980a105` touches only `tests/`. The green commit only strengthened one pin.

## 4. What I ran

- **Type-check and build:** I `robocopy`'d the client to scratch with a `node_modules` junction inside the scratch copy only.
  - `npx tsc -b`: clean, 84 s.
  - `npx vite build --outDir <scratch>\dist`: built, 23 s (one pre-existing `INEFFECTIVE_DYNAMIC_IMPORT` warning).
  - Junction removed afterwards; the real `node_modules` is untouched.
- **Python tests:** `webui\.venv` python, `-n 4`, from the worktree: `test_webui_block_views`, `test_webui_library`, `test_block_standard`, `test_webui_serialize`, `test_webui_w2f_ui`, `test_import_boundaries`. Result: **307 passed, 3 xpassed**, in 254 s. The machine was loaded by other agents, so timings are inflated.
- **Merge check:** `git merge-tree main <branch>` is clean, with no textual conflicts. The semantic drift is findings 1 and 5.
- **Serializer experiments:** scratch `exp_exemplars.py` (conda python), run on nine cases. The results are quoted in findings 3 and 4.
- **Read-throughs for the smoke states:** `smoke.py` (navigation, the `select` action, `pin_grouping`, the storage clear), `useViewport` / `clampView`, `route_local` with the surrogate default, the snippets cost model (24 s at 24 h, O(n²)), the templates in `templates.py` and the template tests, and the W2-E report and commit `e7ef98b`.
- **Not run:** smoke itself, since there is no database.
