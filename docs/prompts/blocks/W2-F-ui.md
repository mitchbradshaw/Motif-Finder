# W2-F — The UI for wave 2: one view row, block-named exemplars, the Library's method choice, coherence, glyphs

Read [`00-common.md`](00-common.md) first — **but this prompt hands you the webui files its "Deliver" list names**
(the exception in `00-common.md`'s "Do NOT touch"). Commit prefix **`w2-f:`**. **Round 2 of wave 2:** you start from a
`main` holding W2-A…D (and W2-E if it merged first — check `git log`). Read their reports in
`docs/prompts/blocks/reports/W2-*.md`: each one's "Integration snippets" section is your input. Read `CLAUDE.md`'s
"Web UI" section, `docs/BLOCK_INTEGRATION.md` §2 (the drawing standard) and the memory of the last UI work in
`webui/PAGES_REPORT.md` as needed.

## In plain words

Wave 2 adds blocks whose answers the pages cannot yet draw properly: a block that turns events into windows, blocks
that name their own "typical member" per family, and two new ways of grouping the Library. This ticket makes each of
them show up honestly — and nothing else. It is polish on top of working blocks, under the 21 October priority
(`CLAUDE.md`): **friction first, then legibility**.

## What to build

1. **`spanset->windowset` drawing** — W2-A added the row (`views.py::MODIFIERS` and `registry.tsx`, mapped to the
   existing `WindowSetProcess`). Make it draw what the row promises: each window on the trace around its event, the
   anchor (`anchor_offset` column) marked inside it — extend `WindowSetProcess` for this case, or a small sibling
   component if extending it would put an `if` on every path; no new chart library.
2. **Block-named exemplars** — `webui/server/serialize.py::_grouping/_exemplars`: when the block's `meta` carries
   `exemplar_windows` (`{"<label>": <window index>}`) and an `exemplar_rule`, use those members and that rule instead
   of the feature-centroid pick (snippets: the snippet itself; families: the medoid). Still a member, never an average;
   an exemplar index outside the window set is a loud error, not a silent fallback. Test in
   `tests/test_webui_block_views.py` (or wherever `_exemplars` is tested — grep).
3. **The Library's method choice** — `webui/client/src/library/GroupingPage.tsx` hard-codes `ward` for
   `shape-distance` (≈ lines 72, 161, 610). The server's `GET /api/library/grouping-editor` should list the registered
   methods per basis with their `label`, `description` and `params` (read them from the methods registry — add that to
   `webui/server/library.py::get_grouping_editor`); the page offers them in the existing select, renders each method's
   params, and when `merge_heights` is `[]` replaces the tree-height histogram with one line saying *why* (no tree:
   k-Shape and HDBSCAN do not build one). The new omission reason `not_in_a_dense_family` gets a plain label wherever
   omission reasons are listed (grep the existing five).
4. **Coherence on the Family page** — W2-B added `coherence` to the family detail. Show `svd_entropy_norm` beside the
   amplitude numbers, with a one-sentence tooltip: "How much the members are copies of one shape: 0 = all the same
   shape, 1 = no shared shape. Ignores amplitude." Say "aligned" when it is.
5. **Glyphs** — `webui/client/src/analyse/glyphs.tsx` `BY_NAME` for every wave-2 block, from the reports' sketches.
6. **Smoke states** — `webui/smoke_pages/zz_analyse_run.json`: one state per wave-2 template (`event_clusters`,
   `minirocket_manual_labels` if it can run without human labels in the sandbox — else say so, `recording_snippets`,
   `event_families`), following the `w1-*-thumbnails` states' pattern (rule 9); and one Library state that switches the
   method to `hdbscan` and checks the omission line renders. Pick spans that run in seconds (read the wave-1 states).
7. `webui/client/src/api.ts` types for anything new the server sends.

## Gate (yours)

`npx tsc -b` and `npm run build` in `webui/client` (your worktree has its own `node_modules`? If not, **do not**
`npm install` — report it, the manager builds in the main checkout); the Python tests you touched plus
`tests/test_webui_block_views.py tests/test_webui_library.py tests/test_block_standard.py`. You **cannot** run smoke
(your worktree has no database): write the states, and say exactly what each should show — the manager runs smoke on
a sandbox bridge after merging.

## Deliver

`webui/server/views.py` (one row), `webui/server/serialize.py` (exemplars), `webui/server/library.py`
(grouping-editor methods), `webui/client/src/analyse/views/registry.tsx`, `.../analyse/glyphs.tsx`,
`webui/client/src/library/GroupingPage.tsx`, the Family page component (grep `coherence`/family detail),
`webui/client/src/api.ts`, `webui/smoke_pages/zz_analyse_run.json` (+ a Library smoke page if that is where Library
states live), and their tests. Nothing else under `webui/`.

## Acceptance

- [ ] Every wave-2 block's conversion resolves to a view **and** a modifier (`tests/test_block_standard.py`).
- [ ] A snippets / families Grouping draws the block's own member as each exemplar, with the block's rule as caption.
- [ ] The grouping editor offers ward / kshape / hdbscan for shape distance with their own params, and the no-tree line
      for the last two; Ward's editor is unchanged (its existing tests and smoke states still pass).
- [ ] `tsc -b` and `npm run build` clean.
