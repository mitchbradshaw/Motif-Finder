# Fixup AN — a dendrogram in the Library: see how the families cluster, preview other cuts, apply one

**Written 2026-10-13 from the researcher's list ("dendrogram in library — to show how families are clustered. option
to preview different groupings at different cuts, and then run a grouping at a different cut, saving new grouping
template or using cached existing cuts"). Not run yet. The biggest of the 2026-10-13 tickets; expect two to three days.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md` (rule 4: bulk arrays never enter the database), `docs/LIBRARY_STORAGE.md`,
`Working/library/grouping/engine.py` (`run_grouping`, `preview`, `GroupingResult.merge_heights`),
`Working/library/grouping/methods/ward.py` (`fit` keeps `payload["linkage"]`; `assign(fit, cut=…)`; `merge_heights`),
`webui/server/library.py` (the `regroup` job, `_grouping_payload`), `webui/client/src/library/GroupingPage.tsx` (the
editor and its cut field), `webui/server/shape_routes.py` (`tree_and_shapes`, `shape_cut` — a tree served as
icoord/dcoord already) and `webui/client/src/analyse/views/TreePage.tsx` (**a dendrogram with a draggable cut line
already exists** — reuse it, do not draw a second one).

Commit prefix `fixup-an:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only.**

## In plain words

The Library sorts motifs into families by building a tree: the two most alike shapes join first, then the next, and
so on until everything is one trunk. Cutting the tree at a height gives the families; a lower cut gives more, smaller
families, a higher cut fewer, bigger ones. Today the researcher types a cut number and waits for the whole regroup to
run to see what it does, and the tree itself is thrown away as soon as the families are written. The ask is to keep
the tree, draw it, let the researcher slide the cut and see the families change instantly, and only then run (and
save) the grouping at the cut they like.

## Facts to build on

- `ward.py` builds a real scipy linkage and keeps it in the fit; `engine.run_grouping` keeps only `merge_heights` from
  it. The linkage is the tree; it must be persisted.
- `TreePage.tsx` + `shape_routes.tree_and_shapes` / `shape_cut` already serve and draw a tree with a cut line, counts
  and cards for the Shape clustering block. Same shape of payload, same component.
- A grouping is a `groupings` row; "save a new grouping" is what `POST /api/library/groupings/run` already does.
  Hand edits survive regrouping (P22).

## Decide this way

- **Persist the tree per fit, on disk**, under the library's derived store (`docs/LIBRARY_STORAGE.md` says where), as
  one `.npz`: linkage, leaf order, the member refs in leaf order, the method params minus the cut, and a key that is
  the hash of (member content hashes, basis, method, params-minus-cut). The `groupings` row references it by path.
- **Preview a cut from the tree, never by refitting**: `fcluster` at the cut is milliseconds; the preview route answers
  families, sizes, how many members move relative to the current grouping, and what is omitted under `min_group`.
- **"Use cached existing cuts"** = the key above: an apply whose member set and params are unchanged reuses the stored
  fit and only re-assigns; the regroup job says *reused the tree* in its progress.

## Work

1. Core: `ward.fit` result serialisable (`save`/`load` beside `trace_shapes`' pattern in `Working/training/shape.py`);
   `engine.run_grouping` writes it and records the path and key; `engine.cut_preview(tree, cut, params)`.
2. Bridge: `GET /api/library/groupings/{id}/tree` (icoord/dcoord/heights as `shape_routes` does), `GET …/cut?cut=`
   (the preview), and the regroup job's reuse of a stored fit when the key matches.
3. Page: Library › Grouping gets the dendrogram panel above the editor; the cut line and the editor's `cut` field are
   one value; *Preview at this cut* is instant; *Compute and apply* is today's run, now at that cut, and names a new
   grouping as today. A grouping made before this ticket has no tree: the panel says so and offers to build one
   (a regroup at its own cut).
4. Omit the tree panel for feature-bin groupings (no tree; `feature_bins.py` says `merge_heights` is empty).

## Acceptance

- [ ] After a regroup, a tree file exists for the grouping; the `groupings` row references it; the DB holds no array.
- [ ] `cut_preview` at the grouping's own cut reproduces its families exactly; at another cut it matches `assign()`.
- [ ] A second apply with the same members and params reuses the fit (the job reports it; no second linkage is built).
- [ ] The page's cut line, the editor field and the URL agree; sliding the line updates the family count without a job.
- [ ] Hand edits are re-applied after an apply from the tree, as today.
- [ ] `pytest`, `tsc -b`, `npm run build`, smoke (walk: open Grouping → drag the cut → preview → apply) pass.

## If it splits

AN-1 core + bridge (tree persisted, preview route, reuse) · AN-2 the page. AN-1 is useful on its own.

## Report

`docs/prompts/fixup/reports/AN-library-dendrogram.md`. Update `docs/rq_roundA/RQ1-*.md` if the cut preview changes
what can be answered about family structure.
