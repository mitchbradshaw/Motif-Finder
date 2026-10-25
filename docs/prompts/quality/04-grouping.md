# tq-grouping — split the Grouping editor back under 1000 lines, one job lifecycle

Package id for commits: `tq-grouping`. Read `docs/prompts/quality/00-common.md` first.

## The findings

1. **`webui/client/src/library/GroupingPage.tsx` crossed 1000 lines in the night wave (976 → 1013).** It mixes four
   unrelated concerns:
   - the pure draft model (~72–237: `Draft`, `BASE`, `METHOD_FOR`, `DISTANCE_BASES`, `methodOf`,
     `parseParamsText`, `seedFromGrouping`, `parseEdges`, `validate`, `paramsFor`);
   - the job hook (`useGroupingJob`, ~249–343);
   - the editor plus the tree panel (~358–835);
   - the parameter widgets and histogram (~847–1013: `Params`, `MethodParams`, `NoDistribution`, `quantileEdges`,
     `FeatureHistogram`).

   It also declares a private `extentOf(dist: FeatureBin[])` (~line 156) that shadows the app's one extent rule
   (`charts/domain.ts::extentOf`) under the same name with a different meaning.
2. **`library/treeSource.ts` (new) re-declares rules the page and chrome already own.**
   - `TREE_BASES` duplicates `DISTANCE_BASES`.
   - Its `num` duplicates `groupingNum` (`library/chrome.tsx:~178`).
   - Its newest-pick loop is `newestGrouping` (`chrome.tsx:~70`) with a filter.
   - `isTreeGrouping` restates the `treeGid` condition in the editor (~line 453:
     `current.unit === d.unit && wardDraft && currentMethod === 'ward' && DISTANCE_BASES.includes(current.basis)`).
   - It reads `g.method`, which the `Grouping` type does not declare, and the editor then needs
     `(current as Grouping & {recipeHash…})`-style casts (~line 420).
3. **The job lifecycle has four refs for one cancellation.** `useGroupingJob` tracks the job through `alive`, `gen`,
   `liveJob` and `view.jobId`. Cancellation is spread over:
   - the unmount effect (~261, a 200-character one-liner);
   - `start` (`if (!alive.current || mine !== gen.current) { void cancelJob(j.job_id) … }`);
   - `cancel`;
   - `reset`.

   `close` still calls `job.cancel(); job.reset()`, though unmount now cancels.
4. **The auto-build is a seven-term predicate in the parent, feeding a child ref.** The parent passes
   `autoBuild={d.unit === 'motifs' && d.basis === 'shape-distance' && seededFrom === treeGid && !touched.current && !stateQ && job.view.phase === 'idle' && !job.view.result && !job.view.refusal}`.
   - The child keeps a `builtOnce` ref and an effect.
   - It branches its render on `if (!tree.tree && builtOnce.current && busy)`: a non-reactive ref read during
     render, correct only because `busy` happens to re-render.

## The remedy

- **Split the file:**
  - `library/groupingDraft.ts`: pure. It holds the draft model plus `isTreeGrouping` and replaces `treeSource.ts`.
    Write it so a Node test could load it (pure siblings may be imported with an explicit `.ts`).
  - `library/useGroupingJob.ts`.
  - `library/TreePanel.tsx`.
  - `library/GroupingParams.tsx`: the parameter widgets and histogram.
  - That leaves `GroupingPage.tsx` at roughly 450 lines.
  - Rename the private bin-extent helper so it no longer shadows `extentOf` (or express it through
    `charts/domain.ts`).
- **treeSource:** becomes `isTreeGrouping(cur) ? cur : newestGrouping(all.filter(isTreeGrouping), unit) ?? cur`,
  reusing `newestGrouping`, `groupingNum` and `DISTANCE_BASES`. The editor's `treeGid` condition uses
  `isTreeGrouping`.
- **Types:** declare `method`, `recipeHash` and `treeKey` on `Grouping` (wherever it is declared; check `api.ts` /
  `api/library.ts`) if the bridge sends them, so the casts go.
- **Job lifecycle:** one AbortController per `start()`. `cancel`, `reset`, a newer `start` and unmount all abort it.
  A job id that arrives after its controller was aborted is cancelled at once. This deletes `alive`, `gen` and
  `liveJob`. Drop the redundant `job.cancel()` in `close` only if unmount truly covers it.
- **Auto-build:** lift the tree read into a `useGroupingTree(...)` hook used by the editor. The editor decides the
  auto-build in one effect with an `autoBuilt` state (not a ref) and passes `building` down. This deletes the
  `autoBuild` prop and the `builtOnce` ref.

## Behaviour that must not change (night-review)

- **The editor opens on a tree grouping** when one exists for the unit, and builds a missing tree automatically, only
  for motif shape distance, and only once.
- **The grouping job is cancelled on every exit:** close, unmount, a newer start, reset (F2).
- **A refusal or a result** stays on screen until the researcher acts.
- **Every test id** the smoke states use stays.

## Files

`webui/client/src/library/GroupingPage.tsx`, the four new files, `library/treeSource.ts` (delete), `library/chrome.tsx`
(exports and imports only, if `newestGrouping` or `groupingNum` must be exported), the file that declares `Grouping`
(the type only).

Tests: `tests/test_night_review.py`, `tests/test_webui_library_tree.py`, `tests/test_webui_w2f_ui.py`, and
`grep -rln "GroupingPage\|treeSource\|useGroupingJob\|builtOnce\|autoBuild" tests/`. Several pin GroupingPage.tsx by
source text: when code moves to a new file, move the pin with it and say so. Run them before your first change and
record the failure set.

Smoke units for the manager: `library_grouping_url`, `zzzzzzzzzzz_an_library_tree`, `zzzzzzzzzzz_night_review`, `library`.
