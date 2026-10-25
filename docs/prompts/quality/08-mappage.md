# tq-mappage — the Discovery Map page in focused modules, its hide/sort code written once

Package id for commits: `tq-mappage`. Read `docs/prompts/quality/00-common.md` first. The manager already moved
MapPage's extent import to `charts/domain.ts`.

## The findings

1. **The hide/sort layout code is copy-pasted between level 3 and level 2, and `arrange` returns keys.**
   File: `webui/client/src/discovery/MapPage.tsx` (403 → 675 lines in the night wave), at `:~150-155`,
   `:~343-362` vs `:~444-460`, and `:~379-391` vs `:~467-478`.
   - Both `layout` memos build `items` with `values`/`count`, call `arrange` (`discovery/mapOrder.ts`), then do
     `new Map(...colId...)` and `a.shown.map(k => byId.get(k)!)`. `orderRows` does the same with `by.get(k)!`:
     four key→object round trips with non-null assertions.
   - Each level has its own `line(row, hidden)` renderer branching on `hidden` per cell, plus near-identical
     shown/hidden `<th>` pairs with `HideButton`.
2. **`SignalStrip` pushes a closure up to its parent** through `onRange` / `setRange(() => r)`, and hover uses a magic
   `'__signal'` row key. File: `MapPage.tsx:~544-560`, `:~612`, `:~665`.
   - The child owns the read (`getOverview`) and hands the parent a function so the readout can query it. That takes
     an effect with an exhaustive-deps disable, a function held in state, and a sentinel string sharing the namespace
     with real row keys.
   - The closure also hand-rolls a min/max loop.

## The remedy

- **`arrange` returns the items themselves:** `arrange<T extends {key: string}>(items: T[], …) => { shown: T[]; hidden: T[] }`.
  The `byId` maps and the `!` go away.
- **Extract one shared helper,** e.g. `arrangeColumns(channels, rowKeys, cellsOf, view)`, used by both levels, and
  one `<HideableHeader>`.
- **Lift the signal read** into the channel level with a `useSignal(dataset, channel, hours)` hook returning
  `{ values, at, state }`. `SignalStrip` becomes presentational, and the readout computes the range inline over the
  slice with `extentOf` (`charts/domain.ts`).
- **Type hover** as `{ kind: 'signal'; bin } | { kind: 'row'; key; bin }`.
- **Move the map into `webui/client/src/discovery/map/`:** `DatasetsLevel.tsx`, `DatasetLevel.tsx`,
  `ChannelLevel.tsx`, `SignalStrip.tsx`, `TopScrollbar.tsx`, `hideSort.tsx`, or whatever split the code actually
  has. Keep `MapPage.tsx` as the route entry the app imports, or update the import.

## Behaviour that must not change

- **Every level draws the same rows, columns, order, hidden lines, sort controls, restore buttons, readout text and
  scrollbars.**
- **Every test id stays.** The smoke states and `tests/test_webui_site_map_order.py` read them.
- **The signal strip's states** stay: failed, refused, loading, empty, drawn.
- **No `Math.max(...xs)` over data-sized lists.** Spreading a list that size into the argument list is a RangeError.

## Files

`webui/client/src/discovery/MapPage.tsx`, `discovery/mapOrder.ts`, new files under `discovery/map/`,
`discovery/discovery.css` only if a class must move.

Tests: `tests/test_webui_site_map_order.py` (it reads MapPage.tsx as source text: point its reader at the new files,
or at the directory, and keep every assertion), `tests/test_night_disc.py`, and
`grep -rln "MapPage\|mapOrder" tests/`. Record the failure set first.

Smoke units for the manager: `zzzzzzzzzzz_a1_site_map`, `zzzzzzzzzzz_a1_night_disc`.
